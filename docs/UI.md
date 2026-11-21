# UI Obsidian Gold — painel Ryoku

Paleta isolada em `plugins/io.github.paulon34.ryoku-ai/Theme.qml` (não altera o tema global do Omarchy):

| Token | Hex |
| --- | --- |
| Fundo | `#09090B` |
| Superfície | `#18181C` |
| Borda | `#303035` |
| Dourado | `#D4AF67` / hover `#E6C37C` |
| Perigo | `#A83B42` |
| Texto | `#F2EFE8` / `#98989F` |

Regras: dourado só em ações importantes; vermelho só em destruição/erro; 緑 e o nome Ryoku AI preservados; sem neon/glow/RGB.

Empty state corrigido (texto centralizado com `wrapMode`, fora do `ListView` para não cortar).

Rollback do plugin: `scripts/rollback-plugin.sh`.
