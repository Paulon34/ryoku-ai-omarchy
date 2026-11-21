<div align="center">

# 緑 RYOKU AI — OMARCHY

**Assistente de IA leve e conversacional para Omarchy / Arch Linux.**

Terminal primeiro · ChatGPT com consentimento · Segurança · Quickshell depois

[🇧🇷 Português](README.md) · [🇬🇧 English](README.en.md)

</div>

> **Pré-alpha v0.1:** o CLI e o diagnóstico somente leitura estão implementados. **O login e as conversas pelo ChatGPT ainda não estão implementados.** Não usa tokens de Codex nem chave de API.

## A ideia

Um comando `ryoku chat` para conversar naturalmente com um assistente via terminal, depois um painel Quickshell discreto na barra. **Cursor é a ferramenta que desenvolve o código**, não o chatbot. Este repositório é independente do [Ryoku Desktop](https://github.com/Paulon34/ryoku-desktop), da versão NixOS e do projeto Jarvis.

## O que já funciona

- `ryoku`: saudação e comandos disponíveis.
- `ryoku doctor`: verifica Linux, família Arch e presença do CLI Omarchy, Hyprland e Quickshell, sem executar comandos externos.
- `ryoku doctor --json`: mesmo diagnóstico em JSON, sem dados pessoais.
- `ryoku status`: estado da implementação.
- `ryoku chat`: avisa com transparência que o ChatGPT ainda não está conectado, sem fingir que respondeu.

## Como testar no Omarchy

Python 3.11+; nenhuma dependência em tempo de execução:

```bash
git clone https://github.com/Paulon34/ryoku-ai-omarchy.git
cd ryoku-ai-omarchy
PYTHONPATH=src python3 -m ryoku_ai doctor
PYTHONPATH=src python3 -m ryoku_ai status
```

Se quiser disponibilizar o comando `ryoku`, instale em um ambiente virtual (sem `sudo`):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/ryoku doctor
```

Testes: `.venv/bin/python -m unittest discover -s tests -v`.

## Sobre ChatGPT Plus

A assinatura Plus não cobre o uso normal da API OpenAI, cujo faturamento é separado. Porém, a OpenAI documenta **Sign in with ChatGPT para projetos open source locais**, permitindo pedidos de IA elegíveis com autorização específica e limites da conta. A disponibilidade e os escopos precisam ser verificados no login real; **esse fluxo não está funcionando neste projeto ainda**.

- [Quickstart oficial](https://developers.openai.com/siwc/quickstart)
- [Cookbook oficial](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [Decisões de autenticação](docs/AUTH.md)

A integração não herda automaticamente suas conversas nem memórias do ChatGPT. Não vamos extrair cookies, contas do Cursor ou tokens do Codex.

## Princípios

**Local-first.** Credenciais, quando implementadas, ficam protegidas pelo armazenamento seguro do sistema operacional, nunca no Git. Nenhum comando é executado no sistema sem propósito e autorização explícitos. Nenhuma alteração com `sudo` automático. Nenhum daemon permanente enquanto a V1 não justificar.

## Roteiro

1. V0.1: CLI e diagnósticos (código presente; testes automatizados).
2. V0.2: login oficial seguro e `ryoku chat` real.
3. V0.3: histórico local opcional e diagnósticos assistidos.
4. V0.4: plugin Quickshell integrado à barra Omarchy.

O [backlog para o Cursor](docs/CURSOR_TASKS.md) detalha cada etapa, sem afirmar que funções futuras já existem.

Código original sob **MIT**. Projeto independente, não afiliado à OpenAI ou aos mantenedores do Omarchy.
