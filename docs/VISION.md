# Visão multimodal no Ryoku AI

**Branch:** `feat/chat-vision-backend` · **Base:** PR #13 · **Issue:** #8  
**Sem merge. Sem download automático de modelos.**

## Por que `vision.toml` (não só env)

O Quickshell frequentemente **não herda** o environment do user systemd (`systemctl --user show-environment`).  
Mesmo com `RYOKU_VISION_*` no user env, `/proc/<pid do quickshell>/environ` pode estar vazio → painel mostra `sem visão`.

Solução: configuração persistente lida pela CLI em todo processo:

`~/.config/ryoku-ai/vision.toml`

```toml
backend = "ollama"
model = "moondream:1.8b"
host = "http://127.0.0.1:11434"
# allow_remote = false
```

Criar:

```bash
ryoku vision init-config
# ou edite o arquivo manualmente
```

### Precedência

1. Variáveis de ambiente **explícitas** (`RYOKU_VISION_BACKEND`, `RYOKU_VISION_MODEL`, `RYOKU_OLLAMA_HOST`, `RYOKU_VISION_ALLOW_REMOTE`)
2. `vision.toml`
3. Desligado (padrão)

A mesma resolução vale para `ryoku vision capabilities`, `attach inspect` e o envio de imagens no chat.

## SIWC

`@siwc/local` continua **text-only**. Tokens SIWC **não** são reutilizados no caminho Ollama.

## Hardware / NVIDIA (atualizado)

- Medir com `ryoku vision capabilities` → `hardware.nvidia_usable` / `nvidia_detail`.
- `nvidia-smi` presente **não** implica driver funcional; o Ryoku tenta `nvidia-smi -L`.
- `moondream:1.8b` é adequado para CPU com ~8 GiB RAM.
- Host Ollama padrão: apenas loopback (`127.0.0.1` / `localhost`). Remoto exige `allow_remote = true` + ciência do risco.

## Ativar no notebook (PASS_REAL)

1. Confirme Ollama + modelo (`ollama list`).
2. `ryoku vision init-config` (ajuste `model` se preciso).
3. `ryoku vision capabilities` **sem** `export` — deve mostrar `vision_available: true`, `config.source: file`.
4. Reinicie só o Omarchy shell / plugin.
5. Remova a miniatura antiga e anexe de novo (metadados `vision_available` são gerados no `inspect`).
6. Envie um screenshot e confirme detalhe **só** na imagem.

## Rollback

```bash
rm ~/.config/ryoku-ai/vision.toml   # desliga visão
# ou backend = "off"
```
