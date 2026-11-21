# Ditado no composer Ryoku AI

**Status:** PR draft `feat/chat-voice-dictation` (issue #12). **Sem merge até PASS_REAL.**  
**Base:** PR #11 (`feat/chat-image-vision`) → #10 → #9.

## Relatório de capacidades (notebook Omarchy, 2026-11-21)

| Item | Achado |
|------|--------|
| Backend selecionado | `omarchy default dictation` → **superwhisper** |
| `omarchy dictation` | `start` \| `stop` \| `toggle` apenas |
| Cancel Omarchy público | **Não existe** |
| Cancel programático | **`superwhisper cancel`** → JSON `{ok, cancelled, phase}` (verificado idle) |
| Serviço | `superwhisper.service` **active**; `ready: true`, `phase: idle` |
| Processamento | ASR worker **`cloud`** (free-tier); modelos offline **missing** |
| Injeção de texto | Superwhisper `autoPasteEnabled` + `linux.textCommit` → campo **com foco** |
| Transcrição parcial para apps | **Indisponível** — `status --bar` só fase/ícone; sem API de legendas |
| Clipboard | `clipboardBehaviour: bypass` — reduz conflito com Ctrl+V de imagens |
| SIWC | **Não usado** para STT |

### Privacidade

Neste notebook o Superwhisper está em **modo nuvem**. O primeiro clique em 🎙 no painel mostra o aviso; o segundo confirma e inicia a gravação. Não instalamos modelos offline nem alteramos `superwhisper models select` sem autorização.

### Streaming parcial

**Não declarado.** A UI mostra apenas `Gravando…` / `Transcrevendo…`.

### Botão ×

Habilitado quando `ryoku dictation capabilities` reporta `cancel.available=true` (Superwhisper). Chama `superwhisper cancel` via `ryoku dictation cancel`. Se o backend for outro sem cancel verificado, × fica desabilitado com mensagem clara — **não** fingimos cancelar só na UI.

## CLI

```bash
ryoku dictation capabilities --json
ryoku dictation status --json
ryoku dictation start --json    # após focar o composer
ryoku dictation stop --json
ryoku dictation cancel --json   # Superwhisper
```

Saídas JSON **não** incluem áudio nem texto transcrito.

## UX no painel

`+ | 🎙 | ■ | × | input | Enviar` — Obsidian Gold, cantos retos.  
Parar **não** envia a mensagem. Anexos e digitação convivem com o ditado. Fechar o painel cancela se estiver gravando.

## PASS_REAL (checklist)

- [ ] Capabilities batem com o backend real
- [ ] Mic grava com foco no composer; sem auto-send
- [ ] ■ injeta texto editável no draft
- [ ] Digitação antes/depois + nova gravação
- [ ] × cancela no Superwhisper sem inserir trecho cancelado
- [ ] Cloud: aviso + segundo clique
- [ ] Anexos / Ctrl+V imagem intactos
- [ ] Esc/Enter/Nova/Renomear; shell refresh

## Rollback

```bash
git checkout feat/chat-image-vision
scripts/rollback-plugin.sh   # se o plugin estiver instalado
```
