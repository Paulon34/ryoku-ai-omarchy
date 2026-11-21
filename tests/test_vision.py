import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ryoku_ai.attachments import AttachmentError, prepare_attachments
from ryoku_ai.chat import run_chat_repl, run_vision_turn
from ryoku_ai.cli import main
from ryoku_ai.history import HistoryStore
from ryoku_ai.vision import (
    VisionError,
    VisionResult,
    analyze_with_ollama,
    load_vision_settings,
    vision_capabilities,
    write_example_config,
)


PNG_MIN = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _clear_vision_env():
    return patch.dict(
        "os.environ",
        {
            "RYOKU_VISION_BACKEND": "",
            "RYOKU_VISION_MODEL": "",
            "RYOKU_OLLAMA_HOST": "",
            "RYOKU_VISION_ALLOW_REMOTE": "",
        },
        clear=False,
    )


class VisionConfigFileTests(unittest.TestCase):
    def test_file_enables_without_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            path.write_text(
                'backend = "ollama"\nmodel = "moondream:1.8b"\nhost = "http://127.0.0.1:11434"\n',
                encoding="utf-8",
            )
            env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("RYOKU_VISION") and k != "RYOKU_OLLAMA_HOST"
            }
            with patch.dict("os.environ", env, clear=True):
                settings = load_vision_settings(config_path=path)
            self.assertTrue(settings.enabled)
            self.assertEqual(settings.backend, "ollama")
            self.assertEqual(settings.model, "moondream:1.8b")
            self.assertEqual(settings.source, "file")

    def test_env_overrides_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            path.write_text(
                'backend = "ollama"\nmodel = "moondream:1.8b"\nhost = "http://127.0.0.1:11434"\n',
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {
                    "RYOKU_VISION_BACKEND": "ollama",
                    "RYOKU_VISION_MODEL": "llava:7b",
                    "RYOKU_OLLAMA_HOST": "http://127.0.0.1:11434",
                },
                clear=False,
            ):
                settings = load_vision_settings(config_path=path)
            self.assertEqual(settings.model, "llava:7b")
            self.assertEqual(settings.source, "env")

    def test_empty_env_disables_even_with_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            path.write_text('backend = "ollama"\n', encoding="utf-8")
            with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": ""}, clear=False):
                settings = load_vision_settings(config_path=path)
            self.assertFalse(settings.enabled)
            self.assertIsNone(settings.backend)

    def test_remote_host_denied_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            path.write_text(
                'backend = "ollama"\nhost = "http://evil.example:11434"\n',
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"RYOKU_VISION_BACKEND": ""}, clear=False):
                # empty env backend disables before host from file… force file-only:
                pass
            env = {k: v for k, v in os.environ.items() if k not in {"RYOKU_VISION_BACKEND", "RYOKU_OLLAMA_HOST"}}
            with patch.dict("os.environ", env, clear=True):
                with self.assertRaises(VisionError) as ctx:
                    load_vision_settings(config_path=path)
            self.assertEqual(ctx.exception.code, "remote_host_denied")

    def test_init_config_writes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ryoku-ai" / "vision.toml"
            written = write_example_config(path)
            self.assertEqual(written, path)
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertIn('backend = "ollama"', text)
            self.assertIn("moondream:1.8b", text)


class VisionCapabilitiesTests(unittest.TestCase):
    def test_default_unavailable_siwc_text_only(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.toml"
            with _clear_vision_env():
                with patch("ryoku_ai.vision.default_config_path", return_value=missing):
                    with patch("ryoku_ai.vision.shutil.which", return_value=None):
                        caps = vision_capabilities()
        self.assertFalse(caps["vision_available"])
        self.assertTrue(caps["siwc_text_only"])
        self.assertFalse(caps["siwc_supports_images"])
        self.assertTrue(caps["no_auto_download"])
        self.assertTrue(caps["no_siwc_token_reuse"])
        self.assertIn("vision.toml", caps["message"])

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

    def test_capabilities_from_file_without_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            path.write_text(
                'backend = "ollama"\nmodel = "moondream:1.8b"\nhost = "http://127.0.0.1:11434"\n',
                encoding="utf-8",
            )
            env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("RYOKU_VISION") and k != "RYOKU_OLLAMA_HOST"
            }
            with patch.dict("os.environ", env, clear=True):
                with patch("ryoku_ai.vision.default_config_path", return_value=path):
                    with patch(
                        "ryoku_ai.vision.probe_ollama",
                        return_value={
                            "reachable": True,
                            "model_installed": True,
                            "configured_model": "moondream:1.8b",
                            "host": "http://127.0.0.1:11434",
                        },
                    ):
                        caps = vision_capabilities()
            self.assertTrue(caps["vision_available"])
            self.assertEqual(caps["config"]["source"], "file")
            self.assertEqual(caps["config"]["model"], "moondream:1.8b")


class PrepareAttachmentsTests(unittest.TestCase):
    def test_image_rejected_without_backend_before_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "err.png"
            path.write_bytes(PNG_MIN)
            missing = Path(directory) / "no-vision.toml"
            with _clear_vision_env():
                with patch("ryoku_ai.vision.default_config_path", return_value=missing):
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

            from ryoku_ai.vision import VisionSettings

            settings = VisionSettings(
                backend="ollama",
                model="llava:7b",
                host="http://127.0.0.1:11434",
                allow_remote=False,
                source="env",
                config_path=None,
                enabled=True,
            )
            with patch("ryoku_ai.vision.vision_capabilities", return_value=caps):
                with patch("ryoku_ai.vision.load_vision_settings", return_value=settings):
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
            missing = Path(directory) / "no.toml"
            with _clear_vision_env():
                with patch("ryoku_ai.vision.default_config_path", return_value=missing):
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

    def test_cli_init_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vision.toml"
            with patch("ryoku_ai.cli.write_example_config", return_value=path) as writer:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(["vision", "init-config"]), 0)
            writer.assert_called_once()
            self.assertIn(str(path), out.getvalue())

    def test_panel_restores_on_error_contract(self):
        root = Path(__file__).resolve().parents[1]
        panel = (root / "plugins/io.github.paulon34.ryoku-ai/Panel.qml").read_text(encoding="utf-8")
        self.assertIn("abortFailedSend", panel)
        self.assertIn("sendSnapshot", panel)
        self.assertIn("pendingAttachments = snap.attachments", panel)
        self.assertIn('event === "error"', panel)


if __name__ == "__main__":
    unittest.main()
