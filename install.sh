#!/usr/bin/env bash
set -euo pipefail

NEXUS_HOME="${HOME}/.nexus"
ENV_DIR="${NEXUS_HOME}/env"
SRC_DIR="${NEXUS_HOME}/src"
WRAPPER_PATH="/usr/local/bin/nexus"
DEFAULT_REPO_URL="https://github.com/Ezequiel135/Nexus-Agent.git"
REPO_URL="${NEXUS_REPO_URL:-${DEFAULT_REPO_URL}}"
PROJECT_SOURCE="$(pwd)"

echo "[1/6] Verificando Python 3.10+"
python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

echo "[2/6] Instalando dependencias de sistema"
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip python3-dev python3-tk scrot xdotool tesseract-ocr

echo "[3/6] Preparando diretorios do NEXUS AGENT"
mkdir -p "${NEXUS_HOME}"
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
"${ENV_DIR}/bin/pip" install -r "${SRC_DIR}/requirements.txt"

echo "[6/6] Criando wrapper global"
sudo tee "${WRAPPER_PATH}" >/dev/null <<EOF
#!/usr/bin/env bash
exec "${ENV_DIR}/bin/python" "${SRC_DIR}/main.py" "\$@"
EOF
sudo chmod +x "${WRAPPER_PATH}"

echo "Instalacao concluida. NEXUS AGENT criado por Ezequiel 135. Rode: nexus start"
