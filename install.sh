#!/usr/bin/env bash
# ─── H9S Installer ────────────────────────────────────────────────────────────
#
# Installs H9S — a k9s-style terminal UI for Helm releases.
#
# Usage (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/razvanbalsan/h9s/main/install.sh | bash
#
# Or locally:
#   chmod +x install.sh && ./install.sh
#
# The script tries to install a pre-built binary first (fast, no Python required).
# Falls back to pip install into a venv if no binary is available for this platform.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO="razvanbalsan/h9s"
INSTALL_DIR="${H9S_INSTALL_DIR:-/usr/local/bin}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[ OK ]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$*" >&2; exit 1; }

# ── Detect platform ────────────────────────────────────────────────────────────

OS="$(uname -s)"
ARCH="$(uname -m)"

case "${OS}" in
  Darwin)
    case "${ARCH}" in
      arm64)  ARTIFACT="h9s-macos-arm64" ;;
      x86_64) ARTIFACT="h9s-macos-x86_64" ;;
      *)      ARTIFACT="" ;;
    esac
    ;;
  *)
    ARTIFACT=""
    ;;
esac

# ── Fetch latest release tag ───────────────────────────────────────────────────

get_latest_tag() {
  if command -v curl &>/dev/null; then
    curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
      | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\(.*\)".*/\1/'
  elif command -v wget &>/dev/null; then
    wget -qO- "https://api.github.com/repos/${REPO}/releases/latest" \
      | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\(.*\)".*/\1/'
  else
    echo ""
  fi
}

# ── Install pre-built binary ───────────────────────────────────────────────────

install_binary() {
  local tag="$1"
  local url="https://github.com/${REPO}/releases/download/${tag}/${ARTIFACT}"

  info "Downloading ${ARTIFACT} (${tag})..."
  tmp="$(mktemp)"
  if command -v curl &>/dev/null; then
    curl -fsSL "$url" -o "$tmp"
  else
    wget -qO "$tmp" "$url"
  fi

  # Write to install dir (may need sudo)
  TARGET="${INSTALL_DIR}/h9s"
  if [ -w "$INSTALL_DIR" ]; then
    mv "$tmp" "$TARGET"
  else
    info "Writing to ${INSTALL_DIR} requires sudo..."
    sudo mv "$tmp" "$TARGET"
  fi
  chmod +x "$TARGET"
  ok "Installed binary to ${TARGET}"
}

# ── Fallback: pip into venv ────────────────────────────────────────────────────

install_from_source() {
  info "Installing from source via pip..."

  # Require Python 3.11+
  if ! command -v python3 &>/dev/null; then
    fail "Python 3.11+ is required. Install via: brew install python@3.12"
  fi

  PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')
  if [ "$PY_VER" -lt 311 ] 2>/dev/null; then
    fail "Python 3.11+ required (found $(python3 --version)). Install via: brew install python@3.12"
  fi

  VENV_DIR="${HOME}/.h9s/venv"
  mkdir -p "$(dirname "$VENV_DIR")"
  python3 -m venv "$VENV_DIR"
  "${VENV_DIR}/bin/pip" install --upgrade pip -q
  "${VENV_DIR}/bin/pip" install "git+https://github.com/${REPO}.git" -q
  ok "Installed into ${VENV_DIR}"

  # Write launcher
  TARGET="${INSTALL_DIR}/h9s"
  LAUNCHER="#!/usr/bin/env bash
exec \"${VENV_DIR}/bin/python\" -m helm_dashboard \"\$@\""

  if [ -w "$INSTALL_DIR" ]; then
    printf '%s\n' "$LAUNCHER" > "$TARGET"
  else
    info "Writing to ${INSTALL_DIR} requires sudo..."
    echo "$LAUNCHER" | sudo tee "$TARGET" > /dev/null
  fi
  chmod +x "$TARGET"
  ok "Launcher written to ${TARGET}"
}

# ── Check prerequisites (non-fatal warnings) ───────────────────────────────────

check_prereqs() {
  if command -v helm &>/dev/null; then
    ok "helm $(helm version --short 2>/dev/null | head -1)"
  else
    warn "helm not found — install via: brew install helm"
  fi

  if command -v kubectl &>/dev/null; then
    ok "kubectl found"
  else
    warn "kubectl not found — some tabs (Resources, Events) will be unavailable"
  fi
}

# ── Main ───────────────────────────────────────────────────────────────────────

echo ""
printf "${CYAN}⎈ H9S Installer${NC}\n"
echo "──────────────────────────────────────────"
echo ""

check_prereqs
echo ""

TAG="$(get_latest_tag)"

if [ -n "$ARTIFACT" ] && [ -n "$TAG" ]; then
  install_binary "$TAG"
else
  if [ -z "$ARTIFACT" ]; then
    warn "No pre-built binary for ${OS}/${ARCH} — falling back to pip install"
  else
    warn "Could not determine latest release tag — falling back to pip install"
  fi
  install_from_source
fi

echo ""
printf "${GREEN}✓ H9S installed successfully!${NC}\n"
echo ""
printf "  Run:  ${YELLOW}h9s${NC}\n"
echo ""
printf "  Make sure ${INSTALL_DIR} is in your PATH.\n"
printf "  Press ${YELLOW}?${NC} inside the app for keyboard shortcuts.\n"
echo ""
