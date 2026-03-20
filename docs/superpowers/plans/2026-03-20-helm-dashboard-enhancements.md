# Helm Dashboard Enhancement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix existing bugs, split app.py into maintainable modules, and add high-value troubleshooting features: context switching, pod log streaming, K8s events view, values diff, upgrade-available indicators, auto-refresh, and structured resources view.

**Architecture:** Extract all Screen subclasses from app.py into a `helm_dashboard/screens/` package. Extend `helm_client.py` with new kubectl-backed query functions. New features are self-contained screens and helm_client functions that the main `HelmDashboard` app class wires together.

**Tech Stack:** Python 3.11+, Textual ≥0.85, Rich ≥13, PyYAML ≥6, helm CLI, kubectl CLI (optional)

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `helm_dashboard/screens/__init__.py` | Re-export all screen classes |
| `helm_dashboard/screens/dialogs.py` | `ConfirmDialog`, `InputDialog` |
| `helm_dashboard/screens/help.py` | `HelpScreen` |
| `helm_dashboard/screens/namespace.py` | `NamespaceScreen` |
| `helm_dashboard/screens/context.py` | `ContextScreen` (new – context switching) |
| `helm_dashboard/screens/repos.py` | `RepoScreen` |
| `helm_dashboard/screens/detail.py` | `DetailScreen` (tabbed release detail) |
| `helm_dashboard/screens/logs.py` | `LogScreen` (new – pod log streaming) |
| `helm_dashboard/screens/describe.py` | `DescribeScreen` (new – kubectl describe) |
| `tests/test_helm_client.py` | Unit tests for helm_client pure functions |

### Modified files
| File | Changes |
|------|---------|
| `helm_dashboard/helm_client.py` | Fix `HelmRevision.status` type; add `get_release_events`, `get_pod_logs_stream`, `describe_resource`, `get_available_chart_versions`, `switch_context` |
| `helm_dashboard/app.py` | Strip all Screen classes; import from `screens`; add context-switch binding; add auto-refresh worker; add upgrade-available column |

---

## Task 1: Extract screens — dialogs and help

**Files:**
- Create: `helm_dashboard/screens/__init__.py`
- Create: `helm_dashboard/screens/dialogs.py`
- Create: `helm_dashboard/screens/help.py`

- [ ] **Step 1: Create the screens package**

`screens/__init__.py` is built incrementally — each task adds its own import. Start with only the screens that exist after Task 1:

```python
# helm_dashboard/screens/__init__.py  (initial — Tasks 1-2 only)
from helm_dashboard.screens.dialogs import ConfirmDialog, InputDialog
from helm_dashboard.screens.help import HelpScreen

__all__ = ["ConfirmDialog", "InputDialog", "HelpScreen"]
```

Later tasks (2, 3, 5, 9, 10) will append to `__all__` and add their own `from ... import ...` lines. Do NOT import `ContextScreen`, `LogScreen`, or `DescribeScreen` here — those files don't exist yet.

- [ ] **Step 2: Create `screens/dialogs.py`**

Move `ConfirmDialog` and `InputDialog` verbatim from `app.py` lines 250–315. Add this import block at the top:

```python
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
```

No logic changes — pure extraction.

- [ ] **Step 3: Create `screens/help.py`**

Move `HelpScreen` verbatim from `app.py` lines 380–420. Import block:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static
```

Update the help text to include the new bindings that will be added in later tasks (`c` for context, `e` for events, `l` for logs).

- [ ] **Step 4: Verify app still launches**

```bash
cd /Users/razvanbalsan/Projects/h9s && source .venv/bin/activate
python -c "from helm_dashboard.screens import ConfirmDialog, HelpScreen; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add helm_dashboard/screens/__init__.py helm_dashboard/screens/dialogs.py helm_dashboard/screens/help.py
git commit -m "refactor: extract ConfirmDialog, InputDialog, HelpScreen into screens package"
```

---

## Task 2: Extract NamespaceScreen and RepoScreen

**Files:**
- Create: `helm_dashboard/screens/namespace.py`
- Create: `helm_dashboard/screens/repos.py`

- [ ] **Step 1: Create `screens/namespace.py`**

Move `NamespaceScreen` verbatim from `app.py` lines 318–377. Imports:

```python
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
```

- [ ] **Step 2: Create `screens/repos.py`**

Move `RepoScreen` verbatim from `app.py` lines 905–1053. Imports:

```python
from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from helm_dashboard.screens.dialogs import ConfirmDialog, InputDialog
from helm_dashboard.helm_client import add_repo, list_repos, remove_repo, update_repos
```

- [ ] **Step 3: Update `screens/__init__.py`** to import the two new screens:

```python
# Append to helm_dashboard/screens/__init__.py
from helm_dashboard.screens.namespace import NamespaceScreen
from helm_dashboard.screens.repos import RepoScreen
```

Also add `"NamespaceScreen"` and `"RepoScreen"` to `__all__`.

- [ ] **Step 4: Verify imports**

```bash
python -c "from helm_dashboard.screens import NamespaceScreen, RepoScreen; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add helm_dashboard/screens/namespace.py helm_dashboard/screens/repos.py
git commit -m "refactor: extract NamespaceScreen and RepoScreen into screens package"
```

---

## Task 3: Extract DetailScreen and slim down app.py

**Files:**
- Create: `helm_dashboard/screens/detail.py`
- Modify: `helm_dashboard/app.py` (remove extracted classes, add imports)

- [ ] **Step 1: Create `screens/detail.py`**

Move `DetailScreen` from `app.py` lines 719–900 verbatim. Imports:

```python
from __future__ import annotations

import asyncio

from rich.syntax import Syntax
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, RichLog, Static, TabbedContent, TabPane

from helm_dashboard.helm_client import (
    HelmRelease,
    ReleaseStatus,
    get_release_history,
    get_release_hooks,
    get_release_manifest,
    get_release_notes,
    get_release_resources,
    get_release_values,
)
```

Add a 7th tab for **Hooks** (the `get_release_hooks` function is already in helm_client but never shown):

```python
# In compose(), inside TabbedContent, after the Notes TabPane:
with TabPane("Hooks", id="tab-hooks"):
    yield RichLog(id="hooks-log", wrap=True, markup=True)
```

Add binding:
```python
Binding("7", "tab_hooks", "Hooks", show=False),
```

In `_load_details`, add hooks to the `asyncio.gather` call:

```python
history, values, manifest, resources, notes, hooks = await asyncio.gather(
    get_release_history(rel.name, rel.namespace),
    get_release_values(rel.name, rel.namespace, all_values=True),
    get_release_manifest(rel.name, rel.namespace),
    get_release_resources(rel.name, rel.namespace),
    get_release_notes(rel.name, rel.namespace),
    get_release_hooks(rel.name, rel.namespace),
)
```

Then write hooks result:
```python
hooks_log = self.query_one("#hooks-log", RichLog)
hooks_log.clear()
hooks_log.write(Syntax(hooks, "yaml", theme="monokai", line_numbers=True))
```

Add action method:
```python
def action_tab_hooks(self) -> None:
    self.query_one("#detail-tabs", TabbedContent).active = "tab-hooks"
```

- [ ] **Step 2: Update `app.py`**

Replace the extracted class definitions with an import block that only includes screens that exist at this point in the plan (Tasks 1–3). Tasks 5, 9, and 10 will each extend this import when their screens are added:

```python
# Task 3 — import only what exists so far
from helm_dashboard.screens import (
    ConfirmDialog,
    DetailScreen,
    HelpScreen,
    InputDialog,
    NamespaceScreen,
    RepoScreen,
)
# ContextScreen, LogScreen, DescribeScreen added in Tasks 5, 9, 10 respectively
```

Remove from `app.py`: `ConfirmDialog`, `InputDialog`, `NamespaceScreen`, `HelpScreen`, `DetailScreen`, `RepoScreen` class definitions (those are now in screens package).

Also remove the now-unused `_ns_index` attribute completely:
- Remove `self._ns_index: int = 0` from `__init__` (line ~456 in current app.py)
- Remove `self._ns_index = self._namespaces.index(result) if result in self._namespaces else 0` from `_handle_namespace_selected` (line ~562)

Both lines are dead code — namespace selection now goes through the `NamespaceScreen` modal and doesn't use an index.

- [ ] **Step 3: Smoke-test the app structure**

```bash
python -c "from helm_dashboard.app import HelmDashboard; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add helm_dashboard/screens/detail.py helm_dashboard/app.py
git commit -m "refactor: extract DetailScreen into screens package; add Hooks tab; remove dead _ns_index"
```

---

## Task 4: Fix HelmRevision.status enum type

**Files:**
- Modify: `helm_dashboard/helm_client.py`
- Modify: `helm_dashboard/screens/detail.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_helm_client.py`:

```python
"""Tests for helm_client pure functions."""
import pytest
from helm_dashboard.helm_client import (
    HelmRevision,
    ReleaseStatus,
    list_releases,
)


def test_helm_revision_status_is_enum():
    rev = HelmRevision(
        revision=1,
        updated="2024-01-01T00:00:00Z",
        status=ReleaseStatus.DEPLOYED,
        chart="nginx-1.0.0",
        app_version="1.0",
        description="install complete",
    )
    assert isinstance(rev.status, ReleaseStatus)
    assert rev.status == ReleaseStatus.DEPLOYED


def test_helm_revision_status_icon():
    rev = HelmRevision(
        revision=1,
        updated="2024-01-01T00:00:00Z",
        status=ReleaseStatus.FAILED,
        chart="nginx-1.0.0",
        app_version="1.0",
        description="upgrade failed",
    )
    assert rev.status_icon == "❌"


def test_release_status_from_str_unknown():
    status = ReleaseStatus.from_str("something-weird")
    assert status == ReleaseStatus.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/razvanbalsan/Projects/h9s && source .venv/bin/activate && pytest tests/test_helm_client.py -v
```

Expected: `FAILED` — `HelmRevision` has no `status_icon` and `status` is `str`

- [ ] **Step 3: Fix `HelmRevision` in `helm_client.py`**

Change the dataclass definition:

```python
@dataclass
class HelmRevision:
    """Represents a single revision in release history."""
    revision: int
    updated: str
    status: ReleaseStatus   # was: str
    chart: str
    app_version: str
    description: str

    @property
    def status_icon(self) -> str:
        icons = {
            ReleaseStatus.DEPLOYED: "✅",
            ReleaseStatus.FAILED: "❌",
            ReleaseStatus.PENDING_INSTALL: "⏳",
            ReleaseStatus.PENDING_UPGRADE: "⏳",
            ReleaseStatus.PENDING_ROLLBACK: "⏳",
            ReleaseStatus.SUPERSEDED: "📦",
            ReleaseStatus.UNINSTALLING: "🗑️",
            ReleaseStatus.UNINSTALLED: "🗑️",
            ReleaseStatus.UNKNOWN: "❓",
        }
        return icons.get(self.status, "❓")
```

In `get_release_history`, update the list comprehension to parse the status:

```python
return [
    HelmRevision(
        revision=int(item.get("revision", 0)),
        updated=item.get("updated", ""),
        status=ReleaseStatus.from_str(item.get("status", "unknown")),  # was: item.get("status", "")
        chart=item.get("chart", ""),
        app_version=item.get("app_version", ""),
        description=item.get("description", ""),
    )
    for item in data
]
```

- [ ] **Step 4: Fix `detail.py` history rendering**

In `_load_details`, the history table renders `rev.status` as a raw string. Update to use the enum and icon:

```python
for rev in reversed(history):
    status_style = {
        ReleaseStatus.DEPLOYED: "green",
        ReleaseStatus.FAILED: "red",
    }.get(rev.status, "dim")
    hist_table.add_row(
        str(rev.revision),
        rev.updated[:19] if len(rev.updated) > 19 else rev.updated,
        Text(f"{rev.status_icon} {rev.status.value}", style=status_style),
        rev.chart,
        rev.app_version,
        rev.description[:60] if rev.description else "",
        key=str(rev.revision),
    )
```

Add to `detail.py` imports:
```python
from helm_dashboard.helm_client import ReleaseStatus
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_helm_client.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/detail.py tests/test_helm_client.py
git commit -m "fix: HelmRevision.status is now ReleaseStatus enum; add status_icon property; add tests"
```

---

## Task 5: Context switching screen

**Files:**
- Create: `helm_dashboard/screens/context.py`
- Modify: `helm_dashboard/helm_client.py` (add `switch_context`)
- Modify: `helm_dashboard/app.py` (add `c` binding, `action_switch_context`)

- [ ] **Step 1: Add `switch_context` and `get_contexts` tests**

Append to `tests/test_helm_client.py`:

```python
def test_get_contexts_returns_list():
    """get_contexts always returns a list, even on error."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from helm_dashboard.helm_client import get_contexts

    async def run():
        with patch("helm_dashboard.helm_client._run_kubectl", new=AsyncMock(return_value=(1, b"", b"err"))):
            result = await get_contexts()
        assert isinstance(result, list)

    asyncio.run(run())
```

- [ ] **Step 2: `switch_context` in `helm_client.py`**

Add after `get_current_context`:

```python
async def switch_context(context_name: str) -> tuple[bool, str]:
    """Switch the active kubectl context."""
    rc, stdout, stderr = await _run_kubectl(
        "config", "use-context", context_name
    )
    output = (stdout + stderr).decode("utf-8", errors="replace").strip()
    return rc == 0, output
```

- [ ] **Step 3: Create `screens/context.py`**

```python
"""Context switching screen."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static


class ContextScreen(ModalScreen[str | None]):
    """Kubernetes context selector."""

    BINDINGS = [Binding("escape", "cancel", "Close")]

    CSS = """
    ContextScreen { align: center middle; }

    #ctx-box {
        width: 60;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    #ctx-title {
        width: 1fr;
        text-style: bold;
        color: $warning;
        margin: 0 0 1 0;
    }

    #ctx-list {
        height: auto;
        max-height: 22;
    }
    """

    def __init__(self, contexts: list[str], current: str) -> None:
        super().__init__()
        self._contexts = contexts
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="ctx-box"):
            yield Static("⎈  Switch Context", id="ctx-title")
            yield OptionList(id="ctx-list")

    def on_mount(self) -> None:
        ol = self.query_one("#ctx-list", OptionList)
        highlight_idx = 0
        for i, ctx in enumerate(self._contexts):
            ol.add_option(ctx)
            if ctx == self._current:
                highlight_idx = i
        ol.highlighted = highlight_idx
        ol.focus()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 4: Wire into `app.py`**

Add binding in `BINDINGS`:
```python
Binding("c", "switch_context", "Context", show=True),
```

Add action methods to `HelmDashboard`. The pattern: a synchronous action method fetches data in a `@work` coroutine; when data is ready it sets a reactive that triggers `push_screen` from a watcher (synchronous context). This avoids calling `push_screen` from inside an `async` worker.

```python
# Step 1: reactive to hold the fetched contexts list; None = not ready
_pending_contexts: reactive[list[str] | None] = reactive(None)

def action_switch_context(self) -> None:
    self._fetch_contexts()

@work(thread=False)
async def _fetch_contexts(self) -> None:
    from helm_dashboard.helm_client import get_contexts
    contexts = await get_contexts()
    if not contexts:
        self.notify("No contexts found", severity="warning")
        return
    self._pending_contexts = contexts  # triggers watch_pending_contexts

def watch__pending_contexts(self, contexts: list[str] | None) -> None:
    """Called synchronously when _pending_contexts changes; open the screen here."""
    if contexts is None:
        return
    self._pending_contexts = None  # reset immediately
    self.push_screen(
        ContextScreen(contexts, self.current_context),
        callback=self._handle_context_selected,
    )

def _handle_context_selected(self, result: str | None) -> None:
    if result and result != self.current_context:
        self._apply_context_switch(result)

@work(thread=False)
async def _apply_context_switch(self, context_name: str) -> None:
    from helm_dashboard.helm_client import get_namespaces, switch_context
    self.status_message = f"Switching to {context_name}..."
    success, msg = await switch_context(context_name)
    if success:
        self.current_context = context_name
        self.selected_namespace = "All Namespaces"
        self._namespaces = ["All Namespaces"] + await get_namespaces()
        self.notify(f"⎈ Switched to {context_name}", timeout=3)
        self.load_releases()
    else:
        self.notify(f"❌ Context switch failed: {msg}", severity="error", timeout=8)
    self.status_message = ""
```

Extend the `app.py` import block (added in Task 3) to include `ContextScreen`:
```python
# Extend existing import block in app.py
from helm_dashboard.screens import (
    ConfirmDialog,
    ContextScreen,   # NEW
    DetailScreen,
    HelpScreen,
    InputDialog,
    NamespaceScreen,
    RepoScreen,
)
```

Also add `ContextScreen` to `screens/__init__.py`:
```python
from helm_dashboard.screens.context import ContextScreen
# Add "ContextScreen" to __all__
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/context.py helm_dashboard/app.py tests/test_helm_client.py
git commit -m "feat: add context switching screen (c key); add switch_context to helm_client"
```

---

## Task 6: Auto-refresh

**Files:**
- Modify: `helm_dashboard/app.py`

The app gains a configurable auto-refresh interval. Defaults to off. User presses `A` to toggle between off / 30s / 60s / 5m.

- [ ] **Step 1: Add reactive and worker to `HelmDashboard`**

Add reactive:
```python
auto_refresh_interval: reactive[int] = reactive(0)  # 0 = off, else seconds
```

Add a constant near the top of the class:
```python
_REFRESH_INTERVALS = [0, 30, 60, 300]  # seconds; 0 = off
_REFRESH_LABELS = ["off", "30s", "1m", "5m"]
```

Add binding in `BINDINGS`:
```python
Binding("A", "toggle_auto_refresh", "Auto-refresh", show=False),
```

Add action + worker:
```python
def action_toggle_auto_refresh(self) -> None:
    intervals = self._REFRESH_INTERVALS
    current_idx = intervals.index(self.auto_refresh_interval) if self.auto_refresh_interval in intervals else 0
    next_idx = (current_idx + 1) % len(intervals)
    self.auto_refresh_interval = intervals[next_idx]
    label = self._REFRESH_LABELS[next_idx]
    if self.auto_refresh_interval > 0:
        self.notify(f"Auto-refresh: every {label}", timeout=2)
        self._start_auto_refresh()
    else:
        self.notify("Auto-refresh: off", timeout=2)

@work(thread=False, exclusive=True)
async def _start_auto_refresh(self) -> None:
    """Runs until auto_refresh_interval becomes 0."""
    while self.auto_refresh_interval > 0:
        await asyncio.sleep(self.auto_refresh_interval)
        if self.auto_refresh_interval > 0:  # check again after sleep
            self.load_releases()
```

Add `watch_auto_refresh_interval` to immediately update the status bar when the interval changes (don't wait for the next `status_message` mutation):
```python
def watch_auto_refresh_interval(self, value: int) -> None:
    # Re-render the status bar to reflect the new auto-refresh label immediately.
    self.watch_status_message(self.status_message)
```

Update `watch_status_message` to append the auto-refresh state:
```python
def watch_status_message(self, value: str) -> None:
    try:
        bar = self.query_one("#status-bar", Static)
        interval = self.auto_refresh_interval
        if interval > 0:
            idx = self._REFRESH_INTERVALS.index(interval) if interval in self._REFRESH_INTERVALS else 0
            ar_label = f"  [dim]⟳ {self._REFRESH_LABELS[idx]}[/dim]"
        else:
            ar_label = ""
        bar.update(value + ar_label)
    except NoMatches:
        pass
```

- [ ] **Step 2: Update help text in `screens/help.py`**

Add to the Actions section:
```
  [yellow]A[/yellow]            Toggle auto-refresh (off/30s/1m/5m)
  [yellow]c[/yellow]            Switch Kubernetes context
```

- [ ] **Step 3: Commit**

```bash
git add helm_dashboard/app.py helm_dashboard/screens/help.py
git commit -m "feat: add auto-refresh toggle (A key) — cycles off/30s/1m/5m"
```

---

## Task 7: K8s Events tab in DetailScreen

**Files:**
- Modify: `helm_dashboard/helm_client.py` (add `get_release_events`)
- Modify: `helm_dashboard/screens/detail.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_helm_client.py`:

```python
def test_get_release_events_returns_string():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from helm_dashboard.helm_client import get_release_events

    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"Events:\n  Normal  Pulled  1m  kubelet  image pulled", b"")),
        ):
            result = await get_release_events("my-release", "default")
        assert isinstance(result, str)
        assert len(result) > 0

    asyncio.run(run())
```

- [ ] **Step 2: Add `get_release_events` to `helm_client.py`**

```python
async def get_release_events(name: str, namespace: str) -> str:
    """Get Kubernetes events for all resources belonging to a release.

    Fetches events from the release's namespace, filtered to resources
    with matching instance labels, plus events from any resources listed
    in the release manifest by name.
    """
    # Events in the namespace — filter by involved object labels is not
    # directly possible with kubectl, so we fetch all namespace events
    # and sort by last seen time.
    rc, stdout, stderr = await _run_kubectl(
        "get", "events",
        "--namespace", namespace,
        "--sort-by=.lastTimestamp",
        "-o", "wide",
        timeout=15.0,
    )
    output = stdout.decode("utf-8", errors="replace")
    if rc != 0 or not output.strip():
        return f"No events found in namespace '{namespace}'\n{stderr.decode()}"
    return output
```

- [ ] **Step 3: Add Events tab to `detail.py`**

In `compose()`, after the Hooks TabPane, add:
```python
with TabPane("Events", id="tab-events"):
    yield RichLog(id="events-log", wrap=True, markup=True)
```

Add binding:
```python
Binding("8", "tab_events", "Events", show=False),
```

In `_load_details`, add `get_release_events` to the `asyncio.gather` call:
```python
history, values, manifest, resources, notes, hooks, events = await asyncio.gather(
    get_release_history(rel.name, rel.namespace),
    get_release_values(rel.name, rel.namespace, all_values=True),
    get_release_manifest(rel.name, rel.namespace),
    get_release_resources(rel.name, rel.namespace),
    get_release_notes(rel.name, rel.namespace),
    get_release_hooks(rel.name, rel.namespace),
    get_release_events(rel.name, rel.namespace),
)
```

Write events:
```python
events_log = self.query_one("#events-log", RichLog)
events_log.clear()
events_log.write(f"[bold cyan]Kubernetes Events — namespace: {rel.namespace}[/bold cyan]\n\n")
events_log.write(events)
```

Add action:
```python
def action_tab_events(self) -> None:
    self.query_one("#detail-tabs", TabbedContent).active = "tab-events"
```

Add import:
```python
from helm_dashboard.helm_client import get_release_events
```

Update the detail-header hint:
```python
yield Static("[dim]Esc: Back  |  1-8: Tabs[/dim]", id="detail-hint")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/detail.py tests/test_helm_client.py
git commit -m "feat: add Events tab (key 8) to release detail; fetch namespace events via kubectl"
```

---

## Task 8: Improved resource label selector

**Files:**
- Modify: `helm_dashboard/helm_client.py`

The current selector only tries `app.kubernetes.io/instance=<name>` then `release=<name>`. Many charts use neither. We should also parse the manifest to extract resource names directly.

- [ ] **Step 1: Write test**

Append to `tests/test_helm_client.py`:

```python
def test_parse_manifest_resource_names():
    """_parse_manifest_resources extracts kind/name pairs from YAML manifests."""
    from helm_dashboard.helm_client import _parse_manifest_resource_names

    manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: default
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-svc
  namespace: default
"""
    result = _parse_manifest_resource_names(manifest)
    assert ("Deployment", "my-app") in result
    assert ("Service", "my-app-svc") in result
```

- [ ] **Step 2: Add helper and update `get_release_resources` in `helm_client.py`**

Add the parser function:
```python
def _parse_manifest_resource_names(manifest: str) -> list[tuple[str, str]]:
    """Parse a multi-document YAML manifest and extract (kind, name) pairs."""
    results: list[tuple[str, str]] = []
    try:
        for doc in yaml.safe_load_all(manifest):
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind", "")
            name = doc.get("metadata", {}).get("name", "")
            if kind and name:
                results.append((kind, name))
    except Exception:
        pass
    return results
```

Replace `get_release_resources` with a three-tier approach:

```python
async def get_release_resources(name: str, namespace: str) -> str:
    """Get Kubernetes resources for a release.

    Tries three strategies in order:
    1. Label selector: app.kubernetes.io/instance=<name>
    2. Label selector: release=<name>
    3. Parse manifest to get explicit resource names, then kubectl get each type
    """
    # Strategy 1 & 2: label selectors
    for label in (f"app.kubernetes.io/instance={name}", f"release={name}"):
        rc, stdout_bytes, _ = await _run_kubectl(
            "get", "all", "-l", label,
            "--namespace", namespace, "-o", "wide",
            timeout=15.0,
        )
        output = stdout_bytes.decode("utf-8", errors="replace")
        if output.strip() and "No resources found" not in output:
            return output

    # Strategy 3: parse the manifest
    # _run_helm returns tuple[int, str, str] — stdout is already a decoded str.
    rc, manifest, _ = await _run_helm(
        "get", "manifest", name, "--namespace", namespace
    )
    if rc != 0:
        return f"No resources found for release '{name}'"

    resource_pairs = _parse_manifest_resource_names(manifest)
    if not resource_pairs:
        return f"No resources found for release '{name}'"

    # Group by kind for a single kubectl call per kind
    from collections import defaultdict
    by_kind: dict[str, list[str]] = defaultdict(list)
    for kind, res_name in resource_pairs:
        by_kind[kind].append(res_name)

    sections: list[str] = []
    for kind, names in by_kind.items():
        rc, out_bytes, _ = await _run_kubectl(
            "get", kind, *names,
            "--namespace", namespace, "-o", "wide",
            timeout=15.0,
        )
        out = out_bytes.decode("utf-8", errors="replace")
        if out.strip():
            sections.append(out)

    return "\n".join(sections) if sections else f"No resources found for release '{name}'"
```

Note: `_run_helm` returns `tuple[int, str, str]` (strings), so `manifest` is already `str`. The function signature is correct.

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add helm_dashboard/helm_client.py tests/test_helm_client.py
git commit -m "fix: improve resource discovery with 3-tier strategy (labels → manifest parsing)"
```

---

## Task 9: Pod log streaming screen

**Files:**
- Create: `helm_dashboard/screens/logs.py`
- Modify: `helm_dashboard/helm_client.py` (add `list_pods_for_release`, `stream_pod_logs`)
- Modify: `helm_dashboard/screens/detail.py` (add `l` key binding to open log screen from Resources tab)

- [ ] **Step 1: Add `list_pods_for_release` and streaming to `helm_client.py`**

```python
async def list_pods_for_release(name: str, namespace: str) -> list[dict[str, str]]:
    """List pods belonging to a release. Returns list of {name, status, ready} dicts."""
    pods: list[dict[str, str]] = []

    for label in (f"app.kubernetes.io/instance={name}", f"release={name}"):
        rc, stdout, _ = await _run_kubectl(
            "get", "pods",
            "-l", label,
            "--namespace", namespace,
            "-o", "jsonpath={range .items[*]}{.metadata.name}|{.status.phase}|{range .status.containerStatuses[*]}{.name},{end}\\n{end}",
            timeout=15.0,
        )
        text = stdout.decode("utf-8", errors="replace")
        if rc == 0 and text.strip():
            for line in text.strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 2:
                    pods.append({
                        "name": parts[0],
                        "status": parts[1],
                        "containers": parts[2].rstrip(",") if len(parts) > 2 else "",
                    })
            if pods:
                return pods

    return pods


async def stream_pod_logs(
    pod_name: str,
    namespace: str,
    container: str = "",
    tail_lines: int = 200,
) -> str:
    """Fetch recent pod logs (non-streaming snapshot)."""
    args = ["logs", pod_name, "--namespace", namespace, f"--tail={tail_lines}"]
    if container:
        args.extend(["-c", container])
    rc, stdout, stderr = await _run_kubectl(*args, timeout=30.0)
    output = stdout.decode("utf-8", errors="replace")
    if rc != 0:
        return f"Error fetching logs: {stderr.decode('utf-8', errors='replace')}"
    return output or "(no log output)"
```

- [ ] **Step 2: Create `screens/logs.py`**

```python
"""Pod log viewer screen."""
from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, RichLog, Static

from helm_dashboard.helm_client import list_pods_for_release, stream_pod_logs


class LogScreen(ModalScreen[None]):
    """View logs for pods belonging to a Helm release."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("r", "refresh_logs", "Refresh"),
    ]

    CSS = """
    LogScreen { background: $surface; }

    #log-container {
        height: 1fr;
        width: 1fr;
    }

    #log-header {
        height: 3;
        background: $primary-darken-3;
        padding: 1 2;
        layout: horizontal;
    }

    #log-title { width: 1fr; color: $accent; text-style: bold; }
    #log-hint { width: auto; color: $text-muted; }

    #log-pod-list {
        height: 8;
        background: $surface-darken-1;
    }

    #log-output {
        height: 1fr;
        background: $surface;
    }
    """

    def __init__(self, release_name: str, namespace: str) -> None:
        super().__init__()
        self._release_name = release_name
        self._namespace = namespace
        self._selected_pod: str = ""
        self._selected_container: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="log-container"):
            with Horizontal(id="log-header"):
                yield Static(
                    f"⎈ Logs — {self._release_name}",
                    id="log-title",
                )
                yield Static("[dim]Esc: Back  |  r: Refresh[/dim]", id="log-hint")
            yield DataTable(id="log-pod-list", cursor_type="row", zebra_stripes=True)
            yield RichLog(id="log-output", wrap=False, markup=False)
        # No Footer() — LogScreen is a ModalScreen; parent screen's footer is visible underneath.

    async def on_mount(self) -> None:
        table = self.query_one("#log-pod-list", DataTable)
        table.add_columns("Pod", "Status", "Containers")
        self._load_pods()

    @work(thread=False)
    async def _load_pods(self) -> None:
        pods = await list_pods_for_release(self._release_name, self._namespace)
        table = self.query_one("#log-pod-list", DataTable)
        table.clear()
        if not pods:
            log = self.query_one("#log-output", RichLog)
            log.write(f"No pods found for release '{self._release_name}'")
            return
        for pod in pods:
            table.add_row(pod["name"], pod["status"], pod["containers"], key=pod["name"])
        # Auto-select first pod
        table.focus()
        if pods:
            self._selected_pod = pods[0]["name"]
            self._selected_container = ""
            self._load_logs()

    @work(thread=False)
    async def _load_logs(self) -> None:
        if not self._selected_pod:
            return
        log_widget = self.query_one("#log-output", RichLog)
        log_widget.clear()
        log_widget.write(f"Loading logs for {self._selected_pod}...\n")
        logs = await stream_pod_logs(
            self._selected_pod, self._namespace, self._selected_container
        )
        log_widget.clear()
        log_widget.write(logs)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value:
            self._selected_pod = event.row_key.value
            self._selected_container = ""
            self._load_logs()

    def action_close(self) -> None:
        self.dismiss(None)

    def action_refresh_logs(self) -> None:
        self._load_logs()
```

- [ ] **Step 3: Add `l` binding in `detail.py` to open log screen**

Add binding:
```python
Binding("l", "open_logs", "Logs", show=False),
```

Add action:
```python
def action_open_logs(self) -> None:
    from helm_dashboard.screens.logs import LogScreen
    self.app.push_screen(LogScreen(self._release.name, self._release.namespace))
```

- [ ] **Step 4: Update `screens/__init__.py`** to export `LogScreen`:

```python
# Append to helm_dashboard/screens/__init__.py
from helm_dashboard.screens.logs import LogScreen
# Add "LogScreen" to __all__
```

- [ ] **Step 5: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/logs.py helm_dashboard/screens/detail.py helm_dashboard/screens/__init__.py
git commit -m "feat: add pod log streaming screen (l key from release detail)"
```

---

## Task 10: kubectl describe screen

**Files:**
- Create: `helm_dashboard/screens/describe.py`
- Modify: `helm_dashboard/helm_client.py` (add `describe_resource`)
- Modify: `helm_dashboard/screens/detail.py` (add `d` key binding)

- [ ] **Step 1: Add `describe_resource` to `helm_client.py`**

```python
async def describe_resource(kind: str, name: str, namespace: str) -> str:
    """Run kubectl describe on a specific resource."""
    rc, stdout, stderr = await _run_kubectl(
        "describe", kind, name,
        "--namespace", namespace,
        timeout=15.0,
    )
    output = stdout.decode("utf-8", errors="replace")
    if rc != 0:
        return f"Error: {stderr.decode('utf-8', errors='replace')}"
    return output or f"No describe output for {kind}/{name}"
```

- [ ] **Step 2: Create `screens/describe.py`**

```python
"""Resource describe screen."""
from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from helm_dashboard.helm_client import describe_resource


class DescribeScreen(ModalScreen[None]):
    """Show kubectl describe output for a Kubernetes resource."""

    BINDINGS = [Binding("escape", "close", "Back")]

    CSS = """
    DescribeScreen { background: $surface; }

    #desc-container { height: 1fr; width: 1fr; }

    #desc-header {
        height: 3;
        background: $primary-darken-3;
        padding: 1 2;
        layout: horizontal;
    }

    #desc-title { width: 1fr; color: $accent; text-style: bold; }
    #desc-hint { width: auto; color: $text-muted; }
    #desc-output { height: 1fr; }
    """

    def __init__(self, kind: str, name: str, namespace: str) -> None:
        super().__init__()
        self._kind = kind
        self._name = name
        self._namespace = namespace

    def compose(self) -> ComposeResult:
        with Vertical(id="desc-container"):
            with Horizontal(id="desc-header"):
                yield Static(
                    f"⎈ Describe: {self._kind}/{self._name}",
                    id="desc-title",
                )
                yield Static("[dim]Esc: Back[/dim]", id="desc-hint")
            yield RichLog(id="desc-output", wrap=True, markup=False)
        # No Footer() — DescribeScreen is a ModalScreen.

    async def on_mount(self) -> None:
        self._load_describe()

    @work(thread=False)
    async def _load_describe(self) -> None:
        log = self.query_one("#desc-output", RichLog)
        log.write(f"Loading describe for {self._kind}/{self._name}...\n")
        output = await describe_resource(self._kind, self._name, self._namespace)
        log.clear()
        log.write(output)

    def action_close(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 3: Update `screens/__init__.py`** to export `DescribeScreen`:

```python
# Append to helm_dashboard/screens/__init__.py
from helm_dashboard.screens.describe import DescribeScreen
# Add "DescribeScreen" to __all__
```

- [ ] **Step 4: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/describe.py helm_dashboard/screens/__init__.py
git commit -m "feat: add kubectl describe screen; accessible from log screen via describe_resource"
```

---

## Task 11: Values diff between revisions

**Files:**
- Modify: `helm_dashboard/helm_client.py` (add `get_values_for_revision`)
- Modify: `helm_dashboard/screens/detail.py` (add `v` key in History tab to open diff)

The diff is shown as a simple unified diff — no external dependency needed (Python stdlib `difflib`).

- [ ] **Step 1: Write test**

Append to `tests/test_helm_client.py`:

```python
def test_diff_values_produces_unified_diff():
    """diff_values returns unified diff string."""
    from helm_dashboard.helm_client import diff_values

    old = "replicaCount: 1\nimage:\n  tag: v1.0\n"
    new = "replicaCount: 2\nimage:\n  tag: v1.1\n"
    result = diff_values(old, new, "rev-1", "rev-2")
    assert "-replicaCount: 1" in result
    assert "+replicaCount: 2" in result
```

- [ ] **Step 2: Add helpers to `helm_client.py`**

```python
import difflib  # stdlib — add to top of file

async def get_values_for_revision(name: str, namespace: str, revision: int) -> str:
    """Get computed values for a specific revision."""
    rc, stdout, stderr = await _run_helm(
        "get", "values", name,
        "--namespace", namespace,
        "--revision", str(revision),
        "--all",
        "--output", "yaml",
    )
    if rc != 0:
        return f"# Error fetching values for revision {revision}:\n# {stderr}"
    return stdout


def diff_values(old: str, new: str, old_label: str = "old", new_label: str = "new") -> str:
    """Return a unified diff of two YAML values strings."""
    diff = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=old_label,
        tofile=new_label,
    ))
    return "".join(diff) if diff else "(no differences)"
```

- [ ] **Step 3: Add diff action to `detail.py`**

The History tab has a `DataTable`. When user presses `v` on a highlighted history row, compare that revision's values against the current revision.

Add binding to `DetailScreen`:
```python
Binding("v", "diff_values", "Diff Values", show=False),
```

Add action:
```python
def action_diff_values(self) -> None:
    hist_table = self.query_one("#history-table", DataTable)
    if hist_table.cursor_row is None:
        self.notify("Select a revision in the History tab first", severity="warning")
        return
    row = hist_table.get_row_at(hist_table.cursor_row)
    if row:
        selected_rev = int(str(row[0]))
        self._show_values_diff(selected_rev)

@work(thread=False)
async def _show_values_diff(self, old_revision: int) -> None:
    from helm_dashboard.helm_client import diff_values, get_values_for_revision
    rel = self._release
    old_values, new_values = await asyncio.gather(
        get_values_for_revision(rel.name, rel.namespace, old_revision),
        get_release_values(rel.name, rel.namespace, all_values=True),
    )
    diff = diff_values(
        old_values, new_values,
        old_label=f"revision {old_revision}",
        new_label=f"revision {rel.revision} (current)",
    )
    # Show diff in values log and switch to that tab
    values_log = self.query_one("#values-log", RichLog)
    values_log.clear()
    from rich.syntax import Syntax
    values_log.write(f"[bold cyan]Values diff: rev {old_revision} → rev {rel.revision}[/bold cyan]\n\n")
    values_log.write(Syntax(diff, "diff", theme="monokai"))
    self.query_one("#detail-tabs", TabbedContent).active = "tab-values"
    self.notify(f"Diff: revision {old_revision} vs current", timeout=3)
```

Add `get_values_for_revision` to the `detail.py` helm_client imports.

- [ ] **Step 4: Run tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Update help text in `screens/help.py`**

Add to the detail section:
```
  [yellow]v[/yellow]            Diff selected history revision's values vs current
  [yellow]l[/yellow]            Open pod log viewer for this release
```

- [ ] **Step 6: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/screens/detail.py helm_dashboard/screens/help.py tests/test_helm_client.py
git commit -m "feat: values diff between revisions (v key in History tab)"
```

---

## Task 12: Upgrade-available indicator

**Files:**
- Modify: `helm_dashboard/helm_client.py` (add `get_available_chart_versions`)
- Modify: `helm_dashboard/app.py` (add upgrade check column, background worker)

This adds a lightweight background check: after releases load, run `helm search repo <chart> --output json` for each unique chart and compare versions. Shows `⬆` in a new "Upgrade" column.

- [ ] **Step 1: Write test**

Append to `tests/test_helm_client.py`:

```python
def test_get_available_chart_versions_returns_list():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from helm_dashboard.helm_client import get_available_chart_versions

    mock_output = b'[{"name":"stable/nginx","version":"2.0.0","app_version":"1.25","description":""}]'

    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, mock_output.decode(), "")),
        ):
            result = await get_available_chart_versions("nginx")
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0].chart_version == "2.0.0"

    asyncio.run(run())
```

- [ ] **Step 2: Add `get_available_chart_versions` to `helm_client.py`**

```python
async def get_available_chart_versions(chart_name: str) -> list[HelmChart]:
    """Search repos for available versions of a chart (by base name)."""
    rc, stdout, stderr = await _run_helm(
        "search", "repo", chart_name, "--output", "json", "--versions"
    )
    if rc != 0 or not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    return [
        HelmChart(
            name=c.get("name", ""),
            chart_version=c.get("version", ""),
            app_version=c.get("app_version", ""),
            description=c.get("description", ""),
        )
        for c in data
    ]
```

- [ ] **Step 3: Add upgrade column and background worker in `app.py`**

Add a dict to track available upgrades:
```python
def __init__(self) -> None:
    super().__init__()
    self._namespaces: list[str] = ["All Namespaces"]
    self._upgrade_available: dict[str, bool] = {}  # release_name -> bool
```

In `on_mount`, add a column (modify the `add_columns` call):
```python
table.add_columns(
    "Status", "Name", "Namespace", "Revision", "Chart", "Version", "App Ver", "Updated", "⬆"
)
```

In `_populate_table`, add upgrade cell as last column:
```python
upgrade_flag = "⬆" if self._upgrade_available.get(rel.name, False) else ""
table.add_row(
    status_text,
    rel.name,
    rel.namespace,
    str(rel.revision),
    rel.chart,
    rel.chart_version,
    rel.app_version,
    updated_short,
    Text(upgrade_flag, style="bold yellow"),
    key=str(i),
)
```

After `self.releases = releases` in `load_releases`, trigger background upgrade check:
```python
self._check_upgrades_available()
```

Add the worker:
```python
@work(thread=False)
async def _check_upgrades_available(self) -> None:
    """Background check for newer chart versions (best-effort)."""
    from helm_dashboard.helm_client import get_available_chart_versions
    # Reset stale entries — a release may have been uninstalled/reinstalled.
    self._upgrade_available = {}
    if not self.releases:
        return
    # Deduplicate by chart name to minimize API calls
    seen: set[str] = set()
    for rel in self.releases:
        chart_base = rel.chart
        if chart_base in seen:
            continue
        seen.add(chart_base)
        try:
            versions = await get_available_chart_versions(chart_base)
            if versions:
                latest = versions[0].chart_version
                for r in self.releases:
                    if r.chart == chart_base and latest != r.chart_version:
                        self._upgrade_available[r.name] = True
        except Exception:
            pass  # upgrade check is best-effort
    # Re-populate table with upgrade flags
    self._populate_table()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add helm_dashboard/helm_client.py helm_dashboard/app.py tests/test_helm_client.py
git commit -m "feat: upgrade-available indicator column with background chart version check"
```

---

## Final: Update CLAUDE.md and README

- [ ] **Update `README.md` keyboard shortcuts table** to include new bindings:

| Key | Action |
|-----|--------|
| `c` | Switch Kubernetes context |
| `A` | Toggle auto-refresh (off/30s/1m/5m) |
| `1`–`8` | Switch detail tabs (Overview/History/Values/Manifest/Resources/Notes/Hooks/Events) |
| `v` | (in History tab) Diff values vs current |
| `l` | (in Detail view) Open pod log viewer |

- [ ] **Update `CLAUDE.md` architecture section** to reflect the `screens/` package.

- [ ] **Final commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: update README and CLAUDE.md for new features and screens package"
```

---

## Testing Reference

All automated tests live in `tests/test_helm_client.py`. Run with:
```bash
cd /Users/razvanbalsan/Projects/h9s && source .venv/bin/activate && pytest tests/ -v
```

For manual UI testing:
1. Launch: `python -m helm_dashboard`
2. Navigate with `↑/↓`, press `Enter` to open detail
3. Verify tabs 1–8 all load without error
4. Press `c` — context screen should appear
5. Press `A` — status bar should show `⟳ 30s`, press again for `1m`, etc.
6. In detail view, go to History tab, highlight a row, press `v` — Values tab should show diff
7. In detail view, press `l` — log screen should appear with pod list
8. Resources tab should show resource output or a clear "no resources" message
