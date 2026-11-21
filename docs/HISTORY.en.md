# Local history and Quickshell panel

See the Portuguese guide: [HISTORY.md](HISTORY.md).

Summary:

- SQLite at `~/.local/state/ryoku-ai/conversations.sqlite3` (no auto-delete, no TTL)
- Conversations isolated per SIWC `profile_id`; logout keeps history
- Prior messages are resent as Responses `input` within a character budget
- Plugin `io.github.paulon34.ryoku-ai` talks to `ryoku` via static argv + stdin only
- Install/rollback: `scripts/install-plugin.sh` / `scripts/rollback-plugin.sh`
- **PASS_REAL** on the Omarchy notebook is still required before merge
