"""Histórico local de conversas (SQLite). Sem TTL e sem limpeza automática."""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_STATE_NAME = "ryoku-ai"
DB_NAME = "conversations.sqlite3"
# Orçamento de caracteres enviados como contexto (aprox.; não é tokenizer).
DEFAULT_CONTEXT_CHAR_BUDGET = 120_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / APP_STATE_NAME


def default_db_path() -> Path:
    return default_state_dir() / DB_NAME


@dataclass(frozen=True)
class Conversation:
    id: str
    profile_id: str
    title: str
    created_at: str
    updated_at: str
    model: str | None
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "message_count": self.message_count,
        }


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: str
    role: str
    content: str
    status: str
    created_at: str
    attachments: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at,
        }
        if self.attachments is not None:
            payload["attachments"] = self.attachments
        return payload


@dataclass(frozen=True)
class AttachmentMeta:
    id: str
    message_id: int
    conversation_id: str
    profile_id: str
    filename: str
    extension: str
    size_bytes: int
    mime_hint: str
    truncated: bool
    warning: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "profile_id": self.profile_id,
            "filename": self.filename,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "mime_hint": self.mime_hint,
            "truncated": self.truncated,
            "warning": self.warning,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ContextWindow:
    messages: list[dict[str, str]]
    truncated: bool
    omitted: int
    budget: int


class HistoryStore:
    """Armazenamento transacional por perfil. Logout não apaga linhas."""

    def __init__(self, path: Path | None = None) -> None:
        raw = path or default_db_path()
        self._reject_symlinks(raw)
        self.path = raw.resolve()
        self._ensure_parent()
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA secure_delete=ON")
        self._migrate()
        os.chmod(self.path, 0o600)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _reject_symlinks(path: Path) -> None:
        current = path
        # Check the file and every parent before resolve() collapses links.
        for candidate in [current, *current.parents]:
            if candidate.exists() and candidate.is_symlink():
                raise RuntimeError(f"Caminho de histórico não pode ser symlink: {candidate}")
            if candidate == Path(candidate.anchor):
                break

    def _ensure_parent(self) -> None:
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)
        if self.path.exists() and self.path.is_symlink():
            raise RuntimeError(f"Arquivo SQLite não pode ser symlink: {self.path}")


    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              title TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              model TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
              role TEXT NOT NULL CHECK(role IN ('user','assistant','developer')),
              content TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'complete'
                CHECK(status IN ('complete','partial','error')),
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attachments (
              id TEXT PRIMARY KEY,
              message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              conversation_id TEXT NOT NULL,
              profile_id TEXT NOT NULL,
              filename TEXT NOT NULL,
              extension TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              mime_hint TEXT NOT NULL,
              truncated INTEGER NOT NULL DEFAULT 0,
              warning TEXT,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_profile_updated
              ON conversations(profile_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
              ON messages(conversation_id, id);
            CREATE INDEX IF NOT EXISTS idx_attachments_message
              ON attachments(message_id);
            CREATE INDEX IF NOT EXISTS idx_attachments_conversation
              ON attachments(conversation_id);
            """
        )
        self._conn.commit()

    def _active_key(self, profile_id: str) -> str:
        return f"active:{profile_id}"

    def get_active_id(self, profile_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (self._active_key(profile_id),),
        ).fetchone()
        return str(row["value"]) if row else None

    def set_active_id(self, profile_id: str, conversation_id: str | None) -> None:
        key = self._active_key(profile_id)
        if conversation_id is None:
            self._conn.execute("DELETE FROM meta WHERE key = ?", (key,))
        else:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, conversation_id),
            )
        self._conn.commit()

    def create_conversation(
        self,
        profile_id: str,
        *,
        title: str = "Nova conversa",
        model: str | None = None,
        make_active: bool = True,
    ) -> Conversation:
        cid = str(uuid.uuid4())
        now = utc_now()
        self._conn.execute(
            "INSERT INTO conversations(id, profile_id, title, created_at, updated_at, model) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cid, profile_id, title[:200], now, now, model),
        )
        self._conn.commit()
        if make_active:
            self.set_active_id(profile_id, cid)
        return Conversation(cid, profile_id, title[:200], now, now, model, 0)

    def list_conversations(self, profile_id: str) -> list[Conversation]:
        rows = self._conn.execute(
            """
            SELECT c.*, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.profile_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (profile_id,),
        ).fetchall()
        return [
            Conversation(
                id=row["id"],
                profile_id=row["profile_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                model=row["model"],
                message_count=int(row["message_count"]),
            )
            for row in rows
        ]

    def get_conversation(self, conversation_id: str, profile_id: str | None = None) -> Conversation | None:
        if profile_id is None:
            row = self._conn.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (conversation_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.id = ? AND c.profile_id = ?
                GROUP BY c.id
                """,
                (conversation_id, profile_id),
            ).fetchone()
        if not row:
            return None
        return Conversation(
            id=row["id"],
            profile_id=row["profile_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            model=row["model"],
            message_count=int(row["message_count"]),
        )

    def rename(self, conversation_id: str, profile_id: str, title: str) -> Conversation:
        cleaned = title.strip()[:200]
        if not cleaned:
            raise ValueError("Título vazio.")
        cur = self._conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND profile_id = ?",
            (cleaned, utc_now(), conversation_id, profile_id),
        )
        if cur.rowcount != 1:
            raise KeyError("Conversa não encontrada para este perfil.")
        self._conn.commit()
        conv = self.get_conversation(conversation_id, profile_id)
        assert conv is not None
        return conv

    def delete(self, conversation_id: str, profile_id: str) -> None:
        attachment_ids = [
            str(row["id"])
            for row in self._conn.execute(
                "SELECT id FROM attachments WHERE conversation_id = ? AND profile_id = ?",
                (conversation_id, profile_id),
            ).fetchall()
        ]
        cur = self._conn.execute(
            "DELETE FROM conversations WHERE id = ? AND profile_id = ?",
            (conversation_id, profile_id),
        )
        if cur.rowcount != 1:
            raise KeyError("Conversa não encontrada para este perfil.")
        if self.get_active_id(profile_id) == conversation_id:
            self.set_active_id(profile_id, None)
        self._conn.commit()
        self._conn.execute("VACUUM")
        from .attachments import delete_extracted_text

        for attachment_id in attachment_ids:
            delete_extracted_text(attachment_id)

    def clear_profile(self, profile_id: str) -> int:
        attachment_ids = [
            str(row["id"])
            for row in self._conn.execute(
                "SELECT id FROM attachments WHERE profile_id = ?",
                (profile_id,),
            ).fetchall()
        ]
        cur = self._conn.execute("DELETE FROM conversations WHERE profile_id = ?", (profile_id,))
        deleted = cur.rowcount
        self.set_active_id(profile_id, None)
        self._conn.commit()
        self._conn.execute("VACUUM")
        from .attachments import delete_extracted_text

        for attachment_id in attachment_ids:
            delete_extracted_text(attachment_id)
        return deleted

    def list_attachments_for_message(self, message_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM attachments WHERE message_id = ? ORDER BY created_at ASC",
            (message_id,),
        ).fetchall()
        return [
            AttachmentMeta(
                id=row["id"],
                message_id=int(row["message_id"]),
                conversation_id=row["conversation_id"],
                profile_id=row["profile_id"],
                filename=row["filename"],
                extension=row["extension"],
                size_bytes=int(row["size_bytes"]),
                mime_hint=row["mime_hint"],
                truncated=bool(row["truncated"]),
                warning=row["warning"],
                created_at=row["created_at"],
            ).to_dict()
            for row in rows
        ]

    def list_messages(self, conversation_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [
            Message(
                id=int(row["id"]),
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                status=row["status"],
                created_at=row["created_at"],
                attachments=self.list_attachments_for_message(int(row["id"])) or None,
            )
            for row in rows
        ]

    def append_turn(
        self,
        conversation_id: str,
        *,
        user_text: str,
        assistant_text: str,
        status: str = "complete",
        model: str | None = None,
        title_if_empty: str | None = None,
        profile_id: str | None = None,
        attachments: Sequence[Any] | None = None,
    ) -> int:
        now = utc_now()
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO messages(conversation_id, role, content, status, created_at) "
                "VALUES (?, 'user', ?, 'complete', ?)",
                (conversation_id, user_text, now),
            )
            user_message_id = int(cur.lastrowid)
            self._conn.execute(
                "INSERT INTO messages(conversation_id, role, content, status, created_at) "
                "VALUES (?, 'assistant', ?, ?, ?)",
                (conversation_id, assistant_text, status, now),
            )
            if model is not None:
                self._conn.execute(
                    "UPDATE conversations SET updated_at = ?, model = ? WHERE id = ?",
                    (now, model, conversation_id),
                )
            else:
                self._conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
            if title_if_empty:
                row = self._conn.execute(
                    "SELECT title FROM conversations WHERE id = ?",
                    (conversation_id,),
                ).fetchone()
                if row and row["title"] in {"Nova conversa", "New conversation", ""}:
                    self._conn.execute(
                        "UPDATE conversations SET title = ? WHERE id = ?",
                        (title_if_empty[:80], conversation_id),
                    )
            if attachments and profile_id:
                from .attachments import persist_extracted_text

                for item in attachments:
                    persist_extracted_text(item.id, item.text)
                    self._conn.execute(
                        "INSERT INTO attachments("
                        "id, message_id, conversation_id, profile_id, filename, extension, "
                        "size_bytes, mime_hint, truncated, warning, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item.id,
                            user_message_id,
                            conversation_id,
                            profile_id,
                            item.filename,
                            item.extension,
                            item.size_bytes,
                            item.mime_hint,
                            1 if item.truncated else 0,
                            item.warning,
                            now,
                        ),
                    )
        return user_message_id

    def resolve_conversation(
        self,
        profile_id: str,
        *,
        conversation_id: str | None = None,
        create_new: bool = False,
        model: str | None = None,
    ) -> Conversation:
        if create_new:
            return self.create_conversation(profile_id, model=model)
        if conversation_id:
            existing = self.get_conversation(conversation_id, profile_id)
            if existing is None:
                raise KeyError("Conversa não encontrada para este perfil.")
            self.set_active_id(profile_id, existing.id)
            return existing
        active = self.get_active_id(profile_id)
        if active:
            existing = self.get_conversation(active, profile_id)
            if existing is not None:
                return existing
        latest = self.list_conversations(profile_id)
        if latest:
            self.set_active_id(profile_id, latest[0].id)
            return latest[0]
        return self.create_conversation(profile_id, model=model)


def _content_for_model(message: Message) -> str:
    """Reaproveita texto extraído de anexos (arquivo local), sem binários no SQLite."""
    content = message.content
    if message.role != "user" or not message.attachments:
        return content
    from .attachments import load_extracted_text

    blocks: list[str] = []
    for meta in message.attachments:
        attachment_id = str(meta.get("id") or "")
        filename = str(meta.get("filename") or "anexo")
        text = load_extracted_text(attachment_id) if attachment_id else None
        if not text:
            continue
        header = f"--- Anexo: {filename}"
        if meta.get("truncated"):
            header += ", truncado"
        header += " ---"
        blocks.append(header)
        if meta.get("warning"):
            blocks.append(f"[aviso] {meta['warning']}")
        blocks.append(text)
    if not blocks:
        return content
    return content.rstrip() + "\n\n" + "\n".join(blocks)


def build_context_window(
    messages: Sequence[Message],
    *,
    budget: int = DEFAULT_CONTEXT_CHAR_BUDGET,
) -> ContextWindow:
    """Inclui o máximo de mensagens recentes completas que cabem no orçamento."""
    usable = [m for m in messages if m.status == "complete" and m.role in {"user", "assistant"}]
    prepared = [(m, _content_for_model(m)) for m in usable]
    selected: list[tuple[Message, str]] = []
    total = 0
    for message, content in reversed(prepared):
        size = len(content)
        if selected and total + size > budget:
            break
        selected.append((message, content))
        total += size
    selected.reverse()
    omitted = len(usable) - len(selected)
    return ContextWindow(
        messages=[{"role": m.role, "content": content} for m, content in selected],
        truncated=omitted > 0,
        omitted=omitted,
        budget=budget,
    )


def suggest_title(user_text: str) -> str:
    line = " ".join(user_text.strip().split())
    if not line:
        return "Nova conversa"
    return line if len(line) <= 60 else line[:57] + "…"
