import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ryoku_ai.chat import pick_model, run_chat_repl, run_turn
from ryoku_ai.history import HistoryStore
from ryoku_ai.siwc import BridgePaths, SiwcBridge, SiwcError, format_session


class FormatSessionTests(unittest.TestCase):
    def test_distinguishes_identity_from_sharing(self):
        lines = format_session(
            {
                "status": "connected",
                "sharing": False,
                "profileLabel": "Connection 1",
                "identity": {"name": "Ada", "email": "ada@example.com"},
            }
        )
        text = "\n".join(lines)
        self.assertIn("session.sharing): não", text)
        self.assertIn("reconsent", text)
        self.assertNotIn("token", text.lower())


class PickModelTests(unittest.TestCase):
    def test_default_first(self):
        bridge = MagicMock()
        bridge.request.return_value = [
            {"slug": "gpt-test", "displayName": "Test"},
            {"slug": "gpt-other", "displayName": "Other"},
        ]
        self.assertEqual(pick_model(bridge, None), "gpt-test")

    def test_unknown(self):
        bridge = MagicMock()
        bridge.request.return_value = [{"slug": "gpt-test", "displayName": "Test"}]
        with self.assertRaises(SiwcError):
            pick_model(bridge, "missing")


class ChatReplTests(unittest.TestCase):
    def test_requires_sharing(self):
        bridge = MagicMock()
        bridge.request.return_value = {"status": "connected", "sharing": False, "profileId": "p"}
        chunks: list[str] = []
        code = run_chat_repl(bridge, write=chunks.append, read_line=lambda: "")
        self.assertEqual(code, 3)
        self.assertTrue(any("session.sharing" in part or "consentimento" in part for part in chunks))

    def test_one_shot_streams_and_persists(self):
        bridge = MagicMock()

        def request(op, args=None):
            if op == "session":
                return {"status": "connected", "sharing": True, "profileId": "profile-1"}
            if op == "models":
                return [{"slug": "gpt-test", "displayName": "Test"}]
            raise AssertionError(op)

        bridge.request.side_effect = request

        def chat_stream(*, model, message=None, input=None, instructions=None, on_delta=None):
            self.assertEqual(model, "gpt-test")
            payload = input if input is not None else message
            self.assertIsInstance(payload, list)
            self.assertEqual(payload[-1]["content"], "oi")
            if on_delta:
                on_delta("ola")
            return "ola"

        bridge.chat_stream.side_effect = chat_stream
        chunks: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "c.sqlite3"
            code = run_chat_repl(
                bridge,
                one_shot="oi",
                write=chunks.append,
                history_path=db,
                create_new=True,
            )
            self.assertEqual(code, 0)
            self.assertIn("ola", "".join(chunks))
            store = HistoryStore(db)
            convs = store.list_conversations("profile-1")
            self.assertEqual(len(convs), 1)
            msgs = store.list_messages(convs[0].id)
            self.assertEqual(msgs[0].content, "oi")
            self.assertEqual(msgs[1].content, "ola")
            store.close()

    def test_run_turn_forwards_prior_context(self):
        bridge = MagicMock()
        seen = {}

        def chat_stream(*, model, message=None, input=None, instructions=None, on_delta=None):
            seen["input"] = input
            if on_delta:
                on_delta("next")
            return "next"

        bridge.chat_stream.side_effect = chat_stream
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "db.sqlite3")
            conv = store.create_conversation("p")
            store.append_turn(conv.id, user_text="antes", assistant_text="resposta")
            run_turn(
                bridge,
                store,
                conversation_id=conv.id,
                profile_id="p",
                model="m",
                user_text="depois",
            )
            self.assertEqual(seen["input"][0]["content"], "antes")
            self.assertEqual(seen["input"][-1]["content"], "depois")
            store.close()


class BridgeProtocolTests(unittest.TestCase):
    def test_discover_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SiwcError):
                BridgePaths.discover(Path(directory) / "nowhere.py")

    def test_request_maps_errors(self):
        bridge = SiwcBridge.__new__(SiwcBridge)
        bridge.paths = MagicMock()
        bridge.storage_dir = Path("/tmp")
        bridge.test_memory_crypto = True
        bridge._extra_env = {}
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.stdout.readline.return_value = json.dumps(
            {"ok": False, "error": {"code": "sharing_not_enabled", "message": "no", "retryable": False}}
        ) + "\n"
        bridge._proc = proc
        with patch.object(bridge, "_ensure", return_value=proc):
            with self.assertRaises(SiwcError) as ctx:
                bridge.request("models")
        self.assertEqual(ctx.exception.code, "sharing_not_enabled")


if __name__ == "__main__":
    unittest.main()
