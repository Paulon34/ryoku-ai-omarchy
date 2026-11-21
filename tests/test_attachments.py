import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ryoku_ai.attachments import (
    AttachmentError,
    extract_file,
    extract_many,
    format_attachments_for_prompt,
    inspect_file,
    inspect_many,
    parse_request_stdin,
    persist_extracted_text,
    load_extracted_text,
    delete_extracted_text,
    vision_status,
)
from ryoku_ai.history import HistoryStore, build_context_window


class AttachmentExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, data: bytes | str) -> Path:
        path = self.root / name
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return path

    def test_extracts_utf8_text(self):
        path = self._write("nota.md", "Olá 緑 — café\n")
        item = extract_file(path)
        self.assertIn("緑", item.text)
        self.assertFalse(item.truncated)
        self.assertEqual(item.extension, ".md")

    def test_empty_file_rejected(self):
        path = self._write("vazio.txt", "")
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(path)
        self.assertEqual(ctx.exception.code, "empty_file")

    def test_missing_file(self):
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(self.root / "nao-existe.txt")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_unsupported_extension(self):
        path = self._write("foto.bin", b"not-an-image")
        path = path.rename(self.root / "foto.exe")
        path.write_bytes(b"MZ")
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(path)
        self.assertEqual(ctx.exception.code, "unsupported_type")

    def test_image_preview_ok_but_extract_blocked(self):
        path = self._write("shot.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        meta = inspect_file(path)
        self.assertEqual(meta["kind"], "image")
        self.assertFalse(meta["vision_available"])
        self.assertIn("indisponível", meta["warning"].lower())
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(path)
        self.assertEqual(ctx.exception.code, "vision_unavailable")
        status = vision_status()
        self.assertFalse(status["vision_available"])
        self.assertTrue(status["siwc_text_only"])

    def test_inspect_many_allows_image_preview(self):
        path = self._write("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        items = inspect_many([str(path)])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["filename"], "a.png")

    def test_symlink_denied(self):
        target = self._write("real.txt", "segredo")
        link = self.root / "link.txt"
        link.symlink_to(target)
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(link)
        self.assertEqual(ctx.exception.code, "symlink_denied")

    def test_too_large(self):
        path = self._write("grande.txt", "x" * 100)
        with patch.dict(os.environ, {"RYOKU_ATTACH_MAX_BYTES": "10"}):
            with self.assertRaises(AttachmentError) as ctx:
                extract_file(path)
        self.assertEqual(ctx.exception.code, "too_large")

    def test_truncation_flag(self):
        path = self._write("longo.txt", "a" * 500)
        with patch.dict(os.environ, {"RYOKU_ATTACH_MAX_CHARS": "50"}):
            item = extract_file(path)
        self.assertTrue(item.truncated)
        self.assertEqual(len(item.text), 50)
        self.assertIn("truncado", (item.warning or "").lower())

    def test_binary_nul_rejected(self):
        path = self._write("bin.txt", b"abc\x00def")
        with self.assertRaises(AttachmentError) as ctx:
            extract_file(path)
        self.assertEqual(ctx.exception.code, "binary_file")

    def test_json_and_csv(self):
        j = self._write("data.json", '{"ok": true, "n": 1}')
        c = self._write("rows.csv", "a,b\n1,2\n")
        items = extract_many([str(j), str(c)])
        self.assertEqual(len(items), 2)
        self.assertIn('"ok"', items[0].text)
        self.assertIn("a,b", items[1].text)

    def test_too_many_files(self):
        paths = [str(self._write(f"f{i}.txt", f"x{i}")) for i in range(3)]
        with patch.dict(os.environ, {"RYOKU_ATTACH_MAX_FILES": "2"}):
            with self.assertRaises(AttachmentError) as ctx:
                extract_many(paths)
        self.assertEqual(ctx.exception.code, "too_many")

    def test_relative_path_rejected(self):
        with self.assertRaises(AttachmentError) as ctx:
            extract_file("relativo.txt")
        self.assertEqual(ctx.exception.code, "path_not_absolute")

    def test_pdf_without_backend_clear_error(self):
        path = self._write("scan.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n")
        with patch.dict("sys.modules", {"pypdf": None}):
            with patch("ryoku_ai.attachments.shutil.which", return_value=None):
                with self.assertRaises(AttachmentError) as ctx:
                    extract_file(path)
        self.assertIn(ctx.exception.code, {"pdf_backend_missing", "pdf_error", "pdf_no_text"})

    def test_format_prompt_marks_untrusted(self):
        path = self._write("log.txt", "ERROR=42")
        item = extract_file(path)
        prompt = format_attachments_for_prompt([item], "explique o erro")
        self.assertIn("apenas como dados", prompt)
        self.assertIn("ERROR=42", prompt)
        self.assertIn("explique o erro", prompt)
        self.assertIn("Anexo: log.txt", prompt)

    def test_parse_request_stdin_json(self):
        prompt, paths = parse_request_stdin(
            json.dumps({"prompt": "leia", "attachments": [{"path": "/tmp/a.txt"}, "/tmp/b.md"]})
        )
        self.assertEqual(prompt, "leia")
        self.assertEqual(paths, ["/tmp/a.txt", "/tmp/b.md"])

    def test_parse_request_stdin_plain(self):
        prompt, paths = parse_request_stdin("só texto")
        self.assertEqual(prompt, "só texto")
        self.assertEqual(paths, [])

    def test_parse_request_requires_prompt(self):
        with self.assertRaises(AttachmentError) as ctx:
            parse_request_stdin(json.dumps({"attachments": []}))
        self.assertEqual(ctx.exception.code, "empty_prompt")


class AttachmentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db.sqlite3"
        self.store = HistoryStore(self.db)
        self.text_dir = Path(self.tmp.name) / "attachment-text"
        self.text_dir.mkdir()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_metadata_persisted_text_on_disk_profile_isolation(self):
        from ryoku_ai.attachments import ExtractedAttachment

        conv_a = self.store.create_conversation("p1", title="A")
        conv_b = self.store.create_conversation("p2", title="B")
        item = ExtractedAttachment(
            id="att-1",
            filename="nota.txt",
            path="/tmp/nota.txt",
            extension=".txt",
            size_bytes=12,
            mime_hint="text/plain",
            text="conteúdo secreto p1",
            truncated=False,
        )
        with patch("ryoku_ai.attachments.attachment_text_dir", return_value=self.text_dir):
            self.store.append_turn(
                conv_a.id,
                user_text="pergunte\n\n[anexos: nota.txt]",
                assistant_text="ok",
                profile_id="p1",
                attachments=[item],
            )
            stored = load_extracted_text("att-1")
            self.assertEqual(stored, "conteúdo secreto p1")

        msgs = self.store.list_messages(conv_a.id)
        self.assertIsNotNone(msgs[0].attachments)
        self.assertEqual(msgs[0].attachments[0]["filename"], "nota.txt")
        self.assertNotIn("conteúdo secreto", json.dumps(msgs[0].attachments))

        self.assertIsNone(self.store.get_conversation(conv_a.id, "p2"))
        self.assertEqual(self.store.list_messages(conv_b.id), [])

        with patch("ryoku_ai.attachments.attachment_text_dir", return_value=self.text_dir):
            window = build_context_window(msgs)
            self.assertIn("conteúdo secreto p1", window.messages[0]["content"])

            self.store.delete(conv_a.id, "p1")
            self.assertIsNone(load_extracted_text("att-1"))


class AttachmentCliTests(unittest.TestCase):
    def test_attach_inspect_json(self):
        from ryoku_ai.cli import main
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hello.txt"
            path.write_text("hello-ryoku", encoding="utf-8")
            payload = json.dumps({"paths": [str(path)]})
            out = io.StringIO()
            with patch("sys.stdin", io.StringIO(payload)):
                with contextlib.redirect_stdout(out):
                    code = main(["attach", "inspect", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["attachments"][0]["filename"], "hello.txt")
            self.assertEqual(data["attachments"][0]["path"], str(path))
            # Metadados públicos: só prévia curta, nunca o campo text completo.
            self.assertNotIn("text", data["attachments"][0])
            self.assertLessEqual(len(data["attachments"][0].get("preview", "")), 240)

    def test_attach_capabilities_and_image_inspect(self):
        from ryoku_ai.cli import main
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["attach", "capabilities", "--json"]), 0)
        caps = json.loads(out.getvalue())
        self.assertFalse(caps["vision_available"])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shot.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
            payload = json.dumps({"paths": [str(path)]})
            out2 = io.StringIO()
            with patch("sys.stdin", io.StringIO(payload)):
                with contextlib.redirect_stdout(out2):
                    self.assertEqual(main(["attach", "inspect", "--json"]), 0)
            data = json.loads(out2.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["attachments"][0]["kind"], "image")
            self.assertFalse(data["vision"]["vision_available"])

    def test_paste_image_writes_once(self):
        from ryoku_ai.cli import main
        import contextlib
        import io

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        with tempfile.TemporaryDirectory() as directory:
            text_dir = Path(directory) / "clipboard-images"
            text_dir.mkdir()
            with patch("ryoku_ai.attachments.clipboard_image_dir", return_value=text_dir):
                with patch("ryoku_ai.attachments.shutil.which", side_effect=lambda n: "/bin/wl-paste" if n == "wl-paste" else None):
                    with patch(
                        "ryoku_ai.attachments.subprocess.run",
                        return_value=MagicMock(returncode=0, stdout=png, stderr=b""),
                    ):
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            code = main(["attach", "paste-image", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["attachments"][0]["kind"], "image")
            self.assertFalse(data["vision"]["vision_available"])
            self.assertTrue(Path(data["attachments"][0]["path"]).is_file())


class AttachmentChatContextTests(unittest.TestCase):
    def test_run_turn_sends_extracted_text_to_model(self):
        from ryoku_ai.attachments import ExtractedAttachment
        from ryoku_ai.chat import run_turn

        bridge = MagicMock()
        captured: list[list] = []

        def fake_stream(*, model, input, on_delta):
            captured.append(input)
            on_delta("resposta")
            return "resposta"

        bridge.chat_stream.side_effect = fake_stream
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            text_dir = Path(directory) / "attachment-text"
            text_dir.mkdir()
            store = HistoryStore(db)
            conv = store.create_conversation("p1")
            item = ExtractedAttachment(
                id="att-ctx",
                filename="segredo.txt",
                path="/tmp/segredo.txt",
                extension=".txt",
                size_bytes=20,
                mime_hint="text/plain",
                text="TOKEN_EXCLUSIVO_XYZ_991",
                truncated=False,
            )
            with patch("ryoku_ai.attachments.attachment_text_dir", return_value=text_dir):
                run_turn(
                    bridge,
                    store,
                    conversation_id=conv.id,
                    profile_id="p1",
                    model="gpt-test",
                    user_text="o que tem no arquivo?",
                    attachments=[item],
                )
            store.close()
        self.assertEqual(len(captured), 1)
        last_user = captured[0][-1]["content"]
        self.assertIn("TOKEN_EXCLUSIVO_XYZ_991", last_user)
        self.assertIn("o que tem no arquivo?", last_user)
        self.assertIn("apenas como dados", last_user)


if __name__ == "__main__":
    unittest.main()
