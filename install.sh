#!/usr/bin/env bash
# ─── Helm Dashboard Installer ───────────────────────────────────────
# Installs the helm-dashboard TUI tool on macOS / Linux.
#
# Usage:
#   chmod +x install.sh && ./install.sh
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$*"; exit 1; }

# ── Pre-flight checks ───────────────────────────────────────────────

info "Checking prerequisites..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo "$PY" | cut -d. -f1)
    MINOR=$(echo "$PY" | cut -d. -f2)
    if (( MAJOR < 3 || (MAJOR == 3 && MINOR < 11) )); then
        fail "Python 3.11+ required (found $PY). Install via: brew install python@3.12"
    fi
    ok "Python $PY found"
else
    fail "Python 3 not found. Install via: brew install python@3.12"
fi

# helm
if command -v helm &>/dev/null; then
    ok "Helm $(helm version --short 2>/dev/null || echo 'found')"
else
    warn "Helm not found. Install via: brew install helm"
    warn "The dashboard will start but won't be able to fetch data."
fi

# kubectl
if command -v kubectl &>/dev/null; then
    ok "kubectl found"
else
    warn "kubectl not found. Some features (resources view) may not work."
fi

# ── Create virtual environment ───────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

if [ -d "$VENV_DIR" ] && [ ! -f "${VENV_DIR}/bin/activate" ]; then
    warn "Existing virtual environment is broken (missing activate script). Recreating..."
    python3 -m venv --clear "$VENV_DIR"
    ok "Virtual environment recreated at ${VENV_DIR}"
elif [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created at ${VENV_DIR}"
else
    ok "Virtual environment already exists"
fi

source "${VENV_DIR}/bin/activate"

# ── Install dependencies ─────────────────────────────────────────────

info "Installing dependencies..."
pip install --upgrade pip setuptools -q
pip install -e "${SCRIPT_DIR}" -q
ok "Dependencies installed"

# ── Create launcher script ───────────────────────────────────────────

LAUNCHER="${SCRIPT_DIR}/helm-dashboard"

cat > "$LAUNCHER" << 'SCRIPT'
#!/usr/bin/env bash
# Launcher for Helm Dashboard
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/.venv/bin/activate"
python -m helm_dashboard "$@"
SCRIPT

chmod +x "$LAUNCHER"
ok "Launcher created: ${LAUNCHER}"

# ── Optional: symlink to PATH ────────────────────────────────────────

echo ""
info "Installation complete!"
echo ""
printf "  ${GREEN}To run:${NC}\n"
printf "    cd %s && ./helm-dashboard\n" "$SCRIPT_DIR"
echo ""
printf "  ${GREEN}Or add to PATH:${NC}\n"
printf "    ln -sf %s/helm-dashboard /usr/local/bin/helm-dashboard\n" "$SCRIPT_DIR"
echo ""
printf "  ${GREEN}Then just run:${NC}\n"
printf "    helm-dashboard\n"
echo ""
printf "  ${CYAN}Keyboard shortcuts:${NC} Press ${YELLOW}?${NC} inside the app for help.\n"
echo ""
