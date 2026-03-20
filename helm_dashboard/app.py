"""Helm Dashboard — k9s-style terminal UI for Helm releases.

Usage:
    helm-dashboard          # Launch the dashboard
    python -m helm_dashboard.app
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from rich.markup import escape
from rich.syntax import Syntax
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    OptionList,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from helm_dashboard.helm_client import (
    HelmRelease,
    HelmRepo,
    ReleaseStatus,
    _install_asyncio_error_filter,
    add_repo,
    check_helm_available,
    get_current_context,
    get_namespaces,
    get_release_history,
    get_release_hooks,
    get_release_manifest,
    get_release_notes,
    get_release_resources,
    get_release_values,
    list_releases,
    list_repos,
    remove_repo,
    rollback_release,
    search_charts,
    uninstall_release,
    update_repos,
)
from helm_dashboard.screens import (
    ConfirmDialog,
    ContextScreen,
    DetailScreen,
    HelpScreen,
    InputDialog,
    NamespaceScreen,
    RepoScreen,
)

# ─── CSS Theme ────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
Screen {
    background: $surface;
}

#main-container {
    height: 1fr;
}

/* ── Top Bar ─────────────────────────────────────── */
#top-bar {
    height: 3;
    background: $primary-darken-3;
    color: $text;
    padding: 0 1;
    layout: horizontal;
}

#logo {
    width: auto;
    color: $success;
    text-style: bold;
    padding: 1 2 0 1;
}

#context-label {
    width: auto;
    padding: 1 2 0 0;
    color: $warning;
}

#namespace-select {
    width: 30;
    margin: 0 1;
}

#search-input {
    width: 30;
    margin: 0 1;
}

#status-bar {
    width: 1fr;
    padding: 1 1 0 0;
    text-align: right;
    color: $text-muted;
}

/* ── Left Panel: Release List ───────────────────── */
#left-panel {
    width: 1fr;
}

#release-table {
    height: 1fr;
}

#release-table > .datatable--header {
    background: $primary-darken-2;
    text-style: bold;
}

#release-table > .datatable--cursor {
    background: $accent;
    color: $text;
}

/* ── Left Panel takes full width ───────────────── */

/* ── Repo Table ──────────────────────────────────── */
#repo-table {
    height: 1fr;
}

/* ── Dialogs ─────────────────────────────────────── */
ConfirmDialog {
    align: center middle;
}

#confirm-dialog-box {
    width: 60;
    height: auto;
    max-height: 20;
    background: $surface;
    border: thick $error;
    padding: 1 2;
}

#confirm-dialog-box Label {
    width: 1fr;
    text-align: center;
    margin: 1 0;
}

#confirm-buttons {
    height: 3;
    align: center middle;
}

#confirm-buttons Button {
    margin: 0 2;
}

InputDialog {
    align: center middle;
}

#input-dialog-box {
    width: 70;
    height: auto;
    max-height: 24;
    background: $surface;
    border: thick $accent;
    padding: 1 2;
}

#input-dialog-box Label {
    width: 1fr;
    margin: 1 0;
}

#input-dialog-box Input {
    margin: 0 0 1 0;
}

#input-buttons {
    height: 3;
    align: center middle;
}

#input-buttons Button {
    margin: 0 2;
}

/* ── Status Indicators ───────────────────────────── */
.status-deployed {
    color: $success;
}

.status-failed {
    color: $error;
}

.status-pending {
    color: $warning;
}

/* ── Loading ─────────────────────────────────────── */
#loading-container {
    align: center middle;
    height: 1fr;
}

/* ── Help Overlay ────────────────────────────────── */
HelpScreen {
    align: center middle;
}

#help-box {
    width: 70;
    height: auto;
    max-height: 36;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}

#help-box Static {
    margin: 0 0 1 0;
}

/* ── Resource pane ───────────────────────────────── */
#resources-log {
    height: 1fr;
}
"""


# ─── Main Application ────────────────────────────────────────────────────────


class HelmDashboard(App):
    """A k9s-style terminal dashboard for Helm."""

    TITLE = "⎈ Helm Dashboard"
    SUB_TITLE = "Terminal UI for Helm Releases"
    CSS = DASHBOARD_CSS

    _REFRESH_INTERVALS: list[int] = [0, 30, 60, 300]   # seconds; 0 = off
    _REFRESH_LABELS: list[str] = ["off", "30s", "1m", "5m"]

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "show_help", "Help", show=True, key_display="?"),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("slash", "focus_search", "Search", show=True, key_display="/"),
        Binding("n", "cycle_namespace", "Namespace", show=True),
        Binding("B", "rollback", "Rollback", show=False),
        Binding("D", "delete_release", "Delete", show=False),
        Binding("R", "show_repos", "Repos", show=True),
        Binding("U", "update_repos", "Update Repos", show=False),
        Binding("c", "switch_context", "Context", show=True),
        Binding("A", "toggle_auto_refresh", "Auto-refresh", show=False),
    ]

    # Reactive state
    current_context: reactive[str] = reactive("loading...")
    selected_namespace: reactive[str] = reactive("All Namespaces")
    releases: reactive[list[HelmRelease]] = reactive(list, init=False)
    selected_release: reactive[HelmRelease | None] = reactive(None)
    search_filter: reactive[str] = reactive("")
    status_message: reactive[str] = reactive("")
    auto_refresh_interval: reactive[int] = reactive(0)
    _pending_contexts: reactive[list[str] | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        self._namespaces: list[str] = ["All Namespaces"]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="top-bar"):
            yield Static("⎈ HELM", id="logo")
            yield Static("ctx: loading...", id="context-label")
            yield Input(placeholder="🔍 Filter releases...", id="search-input")
            yield Static("", id="status-bar")

        with Horizontal(id="main-container"):
            # Left panel: release list (full width)
            with Vertical(id="left-panel"):
                yield DataTable(id="release-table", cursor_type="row", zebra_stripes=True)

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the dashboard on mount."""
        _install_asyncio_error_filter()

        # Set up release table columns
        table = self.query_one("#release-table", DataTable)
        table.add_columns(
            "Status", "Name", "Namespace", "Revision", "Chart", "Version", "App Ver", "Updated"
        )

        # Check helm
        available, version = await check_helm_available()
        if not available:
            self.notify(
                f"Helm not found: {version}", severity="error", timeout=10
            )
            self.sub_title = "⚠️  Helm CLI not found"
            return

        self.sub_title = f"Helm {version}"

        # Load context and data
        self.current_context = await get_current_context()
        self._namespaces = ["All Namespaces"] + await get_namespaces()

        self.load_releases()
        self.query_one("#release-table", DataTable).focus()

    def watch_current_context(self, value: str) -> None:
        try:
            label = self.query_one("#context-label", Static)
            label.update(f"ctx: [bold yellow]{escape(value)}[/bold yellow]")
        except NoMatches:
            pass

    def watch_status_message(self, value: str) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            interval = self.auto_refresh_interval
            if interval > 0 and interval in self._REFRESH_INTERVALS:
                idx = self._REFRESH_INTERVALS.index(interval)
                ar_label = f"  [dim]⟳ {self._REFRESH_LABELS[idx]}[/dim]"
            else:
                ar_label = ""
            bar.update(value + ar_label)
        except NoMatches:
            pass

    def watch_auto_refresh_interval(self, value: int) -> None:
        """Immediately re-render the status bar to show the new interval label."""
        self.watch_status_message(self.status_message)

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.search_filter = event.value
        self._apply_filter()

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#release-table", DataTable).focus()

    @on(DataTable.RowSelected, "#release-table")
    def on_release_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value is not None:
            idx = int(event.row_key.value)
            filtered = self._filtered_releases()
            if 0 <= idx < len(filtered):
                self.selected_release = filtered[idx]
                self.push_screen(DetailScreen(filtered[idx]))

    @on(DataTable.RowHighlighted, "#release-table")
    def on_release_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value is not None:
            idx = int(event.row_key.value)
            filtered = self._filtered_releases()
            if 0 <= idx < len(filtered):
                self.selected_release = filtered[idx]

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_auto_refresh(self) -> None:
        intervals = self._REFRESH_INTERVALS
        current_idx = (
            intervals.index(self.auto_refresh_interval)
            if self.auto_refresh_interval in intervals
            else 0
        )
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

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self.load_releases()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cycle_namespace(self) -> None:
        self.push_screen(
            NamespaceScreen(self._namespaces, self.selected_namespace),
            callback=self._handle_namespace_selected,
        )

    def _handle_namespace_selected(self, result: str | None) -> None:
        if result is not None and result != self.selected_namespace:
            self.selected_namespace = result
            self.notify(f"Namespace: {self.selected_namespace}", timeout=2)
            self.load_releases()

    def action_rollback(self) -> None:
        rel = self.selected_release
        if not rel:
            self.notify("No release selected", severity="warning")
            return
        if rel.revision <= 1:
            self.notify("Cannot rollback: only one revision", severity="warning")
            return

        self.push_screen(
            ConfirmDialog(
                f"Rollback [bold]{rel.name}[/bold] in [bold]{rel.namespace}[/bold] "
                f"to revision {rel.revision - 1}?",
                title="⎈ Rollback Release",
            ),
            callback=self._handle_rollback,
        )

    def _handle_rollback(self, confirmed: bool) -> None:
        if confirmed and self.selected_release:
            self._do_rollback(self.selected_release)

    @work(thread=False)
    async def _do_rollback(self, rel: HelmRelease) -> None:
        self.status_message = f"Rolling back {rel.name}..."
        success, msg = await rollback_release(rel.name, rel.namespace, rel.revision - 1)
        if success:
            self.notify(f"✅ Rolled back {rel.name}", severity="information")
            self.load_releases()
        else:
            self.notify(f"❌ Rollback failed: {msg}", severity="error", timeout=8)
        self.status_message = ""

    def action_delete_release(self) -> None:
        rel = self.selected_release
        if not rel:
            self.notify("No release selected", severity="warning")
            return

        self.push_screen(
            ConfirmDialog(
                f"Uninstall [bold red]{rel.name}[/bold red] from "
                f"[bold]{rel.namespace}[/bold]?\n\nThis action cannot be undone!",
                title="⚠️  Uninstall Release",
            ),
            callback=self._handle_uninstall,
        )

    def _handle_uninstall(self, confirmed: bool) -> None:
        if confirmed and self.selected_release:
            self._do_uninstall(self.selected_release)

    @work(thread=False)
    async def _do_uninstall(self, rel: HelmRelease) -> None:
        self.status_message = f"Uninstalling {rel.name}..."
        success, msg = await uninstall_release(rel.name, rel.namespace)
        if success:
            self.notify(f"🗑️ Uninstalled {rel.name}", severity="information")
            self.selected_release = None
            self.load_releases()
        else:
            self.notify(f"❌ Uninstall failed: {msg}", severity="error", timeout=8)
        self.status_message = ""

    def action_show_repos(self) -> None:
        self.push_screen(RepoScreen())

    def action_update_repos(self) -> None:
        self._do_update_repos()

    def action_switch_context(self) -> None:
        self._fetch_contexts()

    @work(thread=False)
    async def _fetch_contexts(self) -> None:
        from helm_dashboard.helm_client import get_contexts
        contexts = await get_contexts()
        if not contexts:
            self.notify("No contexts found", severity="warning")
            return
        self._pending_contexts = contexts  # triggers watch__pending_contexts

    def watch__pending_contexts(self, contexts: list[str] | None) -> None:
        """Called synchronously when _pending_contexts changes; open the screen here."""
        if contexts is None:
            return
        self._pending_contexts = None  # reset immediately to avoid re-triggering
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

    @work(thread=False)
    async def _do_update_repos(self) -> None:
        self.status_message = "Updating repositories..."
        self.notify("Updating all Helm repos...", timeout=3)
        success, msg = await update_repos()
        if success:
            self.notify("✅ Repos updated", severity="information")
        else:
            self.notify(f"❌ Update failed: {msg}", severity="error", timeout=8)
        self.status_message = ""

    # ── Data Loading ──────────────────────────────────────────────────────────

    @work(thread=False)
    async def load_releases(self) -> None:
        """Load releases from Helm."""
        self.status_message = "Loading releases..."
        ns = self.selected_namespace if self.selected_namespace != "All Namespaces" else None
        releases = await list_releases(ns)
        self.releases = releases
        self._populate_table()
        total = len(releases)
        deployed = sum(1 for r in releases if r.status == ReleaseStatus.DEPLOYED)
        failed = sum(1 for r in releases if r.status == ReleaseStatus.FAILED)
        self.status_message = (
            f"[{self.selected_namespace}] "
            f"{total} releases | "
            f"[green]{deployed} deployed[/green]"
            + (f" | [red]{failed} failed[/red]" if failed else "")
        )

    def _filtered_releases(self) -> list[HelmRelease]:
        """Apply search filter to releases."""
        if not self.search_filter:
            return list(self.releases)
        q = self.search_filter.lower()
        return [
            r for r in self.releases
            if q in r.name.lower()
            or q in r.namespace.lower()
            or q in r.chart.lower()
            or q in r.app_version.lower()
        ]

    def _populate_table(self) -> None:
        """Populate the release DataTable."""
        table = self.query_one("#release-table", DataTable)
        table.clear()

        for i, rel in enumerate(self._filtered_releases()):
            status_style = {
                ReleaseStatus.DEPLOYED: "green",
                ReleaseStatus.FAILED: "red",
                ReleaseStatus.PENDING_INSTALL: "yellow",
                ReleaseStatus.PENDING_UPGRADE: "yellow",
                ReleaseStatus.PENDING_ROLLBACK: "yellow",
            }.get(rel.status, "dim")

            status_text = Text(f"{rel.status_icon} {rel.status.value}", style=status_style)

            # Truncate the updated timestamp
            updated_short = rel.updated[:19] if len(rel.updated) > 19 else rel.updated

            table.add_row(
                status_text,
                rel.name,
                rel.namespace,
                str(rel.revision),
                rel.chart,
                rel.chart_version,
                rel.app_version,
                updated_short,
                key=str(i),
            )

    def _apply_filter(self) -> None:
        """Re-populate table with current filter."""
        self._populate_table()


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Launch the Helm Dashboard TUI."""
    app = HelmDashboard()
    app.run()


if __name__ == "__main__":
    main()
