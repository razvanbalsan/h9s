# ⎈ Helm Dashboard — Terminal UI

A **k9s-style** terminal dashboard for managing Helm releases on Kubernetes, built with Python and [Textual](https://textual.textualize.io/).

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Features

- **Release Overview** — list all Helm releases across namespaces with live status indicators
- **Namespace Filtering** — cycle through namespaces with a single keypress
- **Fuzzy Search** — filter releases by name, namespace, chart, or app version
- **Release Details** — tabbed panels for overview, history, values, manifests, resources, and notes
- **Revision History** — view all revisions with status and descriptions
- **Values Inspector** — YAML syntax-highlighted view of user-supplied and computed values
- **Manifest Viewer** — full rendered Kubernetes manifest with syntax highlighting
- **K8s Resources** — live view of pods, services, and deployments belonging to a release
- **One-Key Rollback** — rollback to the previous revision with confirmation
- **Uninstall** — remove releases with safety confirmation
- **Repository Management** — add, remove, update Helm repos from a dedicated screen
- **Keyboard-Driven** — full keyboard navigation inspired by k9s and htop

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| Python 3.11+ | ✅ | `brew install python@3.12` |
| Helm 3 | ✅ | `brew install helm` |
| kubectl | Recommended | `brew install kubectl` |

## Quick Start

```bash
# Clone or download the project
cd helm-dashboard

# Run the installer (creates venv, installs deps, creates launcher)
chmod +x install.sh && ./install.sh

# Launch
./helm-dashboard
```

### Manual Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m helm_dashboard
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑/↓` or `k/j` | Navigate release list |
| `Enter` | Select release |
| `Tab` | Switch panels |
| `1`–`6` | Switch detail tab (Overview/History/Values/Manifest/Resources/Notes) |
| `/` | Focus search filter |
| `n` | Cycle namespace |
| `r` | Refresh releases |
| `B` | Rollback selected release |
| `D` | Uninstall selected release |
| `R` | Open repo management |
| `U` | Update all repos |
| `?` | Show help |
| `q` | Quit |

## Architecture

```
helm-dashboard/
├── pyproject.toml          # Project metadata & dependencies
├── install.sh              # One-command installer
├── README.md
└── helm_dashboard/
    ├── __init__.py
    ├── __main__.py         # python -m entry point
    ├── app.py              # Main TUI application (Textual)
    └── helm_client.py      # Async Helm/kubectl CLI wrapper
```

The app communicates with Helm entirely through the `helm` CLI (JSON output mode), keeping it lightweight and dependency-free beyond Python + Textual. All subprocess calls are async, so the UI never blocks.

## License

MIT
