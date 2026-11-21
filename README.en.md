# 緑 Ryoku AI — Omarchy

**A lightweight, conversation-first assistant for Omarchy / Arch Linux.** The Cursor IDE remains a separate coding tool.

[Português](README.md) · English

> **Pre-alpha v0.2 (Sprint 1):** CLI, diagnostics, and SIWC via pinned `@siwc/local`. **Real-notebook PASS_REAL is still pending.** No Codex-token extraction and no separately billed API key.

## Run it

Python 3.11+. For login/chat: **Node.js 22+**, `npm`, and Linux Secret Service / KWallet (`libsecret`):

```bash
git clone https://github.com/Paulon34/ryoku-ai-omarchy.git
cd ryoku-ai-omarchy
python3 -m venv .venv
.venv/bin/python -m pip install -e .
(cd siwc_bridge && npm install)
.venv/bin/ryoku doctor
.venv/bin/ryoku login
.venv/bin/ryoku chat
```

Doctor still works without Node: `PYTHONPATH=src python3 -m ryoku_ai doctor`.

Mock tests: `.venv/bin/python -m unittest discover -s tests -v`.

## Authentication

We use the official [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart) open-source plan-usage flow through a pinned `@siwc/local` bridge. Credentials are encrypted with an OS-backed key (no plaintext fallback). See [auth design](docs/AUTH.md).

Original Ryoku code: **MIT**. Vendored DevKit code: OpenAI Noncommercial License. Independent community project; not affiliated with OpenAI or Omarchy.
