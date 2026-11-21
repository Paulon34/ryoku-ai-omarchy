<div align="center">

# 緑 RYOKU AI — OMARCHY

**Assistente de IA leve e conversacional para Omarchy / Arch Linux.**

Terminal primeiro · ChatGPT com consentimento · Segurança · Quickshell depois

[🇧🇷 Português](README.md) · [🇬🇧 English](README.en.md)

</div>

> **Pré-alpha v0.2 (Sprint 1):** CLI, diagnóstico e integração SIWC via `@siwc/local` pinado. **PASS_REAL do login no notebook ainda pendente** — não use em produção. Não usa tokens de Codex nem chave de API cobrada à parte.

## A ideia

Um comando `ryoku chat` para conversar naturalmente com um assistente via terminal, depois um painel Quickshell discreto na barra. **Cursor é a ferramenta que desenvolve o código**, não o chatbot. Este repositório é independente do [Ryoku Desktop](https://github.com/Paulon34/ryoku-desktop), da versão NixOS e do projeto Jarvis.

## O que já funciona

- `ryoku`: saudação e comandos disponíveis.
- `ryoku doctor`: verifica Linux, família Arch, ferramentas e prontidão do bridge SIWC, sem ler tokens.
- `ryoku status`: estágio do projeto + sessão (identity vs `session.sharing`).
- `ryoku login` / `logout`: Sign in with ChatGPT oficial (navegador, PKCE, keyring).
- `ryoku models` / `ryoku chat`: descoberta de modelos e streaming após consentimento do plano.

## Como testar no Omarchy

Python 3.11+ e, para login/chat, **Node.js 22+**, `npm`, `libsecret` (Secret Service ou KWallet):

```bash
git clone https://github.com/Paulon34/ryoku-ai-omarchy.git
cd ryoku-ai-omarchy
python3 -m venv .venv
.venv/bin/python -m pip install -e .
(cd siwc_bridge && npm install)
.venv/bin/ryoku doctor
.venv/bin/ryoku login
.venv/bin/ryoku models
.venv/bin/ryoku chat
```

Diagnóstico sem Node continua possível: `PYTHONPATH=src python3 -m ryoku_ai doctor`.

Testes mockados: `.venv/bin/python -m unittest discover -s tests -v`.

## Sobre ChatGPT Plus

A assinatura Plus **não** cobre o uso normal da API OpenAI (faturamento separado). O fluxo **Sign in with ChatGPT para OSS local** permite pedidos elegíveis com consentimento e limites da conta. Elegibilidade só se confirma no login real (`session.sharing`).

- [Quickstart oficial](https://developers.openai.com/siwc/quickstart)
- [Cookbook oficial](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [Decisões de autenticação](docs/AUTH.md)

Não extraímos cookies, contas do Cursor ou tokens do Codex. Conversas/memórias do ChatGPT não são herdadas.

## Princípios

**Local-first.** Credenciais no Secret Service/KWallet; arquivos de perfil criptografados; permissões `0700`. Falha fechada sem chaveiro. Nenhum `sudo` automático.

## Roteiro

1. V0.1: CLI e diagnósticos.
2. V0.2: login oficial seguro e `ryoku chat` (código nesta sprint; PASS_REAL pendente).
3. V0.3: histórico local opcional e diagnósticos assistidos.
4. V0.4: plugin Quickshell integrado à barra Omarchy.

O [backlog para o Cursor](docs/CURSOR_TASKS.md) detalha cada etapa.

Código original sob **MIT**. O vendor `@siwc/local` segue a **Noncommercial License** do DevKit OpenAI. Projeto independente, não afiliado à OpenAI ou aos mantenedores do Omarchy.
