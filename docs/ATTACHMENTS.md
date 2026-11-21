# Anexos no Ryoku AI

**Status Fase 1 (texto/PDF):** implementado nesta branch (`feat/chat-file-attachments`).  
**Status Fase 2 (imagens/visão):** bloqueado — `@siwc/local` vendorizado aceita somente `content: string`.

Não afirmar análise visual sem backend compatível comprovado no hardware (PASS_REAL).

## Fase 1 — o que funciona

- Botão `+` no painel → `QtQuick.Dialogs.FileDialog` (portal nativo no Omarchy/Wayland).
- Formatos: TXT, MD, LOG, JSON, CSV/TSV, código comum e PDF com texto extraível.
- Prévia compacta (nome · formato · tamanho · truncado) acima do composer; remoção antes do envio.
- Envio via `ryoku chat --request-stdin` com JSON `{prompt, attachments:[{path}]}` — **conteúdo nunca vai no argv**.
- `ryoku attach inspect` valida caminhos via stdin JSON `{paths:[...]}` e devolve metadados (sem dump completo).
- Extração local; PDF sem texto → erro claro (`pdf_no_text`), sem resumo fictício.
- Histórico: metadados no SQLite; texto em `~/.local/state/ryoku-ai/attachment-text/<id>.txt` (0600); exclusão junto da conversa; isolamento por perfil; reuso no contexto.

### CLI

```bash
# Inspecionar (UI / debug)
printf '%s' '{"paths":["/abs/path/nota.md"]}' | ryoku attach inspect --json

# Chat com anexos (painel usa isto)
printf '%s' '{"prompt":"Resuma","attachments":[{"path":"/abs/path/nota.md"}]}' \
  | ryoku chat --jsonl --request-stdin --new
```

O REPL/CLI sem anexos permanece: `ryoku chat` e `--prompt-stdin` / `-p`.

### Limites (env)

| Variável | Padrão |
|----------|--------|
| `RYOKU_ATTACH_MAX_FILES` | 5 |
| `RYOKU_ATTACH_MAX_BYTES` | 2097152 (2 MiB) |
| `RYOKU_ATTACH_MAX_CHARS` | 80000 |
| `RYOKU_ATTACH_MAX_TOTAL_CHARS` | 100000 |

PDF opcional: `pip install 'ryoku-ai-omarchy[pdf]'` ou `pdftotext` (poppler).

## Fase 2 — imagens (não liberar sem prova)

- PNG/JPEG/WebP, Ctrl+V, miniatura, screenshot: UI pode ser esboçada, mas análise exige SDK/backend multimodal.
- Bloqueio atual: `vendor/siwc-local` tipa e valida entrada textual; Responses API via SIWC **não** implica visão automática.
- Opção futura: Ollama multimodal **opt-in**, só após medir RAM/VRAM/disco e autorização explícita.
- Até lá, anexar imagem retorna `vision_unavailable` com mensagem clara na UI.

## Privacidade

- Só arquivos escolhidos explicitamente; sem monitor contínuo de clipboard.
- Anexos tratados como dados não confiáveis no prompt (preâmbulo anti-instrução).
- Sem upload silencioso; sem tokens/conteúdo em logs de depuração.
- Symlinks, paths relativos, vazios, enormes e binários com NUL são rejeitados.

## Testes

```bash
python -m unittest tests.test_attachments tests.test_history tests.test_cli -v
```

Cobertura Fase 1: válidos, vazios, enormes, Unicode, binário, symlink, extensão inválida, imagem bloqueada, truncamento, persistência/isolamento, `--request-stdin` / `attach inspect`.

## Rollback

```bash
git checkout feat/chat-panel-visual-polish
# ou reverter o merge da PR desta branch
omarchy-refresh-omarchy-shell   # se o plugin já estiver instalado
```

## PASS_REAL (notebook)

1. Selecionar arquivo pelo `+` e ver prévia; remover e reanexar.
2. Perguntar sobre conteúdo real do arquivo e conferir a resposta.
3. Histórico compartilhado terminal ↔ painel; apagar conversa remove texto em disco.
4. Escala 1.25 / monitor externo; Nova, Atualizar, Renomear, Apagar, Enter, Esc.
5. Bandeja, Google Agenda e Resonance intactos.
6. **Não** marcar visão/imagem como OK sem teste com detalhe exclusivo no print.
