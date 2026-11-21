#!/usr/bin/env bash
# Remove o plugin Ryoku e restaura o último backup, se existir.
# Não toca em outros plugins (bandeja, Agenda, Resonance, etc.).
set -euo pipefail

PLUGIN_ID="io.github.paulon34.ryoku-ai"
DEST="${HOME}/.config/omarchy/plugins/${PLUGIN_ID}"
STATE="${HOME}/.local/state/ryoku-ai"
MARKER="${STATE}/last-install-backup"
BIN_DIR="${HOME}/.local/bin"

BACKUP=""
if [[ -f "${MARKER}" ]]; then
  BACKUP="$(cat "${MARKER}")"
fi

if [[ -d "${DEST}" ]]; then
  echo "Removendo ${DEST}"
  rm -rf "${DEST}"
fi

if [[ -n "${BACKUP}" && -d "${BACKUP}/plugin" ]]; then
  echo "Restaurando plugin de ${BACKUP}/plugin"
  cp -a "${BACKUP}/plugin" "${DEST}"
fi

if [[ -L "${BIN_DIR}/ryoku" ]]; then
  target="$(readlink -f "${BIN_DIR}/ryoku" || true)"
  if [[ "${target}" == *ryoku-ai-omarchy* || "${target}" == *ryoku* ]]; then
    echo "Removendo symlink ${BIN_DIR}/ryoku"
    rm -f "${BIN_DIR}/ryoku"
  fi
fi

if [[ -n "${BACKUP}" && -f "${BACKUP}/ryoku.bin" ]]; then
  echo "Restaurando ${BIN_DIR}/ryoku a partir do backup"
  cp -a "${BACKUP}/ryoku.bin" "${BIN_DIR}/ryoku"
elif [[ -n "${BACKUP}" && -f "${BACKUP}/ryoku.link" ]]; then
  ln -sfn "$(cat "${BACKUP}/ryoku.link")" "${BIN_DIR}/ryoku"
fi

if command -v omarchy >/dev/null 2>&1; then
  echo "Se o widget ainda aparecer na barra, remova a entrada em ~/.config/omarchy/shell.json"
  echo "ou: omarchy plugin disable ${PLUGIN_ID}  (se disponível)"
  echo "Depois: omarchy-shell shell rescanPlugins   # ou omarchy restart shell"
fi

echo "Rollback concluído. Histórico SQLite em ~/.local/state/ryoku-ai/ NÃO foi apagado."
