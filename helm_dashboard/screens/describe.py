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
        name: str = self._name or ""
        log.write(f"Loading describe for {self._kind}/{name}...\n")
        output = await describe_resource(self._kind, name, self._namespace)
        log.clear()
        log.write(output)

    def action_close(self) -> None:
        self.dismiss(None)
