from __future__ import annotations

import asyncio

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, RichLog, Static, TabbedContent, TabPane, TextArea

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

# DataTable IDs that support row-copy via 'y'
_ROW_COPY_TABLES = {"tab-history": "#history-table",
                    "tab-resources": "#resources-table",
                    "tab-events": "#events-table"}


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
        Binding("y", "copy_row", "Copy row", show=False),
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

    /* Read-only TextArea tabs (Values, Manifest, Notes, Hooks) */
    TextArea {
        height: 1fr;
        border: none;
        padding: 0;
    }

    /* Remove the default focus border on TextArea */
    TextArea:focus {
        border: none;
    }

    RichLog {
        height: 1fr;
        background: $surface;
        scrollbar-size: 1 1;
    }

    #history-table, #resources-table, #events-table {
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
                yield Static(
                    "[dim]Esc: Back  |  1-8: Tabs  |  Cmd+C: Copy selection  |  y: Copy row[/dim]",
                    id="detail-hint",
                )
            with TabbedContent(id="detail-tabs"):
                with TabPane("Overview", id="tab-overview"):
                    yield RichLog(id="overview-log", wrap=True, markup=True)
                with TabPane("History", id="tab-history"):
                    yield DataTable(
                        id="history-table", cursor_type="row", zebra_stripes=True
                    )
                with TabPane("Values", id="tab-values"):
                    yield TextArea(
                        "", id="values-text",
                        read_only=True, language="yaml",
                        show_line_numbers=True, theme="monokai",
                    )
                with TabPane("Manifest", id="tab-manifest"):
                    yield TextArea(
                        "", id="manifest-text",
                        read_only=True, language="yaml",
                        show_line_numbers=True, theme="monokai",
                    )
                with TabPane("Resources", id="tab-resources"):
                    yield DataTable(
                        id="resources-table", cursor_type="row", zebra_stripes=True
                    )
                with TabPane("Notes", id="tab-notes"):
                    yield TextArea(
                        "", id="notes-text",
                        read_only=True, theme="monokai",
                    )
                with TabPane("Hooks", id="tab-hooks"):
                    yield TextArea(
                        "", id="hooks-text",
                        read_only=True, language="yaml",
                        show_line_numbers=True, theme="monokai",
                    )
                with TabPane("Events", id="tab-events"):
                    yield DataTable(
                        id="events-table", cursor_type="row", zebra_stripes=True
                    )

    async def on_mount(self) -> None:
        hist_table = self.query_one("#history-table", DataTable)
        hist_table.add_columns("Rev", "Updated", "Status", "Chart", "App Ver", "Description")

        res_table = self.query_one("#resources-table", DataTable)
        res_table.add_columns("Kind", "Name", "Ready", "Status", "Age")

        evt_table = self.query_one("#events-table", DataTable)
        evt_table.add_columns("Age", "Last Seen", "Type", "Reason", "Object", "Message")

        self._load_details()

    @work(thread=False)
    async def _load_details(self) -> None:
        rel = self._release

        # Overview (Rich markup — keep as RichLog)
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

        # Load all tabs concurrently
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
        # Narrow types (asyncio.gather infers Sequence[object])
        history_: list[HelmRevision] = list(history)  # type: ignore[arg-type]
        values_: str = str(values)
        manifest_: str = str(manifest)
        resources_: list[K8sResource] = list(resources)  # type: ignore[arg-type]
        notes_: str = str(notes)
        hooks_: str = str(hooks)
        events_: list[K8sEvent] = list(events)  # type: ignore[arg-type]

        # ── History ──────────────────────────────────────────────────────────
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

        # ── Values (TextArea — selectable, Ctrl+C copies) ────────────────────
        values_ta = self.query_one("#values-text", TextArea)
        values_ta.language = "yaml"
        values_ta.text = values_
        values_ta.move_cursor((0, 0))

        # ── Manifest (TextArea) ───────────────────────────────────────────────
        manifest_ta = self.query_one("#manifest-text", TextArea)
        manifest_ta.text = manifest_
        manifest_ta.move_cursor((0, 0))

        # ── Resources (DataTable — y copies selected row) ─────────────────────
        res_table = self.query_one("#resources-table", DataTable)
        res_table.clear()
        for r in resources_:
            icon = _KIND_ICONS.get(r.kind, "📦")
            if r.status in _OK_STATUSES:
                status_style = "green"
            elif r.status in _ERROR_STATUSES:
                status_style = "red bold"
            else:
                status_style = "yellow"
            res_table.add_row(
                f"{icon} {r.kind}",
                r.name,
                r.ready,
                Text(r.status, style=status_style),
                r.age,
                key=f"{r.kind}/{r.name}",
            )

        # ── Notes (TextArea) ──────────────────────────────────────────────────
        notes_ta = self.query_one("#notes-text", TextArea)
        notes_ta.text = notes_
        notes_ta.move_cursor((0, 0))

        # ── Hooks (TextArea) ──────────────────────────────────────────────────
        hooks_ta = self.query_one("#hooks-text", TextArea)
        hooks_ta.text = hooks_
        hooks_ta.move_cursor((0, 0))

        # ── Events (DataTable — y copies selected row) ────────────────────────
        evt_table = self.query_one("#events-table", DataTable)
        evt_table.clear()
        for e in events_:
            type_text = Text(e.type, style="red bold" if e.type == "Warning" else "dim")
            count_suffix = f" ×{e.count}" if e.count > 1 else ""
            evt_table.add_row(
                e.age,
                e.last_seen,
                type_text,
                e.reason,
                e.object_ref,
                e.message + count_suffix,
            )

    # ── Actions ───────────────────────────────────────────────────────────────

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

    def action_copy_row(self) -> None:
        """Copy the selected DataTable row to the system clipboard (y key)."""
        active_tab = self.query_one("#detail-tabs", TabbedContent).active
        table_id = _ROW_COPY_TABLES.get(active_tab)
        if not table_id:
            return
        table = self.query_one(table_id, DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row = table.get_row_at(table.cursor_row)
        text = "\t".join(
            cell.plain if isinstance(cell, Text) else str(cell)
            for cell in row
        )
        self.app.copy_to_clipboard(text)
        self.notify("Row copied to clipboard", timeout=2)

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
            old_values, new_values,  # type: ignore[arg-type]
            old_label=f"revision {old_revision}",
            new_label=f"revision {rel.revision} (current)",
        )
        header = f"# Values diff: rev {old_revision} → rev {rel.revision} (current)\n\n"
        values_ta = self.query_one("#values-text", TextArea)
        values_ta.language = None   # plain text for diff (no yaml highlighting)
        values_ta.text = header + diff
        values_ta.move_cursor((0, 0))
        self.query_one("#detail-tabs", TabbedContent).active = "tab-values"
        self.notify(f"Diff: revision {old_revision} vs current", timeout=3)
