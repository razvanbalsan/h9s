# ⎈ H9S — Terminal UI for Helm

A **k9s-style** terminal dashboard for managing Helm releases on Kubernetes, built with Python and [Textual](https://textual.textualize.io/).

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Features

- **Release Overview** — list all Helm releases across namespaces with live status indicators
- **Multi-Namespace Filtering** — select one, many, or all namespaces at once
- **Fuzzy Search** — filter releases by name, namespace, chart, or app version
- **Context Switching** — switch between Kubernetes contexts without leaving the dashboard
- **Auto-Refresh** — cycle through 30s / 1m / 5m refresh intervals
- **Release Details** — tabbed panels: Overview, History, Values, Manifest, Resources, Notes, Hooks, Events
- **Revision History** — view all revisions with status, chart version, and descriptions
- **Values Inspector** — YAML syntax-highlighted view with diff between any two revisions
- **Manifest Viewer** — full rendered Kubernetes manifest with syntax highlighting
- **K8s Resources** — live view of pods, services, and deployments belonging to a release
- **Pod Log Viewer** — stream and browse logs for any pod in a release
- **kubectl Describe** — describe any Kubernetes resource without leaving the TUI
- **Upgrade Indicator** — ⬆ flag on releases that have a newer chart version available in your repos
- **One-Key Rollback** — rollback to the previous revision with confirmation
- **Uninstall** — remove releases with safety confirmation
- **Repository Management** — add, remove, and update Helm repos from a dedicated screen
- **Keyboard-Driven** — full keyboard navigation inspired by k9s and htop

## Requirements

| Tool | Required | Notes |
|------|----------|-------|
| helm 3 | ✅ | `brew install helm` |
| kubectl | Recommended | Needed for Resources, Logs, Events, and Describe tabs |
| Python 3.11+ | Only for source installs | `brew install python@3.12` |

## Installation

### Homebrew (recommended)

```bash
brew tap razvanbalsan/h9s https://github.com/razvanbalsan/h9s
brew install h9s
```

### curl one-liner

Downloads the pre-built binary for your platform, falls back to pip if no binary is available:

```bash
curl -fsSL https://raw.githubusercontent.com/razvanbalsan/h9s/main/install.sh | bash
```

To install to a custom location (default is `/usr/local/bin`):

```bash
H9S_INSTALL_DIR=~/.local/bin curl -fsSL \
  https://raw.githubusercontent.com/razvanbalsan/h9s/main/install.sh | bash
```

### Direct binary download (macOS)

Pick the binary that matches your Mac from the [latest release](https://github.com/razvanbalsan/h9s/releases/latest):

**Apple Silicon (M1 / M2 / M3)**
```bash
curl -L https://github.com/razvanbalsan/h9s/releases/latest/download/h9s-macos-arm64 \
  -o /usr/local/bin/h9s && chmod +x /usr/local/bin/h9s
```

**Intel Mac**
```bash
curl -L https://github.com/razvanbalsan/h9s/releases/latest/download/h9s-macos-x86_64 \
  -o /usr/local/bin/h9s && chmod +x /usr/local/bin/h9s
```

### pipx

```bash
pipx install git+https://github.com/razvanbalsan/h9s.git
```

### From source

```bash
git clone https://github.com/razvanbalsan/h9s.git
cd h9s
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
h9s
```

## Usage

```bash
h9s          # uses current kubeconfig context
```

On startup the dashboard loads all releases in the current context. Use `n` to open the namespace selector and `c` to switch context.

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `↑/↓` or `k/j` | Navigate release list |
| `Enter` | Open release detail |
| `/` | Focus search filter |
| `n` | Open namespace selector (multi-select) |
| `c` | Switch Kubernetes context |
| `r` | Refresh releases |
| `A` | Cycle auto-refresh interval (off → 30s → 1m → 5m) |
| `B` | Rollback selected release |
| `D` | Uninstall selected release |
| `R` | Open repo management screen |
| `U` | Update all Helm repos |
| `?` | Show help |
| `q` | Quit |

### Release Detail (tabs 1–8)

| Key | Action |
|-----|--------|
| `1` | Overview tab |
| `2` | History tab |
| `3` | Values tab |
| `4` | Manifest tab |
| `5` | Resources tab |
| `6` | Notes tab |
| `7` | Hooks tab |
| `8` | Events tab |
| `l` | Open pod log viewer |
| `v` | Diff values between selected history revision and current |
| `Esc` | Close / go back |

### Namespace Selector

| Key | Action |
|-----|--------|
| `Space` | Toggle namespace selection |
| `Enter` | Confirm selection |
| `Esc` | Cancel |

## Architecture

```
h9s/
├── pyproject.toml              # Package metadata & dependencies
├── h9s.spec                    # PyInstaller build spec
├── install.sh                  # curl-installable installer
├── Formula/h9s.rb              # Homebrew formula
├── .github/workflows/
│   └── release.yml             # CI: build binaries + create GitHub Release on tag push
├── tests/
│   └── test_helm_client.py
└── helm_dashboard/
    ├── __init__.py
    ├── __main__.py             # python -m entry point
    ├── app.py                  # Main TUI application (Textual)
    ├── helm_client.py          # Async Helm/kubectl CLI wrapper
    └── screens/
        ├── __init__.py
        ├── context.py          # Context switcher modal
        ├── describe.py         # kubectl describe viewer
        ├── detail.py           # Release detail (8 tabs)
        ├── dialogs.py          # Confirm / Input dialogs
        ├── help.py             # Help overlay
        ├── logs.py             # Pod log viewer
        ├── namespace.py        # Multi-namespace selector
        └── repos.py            # Helm repo management
```

The app communicates with Helm and kubectl entirely through their CLI binaries (JSON/YAML output mode). All subprocess calls are async — the UI never blocks.

## Release process

Releases are fully automated via GitHub Actions:

1. Tag a commit: `git tag v1.x.x && git push origin v1.x.x`
2. The workflow builds native binaries for macOS arm64 and x86_64 using PyInstaller
3. A GitHub Release is created with the binaries and SHA256 checksums attached
4. Update `Formula/h9s.rb` with the new tarball URL and SHA256 to publish via Homebrew

## License

MIT
