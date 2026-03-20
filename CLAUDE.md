# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`h9s` is a k9s-style terminal dashboard for managing Helm releases on Kubernetes, built with Python and the Textual TUI framework.

## Development Commands

```bash
# Install in development mode (from project root)
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Run the app
python -m helm_dashboard
# or after install:
helm-dashboard

# Lint
ruff check .

# Type check
mypy helm_dashboard/

# Tests
pytest

# Run a single test
pytest tests/path/to/test_file.py::test_function_name
```

## Architecture

The codebase has two layers:

**`helm_dashboard/helm_client.py`** — Async CLI wrapper. All Helm/kubectl operations are executed here as subprocesses via `asyncio.create_subprocess_exec`. Returns typed dataclasses (`HelmRelease`, `HelmRevision`, `HelmRepo`, `HelmChart`) and uses `ReleaseStatus` enum. No direct Kubernetes library dependencies — everything goes through the `helm` and `kubectl` binaries with JSON/YAML output.

**`helm_dashboard/app.py`** — Textual TUI app (`HelmDashboard(App)`). Uses reactive properties (`current_context`, `selected_namespace`, `releases`, `selected_release`, `search_filter`) that auto-trigger UI re-renders. Heavy operations run via Textual's `@work` decorator (async workers) to keep the UI responsive. When a release is selected, `load_release_details()` fires 5 concurrent `helm_client` calls via `asyncio.gather()`. Modal screens (`ConfirmDialog`, `InputDialog`, `HelpScreen`, `RepoScreen`) are defined in the same file. Textual CSS is embedded inline at the bottom of `app.py`.

**Data flow:** Keyboard event → Textual event handler → `@work` async method → `helm_client` function → subprocess → parsed JSON/YAML → Rich `Syntax`/`Table` objects → rendered in tabs.

## External Dependencies

Requires `helm` (v3) binary on PATH. `kubectl` is optional but needed for the Resources tab (fetches pods/services via label selectors from Helm metadata). The app launches gracefully if either is missing, with warnings.

## Code Style

- Line length: 100 characters (ruff config)
- Target: Python 3.11+
- Type hints expected throughout; mypy is available but not configured in strict mode
- Timeout defaults: 30s for most commands, 60s for repo updates (`helm_client.py`)
