# ⎈ Helm Dashboard — Terminal UI

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

## Prerequisites

| Tool | Required | Notes |
|------|----------|-------|
| Python 3.11+ | ✅ | `brew install python@3.12` |
| Helm 3 | ✅ | `brew install helm` |
| kubectl | Recommended | Needed for Resources, Logs, Events, and Describe tabs |

## Installation

### Option 1 — One-command installer (recommended)

```bash
git clone <repo-url> helm-dashboard
cd helm-dashboard
chmod +x install.sh && ./install.sh
```

The installer creates a virtual environment, installs all dependencies, and places a `helm-dashboard` launcher script in the project root.

```bash
./helm-dashboard
```

### Option 2 — pip install (editable)

```bash
git clone <repo-url> helm-dashboard
cd helm-dashboard
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
helm-dashboard                   # registered entry point
# or: python -m helm_dashboard
```

### Option 3 — pip install (non-editable)

```bash
pip install .
helm-dashboard
```

### Dependencies

All Python dependencies are declared in `pyproject.toml` and installed automatically:

| Package | Version | Purpose |
|---------|---------|---------|
| `textual` | ≥ 0.85 | TUI framework |
| `rich` | ≥ 13.0 | Syntax highlighting, rich text |
| `pyyaml` | ≥ 6.0 | YAML parsing for manifest/values diff |

No Kubernetes SDK is required — the app communicates with Helm and kubectl entirely through their CLI binaries.

## Usage

```bash
helm-dashboard          # uses current kubeconfig context
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
helm-dashboard/
├── pyproject.toml              # Project metadata & dependencies
├── install.sh                  # One-command installer
├── README.md
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

The app communicates with Helm and kubectl entirely through their CLI binaries (JSON/YAML output mode), keeping it lightweight and dependency-free beyond Python + Textual. All subprocess calls are async, so the UI never blocks.

## License

MIT
