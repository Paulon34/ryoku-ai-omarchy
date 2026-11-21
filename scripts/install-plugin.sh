#!/usr/bin/env bash
# Instala o plugin Ryoku no diretório de plugins do usuário (reversível).
# NÃO edita /usr/share/omarchy nem sobrescreve shell.json sem confirmação.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ID="io.github.paulon34.ryoku-ai"
SRC="${REPO_ROOT}/plugins/${PLUGIN_ID}"
DEST="${HOME}/.config/omarchy/plugins/${PLUGIN_ID}"
BIN_DIR="${HOME}/.local/bin"
BACKUP_DIR="${HOME}/.local/state/ryoku-ai/backups/$(date -u +%Y%m%dT%H%M%SZ)"

if [[ ! -f "${SRC}/manifest.json" ]]; then
  echo "Plugin fonte ausente: ${SRC}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}" "${BIN_DIR}" "${HOME}/.config/omarchy/plugins"

if [[ -e "${DEST}" ]]; then
  echo "Backup do plugin existente → ${BACKUP_DIR}/plugin"
  cp -a "${DEST}" "${BACKUP_DIR}/plugin"
  rm -rf "${DEST}"
fi

cp -a "${SRC}" "${DEST}"
echo "Plugin instalado em ${DEST}"

# Wrapper opcional de ryoku em ~/.local/bin (não sobrescreve sem backup)
RYOKU_TARGET="${REPO_ROOT}/.venv/bin/ryoku"
if [[ ! -x "${RYOKU_TARGET}" ]]; then
  RYOKU_TARGET="$(command -v ryoku || true)"
fi

if [[ -n "${RYOKU_TARGET}" ]]; then
  if [[ -e "${BIN_DIR}/ryoku" && ! -L "${BIN_DIR}/ryoku" ]]; then
    echo "Backup de ${BIN_DIR}/ryoku → ${BACKUP_DIR}/ryoku.bin"
    cp -a "${BIN_DIR}/ryoku" "${BACKUP_DIR}/ryoku.bin"
  elif [[ -L "${BIN_DIR}/ryoku" ]]; then
    readlink -f "${BIN_DIR}/ryoku" > "${BACKUP_DIR}/ryoku.link" || true
  fi
  ln -sfn "${RYOKU_TARGET}" "${BIN_DIR}/ryoku"
  echo "Symlink ${BIN_DIR}/ryoku → ${RYOKU_TARGET}"
else
  echo "Aviso: binário ryoku não encontrado. Instale o CLI (pip install -e .) antes." >&2
fi

mkdir -p "${HOME}/.local/state/ryoku-ai"
echo "${BACKUP_DIR}" > "${HOME}/.local/state/ryoku-ai/last-install-backup"

if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin validate "${DEST}" || true
  echo "Próximos passos (não alteram bandeja/Agenda/Resonance automaticamente):"
  echo "  omarchy plugin enable ${PLUGIN_ID}"
  echo "  omarchy bar put ${PLUGIN_ID} --section left   # ou a seção que preferir"
  echo "  omarchy restart shell   # só se o hot-reload não listar o widget"
else
  echo "omarchy CLI não encontrado; copie o plugin e habilite manualmente."
fi

echo "Rollback: scripts/rollback-plugin.sh"
