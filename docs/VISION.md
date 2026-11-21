# Visão multimodal no Ryoku AI

**Branch:** `feat/chat-vision-backend` · **Base:** PR #13 (`feat/chat-voice-dictation`) · **Issue:** #8  
**Sem merge. Sem download automático de modelos.**

## 1. SIWC / ChatGPT sharing

Investigação no vendor `@siwc/local`:

- `ResponseInputMessage.content` é **`string`** (`vendor/siwc-local/src/types.ts`).
- `streamResponse` rejeita qualquer `content` que não seja string (`responses.ts`).
- Conclusão: **não há suporte multimodal oficial** na integração SIWC atual. Não reutilizar tokens SIWC em APIs incompatíveis.

## 2. Backend recomendado (opt-in)

| Opção | Uso | Custo | Estado neste notebook |
|-------|-----|-------|------------------------|
| SIWC Responses | — | plano ChatGPT | **Text-only** |
| **Ollama local** (`RYOKU_VISION_BACKEND=ollama`) | bytes reais via `/api/chat` + `images[]` base64 | local (energia/disco) | **Não instalado** |
| API paga OpenAI Platform | — | cobrança | **Não habilitado** (exige autorização) |

**Recomendação:** Ollama + modelo vision (ex. `llava:7b` ou `moondream`) **somente após autorização** e checagem de RAM/VRAM.

### Requisitos típicos (`llava:7b`)

- Download ~4.7 GiB
- ~8 GiB+ RAM livres (CPU) ou ~6 GiB VRAM
- Serviço `ollama` em `http://127.0.0.1:11434`

### Hardware medido (notebook)

- RAM total ~15 GiB; disponível ~5 GiB no momento da medição
- `nvidia-smi`: **falhou** (driver indisponível)
- `ollama`: **ausente**
- Disco `/home`: ~421 GiB livres

**Compatibilidade atual:** arquitetura pronta; **análise real ainda depende** de instalar Ollama + puxar modelo com autorização. Com a RAM livre atual, `llava:7b` em CPU é arriscado sem fechar apps.

## 3. O que foi implementado

- Correção UI: falha de envio (ex. imagem sem visão) **restaura draft + anexos**, remove `...` provisório, mensagem curta, sem adotar conversa vazia.
- Validação de anexos **antes** de criar conversa SQLite; remove conversa `--new` vazia se a visão falhar depois.
- `ryoku vision capabilities` — probe somente leitura (SIWC text-only, Ollama, hardware).
- Provider Ollama opt-in: envia **bytes reais** (base64); resposta prefixada `[visão: ollama/<modelo>]`.
- Limites de tamanho/extensão/symlink preservados; sem OCR fingido; sem tokens SIWC no caminho de visão.

## 4. O que depende de autorização

- Instalar Ollama
- `ollama pull <modelo>`
- Confirmar uso de CPU/GPU e impacto de memória
- Qualquer API paga de visão

## 5. Como ativar (manual)

```bash
# após autorização explícita
# 1) instalar ollama; 2) ollama pull llava:7b
export RYOKU_VISION_BACKEND=ollama
export RYOKU_VISION_MODEL=llava:7b   # opcional
ryoku vision capabilities
```

## 6. Testes

- Unitários: rejeição sem backend, restore contract no Panel, mock Ollama analyze, capabilities.
- **PASS_REAL visão:** só quando o modelo identificar detalhe **exclusivo da imagem** (não do prompt).

## 7. Rollback

```bash
git checkout feat/chat-voice-dictation
# ou fechar a PR draft desta branch
```
