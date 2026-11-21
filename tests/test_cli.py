import contextlib
import io
import json
import unittest
from unittest.mock import patch

from ryoku_ai.cli import main


class CLITests(unittest.TestCase):
    def test_welcome(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        self.assertIn("RYOKU AI", stream.getvalue())

    def test_status_marks_pending(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["status"]), 0)
        self.assertIn("ainda não implementados", stream.getvalue())

    def test_chat_never_fakes_login(self):
        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            self.assertEqual(main(["chat"]), 3)
        self.assertIn("não está conectado", stream.getvalue())

    @patch("ryoku_ai.cli.collect", return_value={"platform": "Linux", "distribution": "arch", "tools": {}, "arch_family": True, "omarchy_cli": True, "chatgpt_connection": "not_implemented"})
    def test_doctor_json(self, _collect):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["doctor", "--json"]), 0)
        self.assertTrue(json.loads(stream.getvalue())["arch_family"])


if __name__ == "__main__":
    unittest.main()
