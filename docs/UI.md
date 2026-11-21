# UI Obsidian Gold — painel Ryoku (minimalista)

Paleta isolada em `plugins/io.github.paulon34.ryoku-ai/Theme.qml` (não altera o tema global do Omarchy):

| Token | Hex |
| --- | --- |
| Fundo | `#09090B` |
| Superfície | `#121214` / `#18181C` |
| Divisória | `#242428` |
| Borda (foco) | `#303035` / dourado |
| Dourado | `#D4AF67` / hover `#E6C37C` |
| Perigo | `#A83B42` |
| Texto | `#F2EFE8` / `#98989F` |

## Layout

- **Uma superfície** preta contínua (sem cards internos).
- **Sidebar** integrada à esquerda + divisória vertical fina.
- **Chat** sem moldura; bolhas discretas, raio mínimo.
- **Composer** como faixa inferior, separado por linha horizontal.
- **Cabeçalho** flat com botões outlined finos (dourado / vermelho só em Apagar).

Empty state centralizado, sem caixa, com wrap (sem texto cortado).

Rollback: `scripts/rollback-plugin.sh`.
