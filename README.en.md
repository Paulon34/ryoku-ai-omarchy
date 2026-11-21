# 緑 Ryoku AI — Omarchy

**A lightweight, conversation-first assistant for Omarchy / Arch Linux.** The Cursor IDE remains a separate coding tool.

[Português](README.md) · English

> **Pre-alpha v0.1:** a read-only local diagnostic CLI is available. ChatGPT sign-in and AI chat are **not implemented yet**. There is no Codex-token extraction and no API key or billing dependency.

## Run it

Python 3.11+, zero runtime dependencies.

```bash
git clone https://github.com/Paulon34/ryoku-ai-omarchy.git
cd ryoku-ai-omarchy
PYTHONPATH=src python3 -m ryoku_ai doctor
PYTHONPATH=src python3 -m ryoku_ai status
```

Optional install into a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/ryoku doctor --json
```

Implemented: `ryoku`, `ryoku doctor`, `ryoku status`. `ryoku chat` intentionally returns an explicit "not connected" message, not fabricated chatbot output.

## Planned authentication

OpenAI documents [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart) for eligible local open-source projects, with an additional user consent option to apply eligible ChatGPT plan allowance to AI requests. This is **not** the separately billed ordinary API key flow; eligibility and usage limits apply.

We will use the official [developer guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) and SDK only after auditing secure Linux credential storage and packaging. Never extract existing ChatGPT/Codex login tokens, cookies or account data. A ChatGPT connection does not automatically provide past conversation history or memories.

See [auth design](docs/AUTH.md) and the [Cursor backlog](docs/CURSOR_TASKS.md).

Future: terminal chat, opt-in history, then a Quickshell panel running inside Omarchy's existing shell. No automatic `sudo`, privileged shell execution or sensitive machine-data collection.

Original Ryoku code: **MIT**. Independent community project; not affiliated with OpenAI or Omarchy.
