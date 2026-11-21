<div align="center">

# 緑 RYOKU AI — OMARCHY

**Assistente de IA leve e conversacional para Omarchy / Arch Linux.**

Terminal primeiro · ChatGPT com consentimento · Segurança · Quickshell

[🇧🇷 Português](README.md) · [🇬🇧 English](README.en.md)

</div>

> **Pré-alpha v0.5 (ditado + anexos + visão opt-in):** 🎙 Superwhisper; anexos texto/PDF; visão via Ollama local **somente com opt-in** (SIWC continua text-only). **PASS_REAL visão pendente.** Sem merge automático / sem pull de modelos.

## A ideia

Um comando `ryoku chat` para conversar naturalmente com um assistente via terminal, e um botão **緑** na barra Omarchy com o mesmo histórico. **Cursor é a ferramenta que desenvolve o código**, não o chatbot.

## O que já funciona

- `ryoku doctor` / `status` / `login` / `logout` / `models`
- `ryoku chat` com histórico SQLite, contexto reenviado, `--jsonl --prompt-stdin` / `--request-stdin` (anexos)
- `ryoku attach inspect` para validar arquivos localmente
- `ryoku history list|show|rename|delete|clear` (exclusão só com confirmação)
- Plugin `io.github.paulon34.ryoku-ai` (BarWidget + Panel + seletor de anexos)
- Ditado no painel: [docs/DICTATION.md](docs/DICTATION.md)
- Detalhes de anexos: [docs/ATTACHMENTS.md](docs/ATTACHMENTS.md)

## Como testar no Omarchy

```bash
git clone https://github.com/Paulon34/ryoku-ai-omarchy.git
cd ryoku-ai-omarchy
git checkout feat/persistent-chat-quickshell   # ou a branch da PR
python3 -m venv .venv
.venv/bin/python -m pip install -e .
(cd siwc_bridge && npm install)
.venv/bin/ryoku login
.venv/bin/ryoku chat
scripts/install-plugin.sh
# omarchy plugin enable io.github.paulon34.ryoku-ai
# omarchy bar put io.github.paulon34.ryoku-ai --section left
```

Rollback do plugin: `scripts/rollback-plugin.sh` (não mexe na bandeja, Agenda ou Resonance).

Detalhes: [docs/HISTORY.md](docs/HISTORY.md) · [docs/AUTH.md](docs/AUTH.md)

Testes: `.venv/bin/python -m unittest discover -s tests -v`.

## Privacidade

- Credenciais SIWC: keyring; nunca no QML
- Histórico: só em `~/.local/state/ryoku-ai/` — local, sem sync GitHub/telemetria
- Histórico local ≠ memória do ChatGPT
- Logout não apaga conversas

## Roteiro

1. V0.1: CLI e diagnósticos
2. V0.2: login SIWC (PR #4)
3. V0.3: histórico + painel Quickshell
4. V0.4: anexos texto/PDF (Fase 1); visão multimodal quando o SIWC/backend permitir

Código original **MIT**. Vendor `@siwc/local`: Noncommercial License do DevKit. Projeto independente.
