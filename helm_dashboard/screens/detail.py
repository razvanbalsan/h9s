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
    get_release_events,
    get_release_history,
    get_release_hooks,
    get_release_manifest,
    get_release_notes,
    get_release_resources,
    get_release_values,
)


class DetailScreen(ModalScreen[None]):
    """Full-screen release detail view. Press Escape to close."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("1", "tab_overview", "Overview", show=False),
        Binding("2", "tab_history", "History", show=False),
        Binding("3", "tab_values", "Values", show=False),
        Binding("4", "tab_manifest", "Manifest", show=False),
        Binding("5", "tab_resources", "Resources", show=False),
        Binding("6", "tab_notes", "Notes", show=False),
        Binding("7", "tab_hooks", "Hooks", show=False),
        Binding("8", "tab_events", "Events", show=False),
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
                    yield RichLog(id="values-log", wrap=True)
                with TabPane("Manifest", id="tab-manifest"):
                    yield RichLog(id="manifest-log", wrap=True)
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
        history, values, manifest, resources, notes, hooks, events = await asyncio.gather(
            get_release_history(rel.name, rel.namespace),
            get_release_values(rel.name, rel.namespace, all_values=True),
            get_release_manifest(rel.name, rel.namespace),
            get_release_resources(rel.name, rel.namespace),
            get_release_notes(rel.name, rel.namespace),
            get_release_hooks(rel.name, rel.namespace),
            get_release_events(rel.name, rel.namespace),
        )

        # History table
        hist_table = self.query_one("#history-table", DataTable)
        hist_table.clear()
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

        # Values
        values_log = self.query_one("#values-log", RichLog)
        values_log.clear()
        values_log.write(Syntax(values, "yaml", theme="monokai", line_numbers=True))

        # Manifest
        manifest_log = self.query_one("#manifest-log", RichLog)
        manifest_log.clear()
        manifest_log.write(Syntax(manifest, "yaml", theme="monokai", line_numbers=True))

        # Resources
        resources_log = self.query_one("#resources-log", RichLog)
        resources_log.clear()
        resources_log.write(f"[bold cyan]Kubernetes Resources for {rel.name}[/bold cyan]\n")
        resources_log.write(resources)

        # Notes
        notes_log = self.query_one("#notes-log", RichLog)
        notes_log.clear()
        notes_log.write(f"[bold cyan]Release Notes — {rel.name}[/bold cyan]\n\n")
        notes_log.write(notes)

        # Hooks
        hooks_log = self.query_one("#hooks-log", RichLog)
        hooks_log.clear()
        hooks_log.write(Syntax(hooks, "yaml", theme="monokai", line_numbers=True))

        # Events
        events_log = self.query_one("#events-log", RichLog)
        events_log.clear()
        events_log.write(f"[bold cyan]Kubernetes Events — namespace: {rel.namespace}[/bold cyan]\n\n")
        events_log.write(events)

    def action_close(self) -> None:
        self.dismiss(None)

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
