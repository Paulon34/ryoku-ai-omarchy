# Bridge SIWC (Ryoku)

Processo Node confiável que envolve `@siwc/local` pinado em `vendor/siwc-local`.

```bash
# Requer Node >= 22 e libsecret (Arch: libsecret; Debian/Ubuntu: libsecret-1-dev)
npm install
```

O CLI Python fala NDJSON com `src/bridge.mjs`. Credenciais usam keytar (Secret Service/KWallet); não há fallback em texto puro.

Variáveis:
- `RYOKU_SIWC_STORAGE_DIR` — diretório absoluto (padrão `~/.config/ryoku-ai-omarchy`)
- `RYOKU_SIWC_TEST_MEMORY_CRYPTO=1` — **somente testes**; nunca no caminho interativo do usuário
