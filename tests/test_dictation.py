import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from ryoku_ai.cli import main
from ryoku_ai.dictation import DictationError, cancel, capabilities, start, status, stop


class DictationUnitTests(unittest.TestCase):
    def test_capabilities_superwhisper_cancel_and_no_partial(self):
        status_payload = {
            "ready": True,
            "phase": "idle",
            "workers": {"asr_backend": "cloud", "asr": {"backend": "cloud"}},
        }
        models_payload = {
            "credentials": {"source": "free-tier"},
            "license": {"state": "unlicensed"},
            "models": [{"id": "transcription", "download": {"state": "missing"}}],
        }
        with patch("ryoku_ai.dictation._which", side_effect=lambda n: f"/bin/{n}"):
            with patch("ryoku_ai.dictation.selected_backend", return_value="superwhisper"):
                with patch(
                    "ryoku_ai.dictation._run",
                    side_effect=[
                        MagicMock(returncode=0, stdout=json.dumps(status_payload), stderr=""),
                        MagicMock(returncode=0, stdout=json.dumps(models_payload), stderr=""),
                    ],
                ):
                    caps = capabilities()
        self.assertTrue(caps["cancel"]["available"])
        self.assertEqual(caps["cancel"]["argv"], ["superwhisper", "cancel"])
        self.assertFalse(caps["partial_transcript"])
        self.assertTrue(caps["processing"]["cloud"])
        self.assertTrue(caps["siwc_not_used"])
        blob = json.dumps(caps)
        self.assertNotIn('"last"', blob)
        self.assertNotIn(".wav", blob.lower())
        self.assertNotIn("SEGRedo", blob)

    def test_cancel_unavailable_for_unknown_backend(self):
        with patch("ryoku_ai.dictation.capabilities", return_value={"cancel": {"available": False, "note": "nope"}}):
            with self.assertRaises(DictationError) as ctx:
                cancel()
        self.assertEqual(ctx.exception.code, "cancel_unavailable")

    def test_cancel_calls_superwhisper(self):
        with patch(
            "ryoku_ai.dictation.capabilities",
            return_value={"cancel": {"available": True, "argv": ["superwhisper", "cancel"]}},
        ):
            with patch(
                "ryoku_ai.dictation._run",
                return_value=MagicMock(
                    returncode=0,
                    stdout=json.dumps({"ok": True, "cancelled": True, "phase": "idle"}),
                    stderr="",
                ),
            ) as run:
                payload = cancel()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "cancel")
        run.assert_called_once()
        self.assertEqual(run.call_args[0][0], ["superwhisper", "cancel"])

    def test_start_stop_use_omarchy(self):
        with patch("ryoku_ai.dictation._which", side_effect=lambda n: "/usr/bin/omarchy" if n == "omarchy" else None):
            with patch(
                "ryoku_ai.dictation._run",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as run:
                self.assertEqual(start()["action"], "start")
                self.assertEqual(stop()["action"], "stop")
        self.assertEqual(run.call_args_list[0][0][0], ["omarchy", "dictation", "start"])
        self.assertEqual(run.call_args_list[1][0][0], ["omarchy", "dictation", "stop"])

    def test_status_sanitized(self):
        raw = {
            "ready": True,
            "phase": "recording",
            "recording_seconds": 3,
            "last": {"text": "SEGredo que não deve vazar"},
            "workers": {"asr_backend": "cloud", "asr": {"backend": "cloud"}},
        }
        with patch("ryoku_ai.dictation.capabilities", return_value={"backend": "superwhisper", "cancel": {}, "processing": {}}):
            with patch("ryoku_ai.dictation._which", return_value="/bin/superwhisper"):
                with patch(
                    "ryoku_ai.dictation._run",
                    return_value=MagicMock(returncode=0, stdout=json.dumps(raw), stderr=""),
                ):
                    st = status()
        self.assertTrue(st["recording"])
        self.assertNotIn("SEGRedo", json.dumps(st))
        self.assertFalse(st["partial_transcript"])


class DictationCliTests(unittest.TestCase):
    def test_cli_capabilities_json(self):
        fake = {
            "ok": True,
            "backend": "superwhisper",
            "partial_transcript": False,
            "cancel": {"available": True},
            "processing": {"cloud": True},
            "siwc_not_used": True,
        }
        out = io.StringIO()
        with patch("ryoku_ai.cli.dictation_capabilities", return_value=fake):
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["dictation", "capabilities", "--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["backend"], "superwhisper")
        self.assertFalse(data["partial_transcript"])

    def test_cli_cancel_error_json(self):
        out = io.StringIO()
        with patch(
            "ryoku_ai.cli.dictation_cancel",
            side_effect=DictationError("cancel_unavailable", "sem cancel"),
        ):
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["dictation", "cancel", "--json"]), 1)
        data = json.loads(out.getvalue())
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "cancel_unavailable")


class DictationPluginContractTests(unittest.TestCase):
    def test_panel_has_dictation_controls(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        panel = (root / "plugins/io.github.paulon34.ryoku-ai/Panel.qml").read_text(encoding="utf-8")
        self.assertIn("dictation", panel)
        self.assertIn("startDictation", panel)
        self.assertIn("stopDictation", panel)
        self.assertIn("cancelDictation", panel)
        self.assertIn("dictationBusy", panel)
        self.assertNotIn("access_token", panel.lower())
        for name in ("en.json", "pt-BR.json"):
            data = json.loads(
                (root / "plugins/io.github.paulon34.ryoku-ai/i18n" / name).read_text(encoding="utf-8")
            )
            for key in (
                "panel.dictationStart",
                "panel.dictationStop",
                "panel.dictationCancel",
                "panel.dictationCloudWarn",
                "panel.dictationRecording",
            ):
                self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
