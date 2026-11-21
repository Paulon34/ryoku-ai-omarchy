import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from ryoku_ai.cli import main


class CLITests(unittest.TestCase):
    def test_welcome(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        text = stream.getvalue()
        self.assertIn("RYOKU AI", text)
        self.assertIn("login", text)

    def test_status_without_bridge(self):
        stream = io.StringIO()
        with patch("ryoku_ai.cli.bridge_ready", return_value=(False, "sem node")):
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(["status"]), 0)
        self.assertIn("indisponível", stream.getvalue())
        self.assertIn("PASS_REAL", stream.getvalue())

    def test_chat_without_bridge_never_fakes_login(self):
        stream = io.StringIO()
        with patch("ryoku_ai.cli.bridge_ready", return_value=(False, "sem bridge")):
            with contextlib.redirect_stderr(stream):
                self.assertEqual(main(["chat"]), 3)
        self.assertIn("bridge SIWC", stream.getvalue())

    def test_login_reports_sharing(self):
        bridge = MagicMock()
        bridge.__enter__.return_value = bridge
        bridge.__exit__.return_value = None
        bridge.request.return_value = {
            "status": "connected",
            "sharing": True,
            "profileLabel": "Connection 1",
            "identity": {"name": "Test", "email": "t@example.com"},
        }
        out = io.StringIO()
        err = io.StringIO()
        with patch("ryoku_ai.cli.bridge_ready", return_value=(True, "ok")):
            with patch("ryoku_ai.cli._bridge", return_value=bridge):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(main(["login"]), 0)
        self.assertIn("session.sharing", out.getvalue())
        self.assertIn("Consentimento de uso do plano ativo", out.getvalue())
        # Never print tokens
        self.assertNotIn("access_token", out.getvalue().lower())
        self.assertNotIn("refresh", out.getvalue().lower())

    def test_models_requires_sharing(self):
        bridge = MagicMock()
        bridge.__enter__.return_value = bridge
        bridge.__exit__.return_value = None
        bridge.request.return_value = {"status": "connected", "sharing": False}
        err = io.StringIO()
        with patch("ryoku_ai.cli.bridge_ready", return_value=(True, "ok")):
            with patch("ryoku_ai.cli._bridge", return_value=bridge):
                with contextlib.redirect_stderr(err):
                    self.assertEqual(main(["models"]), 3)
        self.assertIn("session.sharing", err.getvalue())

    @patch(
        "ryoku_ai.cli.collect",
        return_value={
            "platform": "Linux",
            "distribution": "arch",
            "tools": {},
            "arch_family": True,
            "omarchy_cli": True,
            "chatgpt_connection": "bridge_ready",
            "siwc_bridge_ready": True,
            "siwc_bridge_detail": "ok",
        },
    )
    def test_doctor_json(self, _collect):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["doctor", "--json"]), 0)
        self.assertTrue(json.loads(stream.getvalue())["arch_family"])


if __name__ == "__main__":
    unittest.main()
