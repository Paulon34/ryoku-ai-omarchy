import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ryoku_ai.diagnostics import TOOLS, collect, os_release, pretty


class DiagnosticsTests(unittest.TestCase):
    def test_os_release_allows_known_fields_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text('ID=arch\nID_LIKE="arch linux"\nSECRET=private\n', encoding="utf-8")
            data = os_release(path)
            self.assertEqual(data["ID"], "arch")
            self.assertNotIn("SECRET", data)

    def test_missing_release(self):
        self.assertEqual(os_release(Path("/this-file-does-not-exist")), {})

    @patch("ryoku_ai.diagnostics.platform.system", return_value="Linux")
    @patch("ryoku_ai.diagnostics.shutil.which", side_effect=lambda tool: "/usr/bin/omarchy" if tool == "omarchy" else None)
    @patch("ryoku_ai.diagnostics.os_release", return_value={"ID": "manjaro", "ID_LIKE": "arch"})
    def test_report_does_not_expose_identifiers(self, _release, _which, _system):
        value = collect()
        self.assertTrue(value["arch_family"])
        self.assertTrue(value["omarchy_cli"])
        self.assertEqual(set(value["tools"]), set(TOOLS))
        for forbidden in ("hostname", "serial", "token", "email", "ip_address"):
            self.assertNotIn(forbidden, str(value).lower())
        self.assertIn("somente leitura", pretty(value))


if __name__ == "__main__":
    unittest.main()
