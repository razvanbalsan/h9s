from __future__ import annotations

import asyncio

import rich.box
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, RichLog, Static, TabbedContent, TabPane

from helm_dashboard.helm_client import (
    HelmRelease,
    HelmRevision,
    K8sEvent,
    K8sResource,
    ReleaseStatus,
    _KIND_ICONS,
    diff_values,
    get_release_events,
    get_release_history,
    get_release_hooks,
    get_release_manifest,
    get_release_notes,
    get_release_resources,
    get_release_values,
    get_values_for_revision,
)


_OK_STATUSES = frozenset({
    "Running", "Complete", "Ready", "Available",
    "ClusterIP", "NodePort", "LoadBalancer", "ExternalName",
    "Active", "Bound",
})
_ERROR_STATUSES = frozenset({
    "Failed", "CrashLoopBackOff", "Error",
    "ImagePullBackOff", "ErrImagePull", "OOMKilled",
})


def _build_resources_table(resources: list[K8sResource]) -> Table:
    table = Table(
        show_header=True,
        header_style="bold cyan",
        expand=True,
        box=rich.box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Kind", min_width=14)
    table.add_column("Name", min_width=20, no_wrap=True)
    table.add_column("Ready", justify="center", min_width=7)
    table.add_column("Status", min_width=14)
    table.add_column("Age", justify="right", min_width=5)

    for r in resources:
        icon = _KIND_ICONS.get(r.kind, "📦")
        if r.status in _OK_STATUSES:
            status_style = "green"
        elif r.status in _ERROR_STATUSES:
            status_style = "red bold"
        else:
            status_style = "yellow"

        table.add_row(
            f"{icon} {r.kind}",
            r.name,
            r.ready,
            Text(r.status, style=status_style),
            r.age,
        )
    return table


def _build_events_table(events: list[K8sEvent]) -> Table:
    table = Table(
        show_header=True,
        header_style="bold cyan",
        expand=True,
        box=rich.box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Age", justify="right", min_width=5)
    table.add_column("Last Seen", min_width=19, no_wrap=True)
    table.add_column("Type", min_width=8)
    table.add_column("Reason", min_width=18, no_wrap=True)
    table.add_column("Object", min_width=22, no_wrap=True)
    table.add_column("Message")

    for e in events:
        type_style = "red bold" if e.type == "Warning" else "dim"
        count_suffix = f" ×{e.count}" if e.count > 1 else ""
        table.add_row(
            e.age,
            e.last_seen,
            Text(e.type, style=type_style),
            e.reason,
            e.object_ref,
            e.message + count_suffix,
        )
    return table


class DetailScreen(ModalScreen[None]):
    """Full-screen release detail view. Press Escape to close."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("l", "open_logs", "Logs", show=False),
        Binding("1", "tab_overview", "Overview", show=False),
        Binding("2", "tab_history", "History", show=False),
        Binding("3", "tab_values", "Values", show=False),
        Binding("4", "tab_manifest", "Manifest", show=False),
        Binding("5", "tab_resources", "Resources", show=False),
        Binding("6", "tab_notes", "Notes", show=False),
        Binding("7", "tab_hooks", "Hooks", show=False),
        Binding("8", "tab_events", "Events", show=False),
        Binding("v", "diff_values", "Diff Values", show=False),
    ]

    CSS = """
    DetailScreen {
        background: $surface;
    }

    #detail-container {
        height: 1fr;
        width: 1fr;
    }

    #detail-header {
        height: 3;
        background: $primary-darken-3;
        color: $text;
        padding: 1 2;
        layout: horizontal;
    }

    #detail-title {
        width: 1fr;
        color: $accent;
        text-style: bold;
    }

    #detail-hint {
        width: auto;
        color: $text-muted;
    }

    #detail-tabs {
        height: 1fr;
    }

    RichLog {
        height: 1fr;
        background: $surface;
        scrollbar-size: 1 1;
    }

    #history-table {
        height: 1fr;
    }
    """

    def __init__(self, release: HelmRelease) -> None:
        super().__init__()
        self._release = release

    def compose(self) -> ComposeResult:
        rel = self._release
        with Vertical(id="detail-container"):
            with Horizontal(id="detail-header"):
                yield Static(
                    f"⎈ {rel.name}  {rel.status_icon} {rel.status.value}  "
                    f"[dim]{rel.namespace}[/dim]",
                    id="detail-title",
                )
                yield Static("[dim]Esc: Back  |  1-8: Tabs[/dim]", id="detail-hint")
            with TabbedContent(id="detail-tabs"):
                with TabPane("Overview", id="tab-overview"):
                    yield RichLog(id="overview-log", wrap=True, markup=True)
                with TabPane("History", id="tab-history"):
                    yield DataTable(
                        id="history-table", cursor_type="row", zebra_stripes=True
                    )
                with TabPane("Values", id="tab-values"):
                    yield RichLog(id="values-log", wrap=True, auto_scroll=False)
                with TabPane("Manifest", id="tab-manifest"):
                    yield RichLog(id="manifest-log", wrap=True, auto_scroll=False)
                with TabPane("Resources", id="tab-resources"):
                    yield RichLog(id="resources-log", wrap=True, markup=True)
                with TabPane("Notes", id="tab-notes"):
                    yield RichLog(id="notes-log", wrap=True, markup=True)
                with TabPane("Hooks", id="tab-hooks"):
                    yield RichLog(id="hooks-log", wrap=True, markup=True)
                with TabPane("Events", id="tab-events"):
                    yield RichLog(id="events-log", wrap=True, markup=True)

    async def on_mount(self) -> None:
        # Set up history table columns
        hist_table = self.query_one("#history-table", DataTable)
        hist_table.add_columns("Rev", "Updated", "Status", "Chart", "App Ver", "Description")
        # Load details
        self._load_details()

    @work(thread=False)
    async def _load_details(self) -> None:
        rel = self._release

        # Overview
        overview_log = self.query_one("#overview-log", RichLog)
        overview_log.clear()
        overview_log.write(
            f"[bold cyan]Release:[/bold cyan]    {rel.name}\n"
            f"[bold cyan]Namespace:[/bold cyan]  {rel.namespace}\n"
            f"[bold cyan]Status:[/bold cyan]     {rel.status_icon} {rel.status.value}\n"
            f"[bold cyan]Revision:[/bold cyan]   {rel.revision}\n"
            f"[bold cyan]Chart:[/bold cyan]      {rel.chart}\n"
            f"[bold cyan]Chart Ver:[/bold cyan]  {rel.chart_version}\n"
            f"[bold cyan]App Ver:[/bold cyan]    {rel.app_version}\n"
            f"[bold cyan]Updated:[/bold cyan]    {rel.updated}\n"
            f"[bold cyan]Description:[/bold cyan] {rel.description}\n"
        )

        # Load everything concurrently
        (
            history,
            values,
            manifest,
            resources,
            notes,
            hooks,
            events,
        ) = await asyncio.gather(
            get_release_history(rel.name, rel.namespace),
            get_release_values(rel.name, rel.namespace, all_values=True),
            get_release_manifest(rel.name, rel.namespace),
            get_release_resources(rel.name, rel.namespace),
            get_release_notes(rel.name, rel.namespace),
            get_release_hooks(rel.name, rel.namespace),
            get_release_events(rel.name, rel.namespace),
        )
        # Narrow types for mypy (asyncio.gather infers Sequence[object])
        history_: list[HelmRevision] = list(history)  # type: ignore[arg-type]
        values_: str = str(values)
        manifest_: str = str(manifest)
        resources_: list[K8sResource] = list(resources)  # type: ignore[arg-type]
        notes_: str = str(notes)
        hooks_: str = str(hooks)
        events_: list[K8sEvent] = list(events)  # type: ignore[arg-type]

        # History table
        hist_table = self.query_one("#history-table", DataTable)
        hist_table.clear()
        for rev in reversed(history_):
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

        # Values
        values_log = self.query_one("#values-log", RichLog)
        values_log.clear()
        values_log.write(Syntax(values_, "yaml", theme="monokai", line_numbers=True))
        values_log.scroll_home(animate=False)

        # Manifest
        manifest_log = self.query_one("#manifest-log", RichLog)
        manifest_log.clear()
        manifest_log.write(Syntax(manifest_, "yaml", theme="monokai", line_numbers=True))
        manifest_log.scroll_home(animate=False)

        # Resources
        resources_log = self.query_one("#resources-log", RichLog)
        resources_log.clear()
        resources_log.write(f"[bold cyan]Kubernetes Resources — {rel.name}[/bold cyan]\n")
        if resources_:
            resources_log.write(_build_resources_table(resources_))
        else:
            resources_log.write("[dim]No resources found for this release.[/dim]")

        # Notes
        notes_log = self.query_one("#notes-log", RichLog)
        notes_log.clear()
        notes_log.write(f"[bold cyan]Release Notes — {rel.name}[/bold cyan]\n\n")
        notes_log.write(notes_)
        notes_log.scroll_home(animate=False)

        # Hooks
        hooks_log = self.query_one("#hooks-log", RichLog)
        hooks_log.clear()
        hooks_log.write(Syntax(hooks_, "yaml", theme="monokai", line_numbers=True))
        hooks_log.scroll_home(animate=False)

        # Events
        events_log = self.query_one("#events-log", RichLog)
        events_log.clear()
        events_log.write(f"[bold cyan]Kubernetes Events — namespace: {rel.namespace}[/bold cyan]\n")
        if events_:
            events_log.write(_build_events_table(events_))
        else:
            events_log.write("[dim]No events found in this namespace.[/dim]")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_open_logs(self) -> None:
        from helm_dashboard.screens.logs import LogScreen
        self.app.push_screen(LogScreen(self._release.name, self._release.namespace))

    def action_tab_overview(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-overview"

    def action_tab_history(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-history"

    def action_tab_values(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-values"

    def action_tab_manifest(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-manifest"

    def action_tab_resources(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-resources"

    def action_tab_notes(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-notes"

    def action_tab_hooks(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-hooks"

    def action_tab_events(self) -> None:
        self.query_one("#detail-tabs", TabbedContent).active = "tab-events"

    def action_diff_values(self) -> None:
        hist_table = self.query_one("#history-table", DataTable)
        if hist_table.cursor_row is None or hist_table.row_count == 0:
            self.notify("Select a revision in the History tab first", severity="warning")
            return
        row = hist_table.get_row_at(hist_table.cursor_row)
        if row:
            selected_rev = int(str(row[0]))
            self._show_values_diff(selected_rev)

    @work(thread=False)
    async def _show_values_diff(self, old_revision: int) -> None:
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
        values_log = self.query_one("#values-log", RichLog)
        values_log.clear()
        values_log.write(
            f"[bold cyan]Values diff: rev {old_revision} → rev {rel.revision}[/bold cyan]\n\n"
        )
        values_log.write(Syntax(diff, "diff", theme="monokai"))
        values_log.scroll_home(animate=False)
        self.query_one("#detail-tabs", TabbedContent).active = "tab-values"
        self.notify(f"Diff: revision {old_revision} vs current", timeout=3)
