# Histórico local e painel Quickshell

**Status:** implementado no código (Sprint 2 / issue #5). **PASS_REAL no notebook pendente.**

## O que é persistido

- Banco SQLite em `${XDG_STATE_HOME:-~/.local/state}/ryoku-ai/conversations.sqlite3`
- Diretório `0700`, arquivo `0600`, recusa symlink
- Conversas isoladas por `profile_id` do SIWC
- **Logout não apaga** conversas; só remove credenciais. Novo login é necessário para enviar ao modelo
- **Sem TTL**, sem limpeza por dias, sem exclusão automática ao fechar o painel/terminal/Quickshell

## Contexto real

Cada turno monta um `input` array `user`/`assistant` com as mensagens anteriores que cabem no orçamento (`120_000` caracteres). Se mensagens antigas ficarem de fora, o CLI avisa (e o evento JSONL inclui `truncated`/`omitted`). Não há “memória mágica” além do que foi reenviado.

Histórico local **não** é o histórico nem a memória do ChatGPT na nuvem.

## CLI

```bash
ryoku chat                     # retoma a conversa mais recente do perfil
ryoku chat --new
ryoku chat --conversation ID
ryoku chat --jsonl --prompt-stdin   # UI: prompt via stdin, eventos NDJSON
ryoku history list [--json]
ryoku history show ID [--json]
ryoku history rename ID "título"
ryoku history delete ID            # pede confirmação (ou --yes)
ryoku history clear                # pede confirmação (ou --yes)
```

Apagar usa `PRAGMA secure_delete=ON` + `VACUUM`. Snapshots/backups do sistema de arquivos podem ainda conter dados antigos.

## Plugin Omarchy

Arquivos em `plugins/io.github.paulon34.ryoku-ai/`. Instalação reversível:

```bash
scripts/install-plugin.sh
omarchy plugin validate ~/.config/omarchy/plugins/io.github.paulon34.ryoku-ai
qmllint -I "$OMARCHY_PATH/shell" \
  ~/.config/omarchy/plugins/io.github.paulon34.ryoku-ai/BarWidget.qml \
  ~/.config/omarchy/plugins/io.github.paulon34.ryoku-ai/Panel.qml
omarchy plugin enable io.github.paulon34.ryoku-ai
omarchy bar put io.github.paulon34.ryoku-ai --section left
# omarchy restart shell   # só se necessário
```

Rollback: `scripts/rollback-plugin.sh` — remove só o plugin Ryoku; **não** altera bandeja animada, Google Agenda nem Resonance.

O QML usa `Quickshell.Io.Process` com argv estático e stdin para prompts. Tokens SIWC nunca passam pelo QML.

## PASS_REAL (notebook)

- [ ] Mensagem no terminal → reaparece no painel após fechar/abrir
- [ ] Reinício do Quickshell / sessão → mesma conversa
- [ ] Nova conversa, troca, apagar com confirmação
- [ ] Logout preserva SQLite; login volta a enviar contexto
- [ ] Esc fecha painel; Enter envia; UTF-8; 2 monitores / escala 1.25
- [ ] Streaming cancelável sem corromper histórico anterior
