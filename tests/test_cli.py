import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ryoku_ai.cli import main
from ryoku_ai.history import HistoryStore


class CLITests(unittest.TestCase):
    def test_welcome(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        text = stream.getvalue()
        self.assertIn("RYOKU AI", text)
        self.assertIn("history", text)
        self.assertIn("dictation", text)

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

    def test_history_delete_requires_confirmation(self):
        bridge = MagicMock()
        bridge.__enter__.return_value = bridge
        bridge.__exit__.return_value = None
        bridge.request.return_value = {
            "status": "connected",
            "sharing": True,
            "profileId": "p1",
        }
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            store = HistoryStore(db)
            conv = store.create_conversation("p1", title="t")
            store.close()
            out = io.StringIO()
            with patch("ryoku_ai.cli.bridge_ready", return_value=(True, "ok")):
                with patch("ryoku_ai.cli._bridge", return_value=bridge):
                    with patch("ryoku_ai.cli._confirm", return_value=False):
                        with contextlib.redirect_stdout(out):
                            code = main(
                                [
                                    "history",
                                    "delete",
                                    conv.id,
                                    "--history-db",
                                    str(db),
                                ]
                            )
            self.assertEqual(code, 1)
            self.assertIn("Cancelado", out.getvalue())
            store = HistoryStore(db)
            self.assertEqual(len(store.list_conversations("p1")), 1)
            store.close()

    def test_history_rename_stdin_persists_and_validates(self):
        bridge = MagicMock()
        bridge.__enter__.return_value = bridge
        bridge.__exit__.return_value = None
        bridge.request.return_value = {
            "status": "connected",
            "sharing": True,
            "profileId": "p1",
        }
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            store = HistoryStore(db)
            conv = store.create_conversation("p1", title="Antigo")
            store.close()

            args = ["history", "rename", conv.id, "--title-stdin", "--history-db", str(db)]
            with patch("ryoku_ai.cli.bridge_ready", return_value=(True, "ok")):
                with patch("ryoku_ai.cli._bridge", return_value=bridge):
                    with patch("sys.stdin", io.StringIO("Meu título novo\n")):
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(main(args), 0)
                    # Não aceita um título vazio, nem dois métodos ao mesmo tempo.
                    with patch("sys.stdin", io.StringIO("  \n")):
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(main(args), 3)
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(
                            main(["history", "rename", conv.id, "X", "--title-stdin",
                                  "--history-db", str(db)]),
                            2,
                        )
            store = HistoryStore(db)
            self.assertEqual(store.get_conversation(conv.id, "p1").title, "Meu título novo")
            self.assertIsNone(store.get_conversation(conv.id, "other-profile"))
            store.close()

    def test_history_list_json(self):
        bridge = MagicMock()
        bridge.__enter__.return_value = bridge
        bridge.__exit__.return_value = None
        bridge.request.return_value = {
            "status": "connected",
            "sharing": True,
            "profileId": "p1",
        }
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite3"
            store = HistoryStore(db)
            store.create_conversation("p1", title="Alpha")
            store.close()
            out = io.StringIO()
            with patch("ryoku_ai.cli.bridge_ready", return_value=(True, "ok")):
                with patch("ryoku_ai.cli._bridge", return_value=bridge):
                    with contextlib.redirect_stdout(out):
                        self.assertEqual(
                            main(["history", "list", "--json", "--history-db", str(db)]),
                            0,
                        )
            data = json.loads(out.getvalue())
            self.assertEqual(data[0]["title"], "Alpha")

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


class PluginContractTests(unittest.TestCase):
    def test_manifest_and_entrypoints_exist(self):
        root = Path(__file__).resolve().parents[1]
        plugin = root / "plugins" / "io.github.paulon34.ryoku-ai"
        manifest = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "io.github.paulon34.ryoku-ai")
        self.assertEqual(manifest["kinds"], ["bar-widget"])
        self.assertEqual(manifest["entryPoints"]["barWidget"], "BarWidget.qml")
        self.assertTrue((plugin / "BarWidget.qml").is_file())
        self.assertTrue((plugin / "Panel.qml").is_file())
        self.assertTrue((plugin / "Theme.qml").is_file())
        panel = (plugin / "Panel.qml").read_text(encoding="utf-8")
        theme = (plugin / "Theme.qml").read_text(encoding="utf-8")
        self.assertIn("stdinEnabled: true", panel)
        self.assertIn("--request-stdin", panel)
        self.assertIn("FileDialog", panel)
        self.assertIn("pendingAttachments", panel)
        self.assertIn("paste-image", panel)
        self.assertIn("visionUnavailable", panel)
        self.assertIn("startDictation", panel)
        self.assertIn("dictationBusy", panel)
        self.assertIn("textFormat: Text.PlainText", panel)
        self.assertIn("panel.emptyBrand", panel)
        self.assertIn("panel.emptyHeadline", panel)
        self.assertIn("#09090B", theme)
        self.assertIn("#D4AF67", theme)
        self.assertIn("#A83B42", theme)
        self.assertIn("divider", theme)
        self.assertNotIn("access_token", panel.lower())
        self.assertNotIn("refresh_token", panel.lower())
        # Empty-state copy must wrap and not live as a clipped single-line ListView child.
        self.assertIn("wrapMode: Text.WordWrap", panel)
        self.assertIn("id: emptyState", panel)
        # Layout minimalista: superfície única + divisórias (não cards empilhados).
        self.assertIn("theme.divider", panel)
        self.assertIn("radiusNone", theme)


    def test_i18n_empty_state_keys(self):
        root = Path(__file__).resolve().parents[1]
        i18n = root / "plugins" / "io.github.paulon34.ryoku-ai" / "i18n"
        for name in ("en.json", "pt-BR.json"):
            data = json.loads((i18n / name).read_text(encoding="utf-8"))
            for key in (
                "panel.emptyBrand",
                "panel.emptyHeadline",
                "panel.emptySubtext",
                "panel.rename",
                "panel.send",
                "panel.attach",
                "panel.attachRemove",
                "panel.attachLimit",
                "panel.visionUnavailable",
                "panel.attachFilterImages",
                "panel.dictationStart",
                "panel.dictationStop",
                "panel.dictationCancel",
            ):
                self.assertIn(key, data)
                self.assertTrue(str(data[key]).strip())



if __name__ == "__main__":
    unittest.main()
