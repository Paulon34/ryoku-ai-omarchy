# 緑 Ryoku AI — Omarchy

**A lightweight, conversation-first assistant for Omarchy / Arch Linux.**

[Português](README.md) · English

> **Pre-alpha v0.3 (Sprint 2):** persistent local history + Quickshell plugin. **Notebook PASS_REAL still pending.** No Codex tokens or separately billed API keys.

## Features

- SIWC login via pinned `@siwc/local` bridge (see [docs/AUTH.md](docs/AUTH.md))
- SQLite conversation history shared by terminal and bar panel ([docs/HISTORY.md](docs/HISTORY.md))
- Real context forwarding (prior messages resent in `input`)
- Plugin `io.github.paulon34.ryoku-ai` with 緑 button; reversible install/rollback

```bash
(cd siwc_bridge && npm install)
pip install -e .
ryoku login && ryoku chat
scripts/install-plugin.sh
```

Original code: **MIT**. Vendored DevKit: OpenAI Noncommercial License.
