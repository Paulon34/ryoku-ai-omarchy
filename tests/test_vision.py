import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ryoku_ai.attachments import AttachmentError, prepare_attachments
from ryoku_ai.chat import run_chat_repl, run_vision_turn
from ryoku_ai.cli import main
from ryoku_ai.history import HistoryStore
from ryoku_ai.vision import VisionError, VisionResult, analyze_with_ollama, vision_capabilities


PNG_MIN = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class VisionCapabilitiesTests(unittest.TestCase):
    def test_default_unavailable_siwc_text_only(self):
        with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": ""}, clear=False):
            with patch("ryoku_ai.vision.shutil.which", return_value=None):
                caps = vision_capabilities()
        self.assertFalse(caps["vision_available"])
        self.assertTrue(caps["siwc_text_only"])
        self.assertFalse(caps["siwc_supports_images"])
        self.assertTrue(caps["no_auto_download"])
        self.assertTrue(caps["no_siwc_token_reuse"])

    def test_opt_in_without_ollama(self):
        with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": "ollama"}, clear=False):
            with patch("ryoku_ai.vision.shutil.which", return_value="/usr/bin/ollama"):
                with patch(
                    "ryoku_ai.vision._http_json",
                    side_effect=VisionError("ollama_unreachable", "down"),
                ):
                    caps = vision_capabilities()
        self.assertTrue(caps["opt_in_set"])
        self.assertFalse(caps["vision_available"])
        self.assertIn("Ollama", caps["message"])


class PrepareAttachmentsTests(unittest.TestCase):
    def test_image_rejected_without_backend_before_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "err.png"
            path.write_bytes(PNG_MIN)
            with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": ""}, clear=False):
                with self.assertRaises(AttachmentError) as ctx:
                    prepare_attachments([str(path)])
            self.assertEqual(ctx.exception.code, "vision_unavailable")

    def test_image_accepted_when_vision_available(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ok.png"
            path.write_bytes(PNG_MIN)
            fake = {
                "vision_available": True,
                "message": "ok",
            }
            with patch("ryoku_ai.attachments.vision_status", return_value=fake):
                docs, images = prepare_attachments([str(path)])
            self.assertEqual(docs, [])
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0].filename, "ok.png")
            self.assertEqual(images[0].text, "")


class OllamaAnalyzeTests(unittest.TestCase):
    def test_analyze_sends_real_base64_not_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret-code.png"
            path.write_bytes(PNG_MIN + b"UNIQUE_BYTES_991")
            caps = {
                "opt_in_set": True,
                "vision_available": True,
                "message": "ok",
            }
            captured: dict = {}

            def fake_http(url, payload=None, timeout=8.0):
                captured["url"] = url
                captured["payload"] = payload
                return {"model": "llava:7b", "message": {"content": "vejo UNIQUE na imagem"}}

            with patch("ryoku_ai.vision.vision_capabilities", return_value=caps):
                with patch("ryoku_ai.vision._http_json", side_effect=fake_http):
                    result = analyze_with_ollama([path], "o que há de único?")
            self.assertEqual(result.backend, "ollama")
            self.assertIn("UNIQUE", result.text)
            images = captured["payload"]["messages"][0]["images"]
            self.assertEqual(len(images), 1)
            # base64 real, não o nome do arquivo
            self.assertNotIn("secret-code", images[0])
            self.assertGreater(len(images[0]), 40)


class VisionTurnHistoryTests(unittest.TestCase):
    def test_run_vision_turn_labels_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            img = Path(directory) / "a.png"
            img.write_bytes(PNG_MIN)
            store = HistoryStore(db)
            conv = store.create_conversation("p1")
            from ryoku_ai.attachments import ExtractedAttachment

            image = ExtractedAttachment(
                id="i1",
                filename="a.png",
                path=str(img),
                extension=".png",
                size_bytes=img.stat().st_size,
                mime_hint="image/png",
                text="",
                truncated=False,
            )
            with patch(
                "ryoku_ai.chat.analyze_images",
                return_value=VisionResult(text="código XYZ-ONLY-IMG", backend="ollama", model="llava:7b"),
            ):
                text = run_vision_turn(
                    store,
                    conversation_id=conv.id,
                    profile_id="p1",
                    user_text="o que diz o print?",
                    documents=[],
                    images=[image],
                    jsonl=False,
                )
            self.assertIn("[visão: ollama/llava:7b]", text)
            self.assertIn("XYZ-ONLY-IMG", text)
            msgs = store.list_messages(conv.id)
            self.assertEqual(msgs[-1].content, text)
            store.close()


class ChatEarlyFailureTests(unittest.TestCase):
    def test_image_failure_does_not_keep_empty_conversation(self):
        bridge = MagicMock()
        bridge.request.side_effect = [
            {"status": "connected", "sharing": True, "profileId": "p1"},
            [{"slug": "gpt-test", "displayName": "t"}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            img = Path(directory) / "shot.png"
            img.write_bytes(PNG_MIN)
            with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": ""}, clear=False):
                code = run_chat_repl(
                    bridge,
                    one_shot="explique",
                    attachment_paths=[str(img)],
                    create_new=True,
                    jsonl=True,
                    history_path=db,
                    write=lambda _t: None,
                )
            self.assertEqual(code, 1)
            store = HistoryStore(db)
            self.assertEqual(store.list_conversations("p1"), [])
            store.close()


class VisionCliAndPanelTests(unittest.TestCase):
    def test_cli_vision_capabilities(self):
        out = io.StringIO()
        with patch(
            "ryoku_ai.cli.vision_capabilities",
            return_value={"vision_available": False, "siwc_text_only": True},
        ):
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["vision", "capabilities", "--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertFalse(data["vision_available"])

    def test_panel_restores_on_error_contract(self):
        root = Path(__file__).resolve().parents[1]
        panel = (root / "plugins/io.github.paulon34.ryoku-ai/Panel.qml").read_text(encoding="utf-8")
        self.assertIn("abortFailedSend", panel)
        self.assertIn("sendSnapshot", panel)
        self.assertIn("pendingAttachments = snap.attachments", panel)
        self.assertIn('event === "error"', panel)


if __name__ == "__main__":
    unittest.main()
