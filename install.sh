#!/usr/bin/env bash
set -euo pipefail

NEXUS_HOME="${HOME}/.nexus"
ENV_DIR="${NEXUS_HOME}/env"
SRC_DIR="${NEXUS_HOME}/src"
LOCAL_BIN_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${LOCAL_BIN_DIR}/nexus"
GLOBAL_WRAPPER_PATH="/usr/local/bin/nexus"
DEFAULT_REPO_URL="https://github.com/Ezequiel135/Nexus-Agent.git"
REPO_URL="${NEXUS_REPO_URL:-${DEFAULT_REPO_URL}}"
PROJECT_SOURCE="$(pwd)"

echo "[1/6] Verificando Python 3.10+"
python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

echo "[2/6] Verificando dependencias de sistema"
if [ "${NEXUS_SKIP_APT:-0}" = "1" ]; then
  echo "NEXUS_SKIP_APT=1 detectado. Pulando apt."
else
  if sudo apt-get update; then
    sudo apt-get install -y git python3-venv python3-pip python3-dev python3-tk scrot xdotool tesseract-ocr || \
      echo "Aviso: nem todas as dependencias do sistema puderam ser instaladas. O modo plain ainda pode funcionar."
  else
    echo "Aviso: apt update falhou. Continuando com instalacao local mesmo assim."
    echo "Se houver repositorio quebrado no sistema, corrija isso depois para habilitar instalacao completa de dependencias."
  fi
fi

echo "[3/6] Preparando diretorios do NEXUS AGENT"
mkdir -p "${NEXUS_HOME}"
mkdir -p "${LOCAL_BIN_DIR}"

if [ -x "${GLOBAL_WRAPPER_PATH}" ] && ! grep -q "NEXUS AGENT WRAPPER" "${GLOBAL_WRAPPER_PATH}" 2>/dev/null; then
  if [ -w /usr/local/bin ]; then
    LEGACY_BACKUP="/usr/local/bin/nexus.legacy.$(date +%s).bak"
    mv "${GLOBAL_WRAPPER_PATH}" "${LEGACY_BACKUP}" || true
    echo "Launcher antigo detectado em /usr/local/bin/nexus e movido para ${LEGACY_BACKUP}"
  elif command -v sudo >/dev/null 2>&1 && sudo -n test -w /usr/local/bin 2>/dev/null; then
    LEGACY_BACKUP="/usr/local/bin/nexus.legacy.$(date +%s).bak"
    sudo mv "${GLOBAL_WRAPPER_PATH}" "${LEGACY_BACKUP}" || true
    echo "Launcher antigo detectado em /usr/local/bin/nexus e movido para ${LEGACY_BACKUP}"
  else
    echo "Aviso: existe um /usr/local/bin/nexus antigo. O launcher novo em ~/.local/bin/nexus vai ter prioridade."
  fi
fi

if [ -d "${PROJECT_SOURCE}/.git" ] && [ -f "${PROJECT_SOURCE}/main.py" ]; then
  rm -rf "${SRC_DIR}"
  cp -r "${PROJECT_SOURCE}" "${SRC_DIR}"
else
  rm -rf "${SRC_DIR}"
  git clone "${REPO_URL}" "${SRC_DIR}"
fi
printf '%s\n' "${REPO_URL}" > "${NEXUS_HOME}/repo.txt"

echo "[4/6] Criando ambiente virtual"
python3 -m venv "${ENV_DIR}"
"${ENV_DIR}/bin/pip" install --upgrade pip

echo "[5/6] Instalando dependencias Python"
if ! "${ENV_DIR}/bin/pip" install -r "${SRC_DIR}/requirements.txt"; then
  echo "Aviso: instalacao completa do requirements falhou."
  echo "Tentando instalar ao menos o minimo para o modo plain..."
  "${ENV_DIR}/bin/pip" install rich litellm requests python-dotenv psutil || true
fi

echo "[6/6] Criando wrapper do usuario"
cat > "${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
# NEXUS AGENT WRAPPER
exec "${ENV_DIR}/bin/python" "${SRC_DIR}/main.py" "\$@"
EOF
chmod +x "${WRAPPER_PATH}"

if ! printf '%s' ":$PATH:" | grep -q ":${LOCAL_BIN_DIR}:"; then
  if [ -f "${HOME}/.bashrc" ]; then
    if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "${HOME}/.bashrc"; then
      printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "${HOME}/.bashrc"
    fi
  fi
fi

if [ "${NEXUS_INSTALL_GLOBAL:-0}" = "1" ]; then
  echo "Criando wrapper global em ${GLOBAL_WRAPPER_PATH}"
  sudo tee "${GLOBAL_WRAPPER_PATH}" >/dev/null <<EOF
#!/usr/bin/env bash
# NEXUS AGENT WRAPPER
exec "${ENV_DIR}/bin/python" "${SRC_DIR}/main.py" "\$@"
EOF
  sudo chmod +x "${GLOBAL_WRAPPER_PATH}"
fi

echo "Instalacao concluida. NEXUS AGENT criado por Ezequiel 135."
echo "Abra um novo terminal e rode:"
echo "  nexus start --plain"
