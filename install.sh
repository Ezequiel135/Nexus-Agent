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
AUTO_INSTALL_DEPS="${NEXUS_AUTO_INSTALL_DEPS:-1}"

# Cores
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}╔══ NEXUS AGENT INSTALLER 26.1.0 ══╗${NC}"
echo -e "${CYAN}║  Criado por Ezequiel 135          ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════╝${NC}"
echo ""

# OS Detection
OS=""
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO="${NAME:-Linux}"
        echo -e "${GREEN}[OS]${NC} Linux — $DISTRO"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo -e "${GREEN}[OS]${NC} macOS"
else
    OS="unknown"
    echo -e "${YELLOW}[OS]${NC} Sistema nao detectado (${OSTYPE}). Continuando..."
fi

# Python detection — tenta varias variantes
PYTHON=""
for p in python3 python python3.10 python3.11 python3.12; do
    if command -v "$p" >/dev/null 2>&1; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}ERRO:${NC} Python nao encontrado. Instale Python 3.10+ primeiro."
    if [ "$OS" = "linux" ]; then
        echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
        echo "  Fedora: sudo dnf install python3"
    elif [ "$OS" = "macos" ]; then
        echo "  HomeBrew: brew install python3"
    fi
    exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}[Python]${NC} $PYTHON — versao $PY_VERSION"

# Checa 3.10+
IFS='.' read -r MAJOR MINOR _ <<< "$PY_VERSION"
if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo -e "${RED}ERRO:${NC} Python 3.10+ necessario. Versao detectada: $PY_VERSION"
    exit 1
fi

echo -e "[1/5] Verificando dependencias de sistema..."

# Dependencias opcionais — avisa mas nao falha
if [ "$OS" = "linux" ]; then
    MISSING_DEPS=()
    if command -v dpkg >/dev/null 2>&1; then
        for dep in git python3-venv python3-pip scrot xdotool tesseract-ocr; do
            if ! dpkg -s "$dep" >/dev/null 2>&1; then
                MISSING_DEPS+=("$dep")
            fi
        done
    else
        for dep in git scrot xdotool tesseract; do
            if ! command -v "$dep" >/dev/null 2>&1; then
                MISSING_DEPS+=("$dep")
            fi
        done
    fi
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${YELLOW}Aviso:${NC} Dependencias faltando: ${MISSING_DEPS[*]}"
        if [ "${AUTO_INSTALL_DEPS}" = "1" ] && command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
            echo "  Tentando instalar automaticamente com sudo apt-get..."
            if sudo apt-get update && sudo apt-get install -y "${MISSING_DEPS[@]}"; then
                echo -e "${GREEN}[OK]${NC} Dependencias do sistema instaladas automaticamente."
            else
                echo -e "${YELLOW}[WARN]${NC} Instalacao automatica falhou."
                echo "  Instale manualmente com: sudo apt install ${MISSING_DEPS[*]}"
                read -p "Continuar mesmo assim? (s/N) " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Ss]$ ]]; then
                    exit 1
                fi
            fi
        else
            echo "  Instale com o gerenciador de pacotes da sua distro."
            if command -v apt-get >/dev/null 2>&1; then
                echo "  Exemplo Debian/Ubuntu: sudo apt install ${MISSING_DEPS[*]}"
            fi
            echo "  Defina NEXUS_AUTO_INSTALL_DEPS=1 para tentativa automatica em sistemas com apt-get."
            echo "  O NEXUS ainda funciona, mas recursos visuais poderao faltar."
            read -p "Continuar mesmo assim? (s/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Ss]$ ]]; then
                exit 1
            fi
        fi
    fi
fi

echo -e "[2/5] Preparando diretorios..."
mkdir -p "${NEXUS_HOME}"
mkdir -p "${LOCAL_BIN_DIR}"

# Limpa wrapper antigo se for genuino
if [ -x "${GLOBAL_WRAPPER_PATH}" ] && ! grep -q "NEXUS AGENT WRAPPER" "${GLOBAL_WRAPPER_PATH}" 2>/dev/null; then
    if [ -w /usr/local/bin ]; then
        LEGACY_BACKUP="/usr/local/bin/nexus.legacy.$(date +%s).bak"
        mv "${GLOBAL_WRAPPER_PATH}" "${LEGACY_BACKUP}" || true
        echo -e "${YELLOW}[WARN]${NC} Wrapper antigo movido para ${LEGACY_BACKUP}"
    elif command -v sudo >/dev/null 2>&1 && sudo -n test -w /usr/local/bin 2>/dev/null; then
        LEGACY_BACKUP="/usr/local/bin/nexus.legacy.$(date +%s).bak"
        sudo mv "${GLOBAL_WRAPPER_PATH}" "${LEGACY_BACKUP}" || true
        echo -e "${YELLOW}[WARN]${NC} Wrapper antigo movido para ${LEGACY_BACKUP}"
    fi
fi

echo -e "[3/5] Clonando Nexus-Agent..."
rm -rf "${SRC_DIR}"
if [ -n "${NEXUS_LOCAL_SRC:-}" ] && [ -d "${NEXUS_LOCAL_SRC}/.git" ]; then
    echo "  Usando fonte local de ${NEXUS_LOCAL_SRC}"
    cp -r "${NEXUS_LOCAL_SRC}" "${SRC_DIR}"
else
    echo "  Clonando de ${REPO_URL} ..."
    git clone --depth=1 "${REPO_URL}" "${SRC_DIR}" || {
        echo -e "${RED}ERRO:${NC} Clone falhou. Verifique sua conexao ou token."
        echo "  Dica: use NEXUS_REPO_URL='https://TOKEN@github.com/...'"
        exit 1
    }
fi
printf '%s\n' "${REPO_URL}" > "${NEXUS_HOME}/repo.txt"

echo -e "[4/5] Criando ambiente virtual..."
$PYTHON -m venv "${ENV_DIR}"
"${ENV_DIR}/bin/pip" install --upgrade pip setuptools wheel

echo -e "[5/5] Instalando dependencias Python..."
if ! "${ENV_DIR}/bin/pip" install -r "${SRC_DIR}/requirements.txt" 2>/dev/null; then
    echo -e "${YELLOW}[WARN]${NC} requirements.txt completo falhou. Instalando conjunto minimo..."
    "${ENV_DIR}/bin/pip" install rich litellm requests python-dotenv psutil textual nbformat nbclient ipykernel
fi

echo ""
echo -e "[6/6] Criando wrapper local..."

# Wrapper em ~/.local/bin (garante prioridade sobre /usr/local/bin)
cat > "${WRAPPER_PATH}" <<'EOF'
#!/usr/bin/env bash
# NEXUS AGENT WRAPPER 26.1.0
export NEXUS_HOME="${HOME}/.nexus"
exec "${NEXUS_HOME}/env/bin/python" "${NEXUS_HOME}/src/main.py" "$@"
EOF
chmod +x "${WRAPPER_PATH}"

# Wrapper global opcional
if [ "${NEXUS_INSTALL_GLOBAL:-0}" = "1" ]; then
    echo "  Criando wrapper global em ${GLOBAL_WRAPPER_PATH}..."
    sudo tee "${GLOBAL_WRAPPER_PATH}" > /dev/null <<'EOF'
#!/usr/bin/env bash
# NEXUS AGENT WRAPPER 26.1.0 — global
export NEXUS_HOME="${HOME}/.nexus"
exec "${NEXUS_HOME}/env/bin/python" "${NEXUS_HOME}/src/main.py" "$@"
EOF
    sudo chmod +x "${GLOBAL_WRAPPER_PATH}"
fi

# PATH check
if ! printf '%s' ":$PATH:" | grep -q ":${LOCAL_BIN_DIR}:"; then
    if [ -f "${HOME}/.bashrc" ]; then
        if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "${HOME}/.bashrc"; then
            printf '\n# Nexus Agent\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "${HOME}/.bashrc"
            echo -e "${GREEN}[PATH]${NC} ~/.local/bin adicionado ao .bashrc"
        fi
    fi
    if [ -f "${HOME}/.zshrc" ]; then
        if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "${HOME}/.zshrc"; then
            printf '\n# Nexus Agent\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "${HOME}/.zshrc"
            echo -e "${GREEN}[PATH]${NC} ~/.local/bin adicionado ao .zshrc"
        fi
    fi
fi

echo ""
echo -e "${GREEN}╔═══ INSTALACAO CONCLUIDA ═══╗${NC}"
echo -e "${GREEN}║  NEXUS AGENT 26.1.0        ║${NC}"
echo -e "${GREEN}╚════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Como usar:${NC}"
echo "  1. Abra um NOVO terminal ou ${YELLOW}source ~/.bashrc${NC}"
echo "  2. Execute: ${YELLOW}nexus${NC}"
echo "  3. Na primeira abertura, escolha a UI (Visual ou Plain) e conclua o setup"
echo "  4. Se quiser forcar o terminal puro: ${YELLOW}nexus start --plain${NC}"
echo "  5. Se outro programa abrir no lugar, confira: ${YELLOW}type -a nexus${NC}"
echo ""
echo -e "${GREEN}Ezequiel 135${NC}"
