# Anexos no Ryoku AI

**Status Fase 1 (texto/PDF):** PR #10 (`feat/chat-file-attachments`).  
**Status Fase 2 (imagens UI):** esta branch (`feat/chat-image-vision`) — seleção PNG/JPEG/WebP, Ctrl+V (captura única), miniatura e aviso claro.  
**Análise visual:** ver [VISION.md](VISION.md) — SIWC text-only; Ollama opt-in (`RYOKU_VISION_BACKEND=ollama`) quando instalado. Sem pull automático.

Não declarar visão OK sem PASS_REAL no hardware com detalhe exclusivo no print.

### Hardware local (checagem pré-modelo)

Medido neste notebook antes de qualquer download: ~15 GiB RAM (~6 GiB disponível), driver NVIDIA **indisponível** (`nvidia-smi` falhou), ~421 GiB livres em `/home`. **Não** instalar Ollama/modelos multimodais nem alterar provedor sem autorização explícita.

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

## Fase 2 — imagens (UI sim; visão não)

Já nesta PR draft:

- Filtro de imagens no `FileDialog`; prévia com miniatura; remoção/substituição.
- `ryoku attach paste-image` (wl-paste/xclip, **uma** leitura — sem monitor contínuo); painel Ctrl+V com fallback para texto.
- `ryoku attach capabilities` → `vision_available: false`.
- `inspect` aceita imagem só para metadados/prévia; `extract`/`chat --request-stdin` rejeita com `vision_unavailable`.

Ainda bloqueado / não feito:

- Envio multimodal real ao SIWC (SDK string-only).
- Backend Ollama opt-in (`RYOKU_VISION_BACKEND`) — stub de env existe, **sem** implementação nem download.
- Screenshot dedicado (evolução): use ferramenta do Omarchy + anexar PNG, ou Ctrl+V do print.
- Teste PASS_REAL “detalhe só no print” — **adiado** até backend compatível.

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
