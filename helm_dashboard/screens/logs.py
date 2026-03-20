"""Pod log viewer screen."""
from __future__ import annotations

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
        Binding("d", "describe_pod", "Describe", show=False),
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

    def action_describe_pod(self) -> None:
        if not self._selected_pod:
            self.app.notify("No pod selected", severity="warning")
            return
        from helm_dashboard.screens.describe import DescribeScreen
        self.app.push_screen(
            DescribeScreen("pod", self._selected_pod, self._namespace)
        )
