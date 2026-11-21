import tempfile
import unittest
from pathlib import Path

from ryoku_ai.history import HistoryStore, build_context_window


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "conversations.sqlite3"
        self.store = HistoryStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_persists_across_reopen(self):
        conv = self.store.create_conversation("profile-a", title="Olá")
        self.store.append_turn(conv.id, user_text="oi", assistant_text="olá")
        self.store.close()
        again = HistoryStore(self.db)
        listed = again.list_conversations("profile-a")
        self.assertEqual(len(listed), 1)
        msgs = again.list_messages(listed[0].id)
        self.assertEqual([m.role for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[0].content, "oi")
        again.close()

    def test_profile_isolation(self):
        a = self.store.create_conversation("p1", title="A")
        b = self.store.create_conversation("p2", title="B")
        self.store.append_turn(a.id, user_text="a", assistant_text="ra")
        self.store.append_turn(b.id, user_text="b", assistant_text="rb")
        self.assertEqual(len(self.store.list_conversations("p1")), 1)
        self.assertEqual(len(self.store.list_conversations("p2")), 1)
        self.assertIsNone(self.store.get_conversation(a.id, "p2"))

    def test_error_does_not_clear_prior(self):
        conv = self.store.create_conversation("p1")
        self.store.append_turn(conv.id, user_text="1", assistant_text="r1")
        before = self.store.list_messages(conv.id)
        # Simula turno parcial sem apagar anteriores
        self.store.append_turn(
            conv.id, user_text="2", assistant_text="parcial", status="partial"
        )
        after = self.store.list_messages(conv.id)
        self.assertEqual(after[0].content, before[0].content)
        self.assertEqual(after[-1].status, "partial")

    def test_delete_requires_explicit_call(self):
        conv = self.store.create_conversation("p1")
        self.store.append_turn(conv.id, user_text="x", assistant_text="y")
        self.assertEqual(len(self.store.list_conversations("p1")), 1)
        self.store.delete(conv.id, "p1")
        self.assertEqual(self.store.list_conversations("p1"), [])

    def test_no_auto_clear_on_new_conversation(self):
        first = self.store.create_conversation("p1", title="old")
        self.store.append_turn(first.id, user_text="keep", assistant_text="me")
        self.store.create_conversation("p1", title="new")
        titles = {c.title for c in self.store.list_conversations("p1")}
        self.assertEqual(titles, {"old", "new"})

    def test_context_window_truncates_oldest(self):
        conv = self.store.create_conversation("p1")
        for i in range(5):
            self.store.append_turn(
                conv.id,
                user_text=("u" + str(i)) * 50,
                assistant_text=("a" + str(i)) * 50,
            )
        msgs = self.store.list_messages(conv.id)
        window = build_context_window(msgs, budget=200)
        self.assertTrue(window.truncated)
        self.assertGreater(window.omitted, 0)
        # Última mensagem do usuário deve estar presente se couber
        self.assertTrue(any(m["role"] == "assistant" for m in window.messages))

    def test_rejects_symlink_db_parent(self):
        link = Path(self.tmp.name) / "linkdir"
        real = Path(self.tmp.name) / "real"
        real.mkdir()
        link.symlink_to(real)
        with self.assertRaises(RuntimeError):
            HistoryStore(link / "conversations.sqlite3")


class ConfirmSemanticsTests(unittest.TestCase):
    def test_clear_is_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "db.sqlite3")
            store.create_conversation("p")
            store.create_conversation("p")
            deleted = store.clear_profile("p")
            self.assertEqual(deleted, 2)
            store.close()


if __name__ == "__main__":
    unittest.main()
