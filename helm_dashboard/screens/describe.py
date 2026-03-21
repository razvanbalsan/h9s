"""Resource describe screen."""
from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from helm_dashboard.helm_client import describe_resource

_WRAP_THRESHOLD = 120


class DescribeScreen(ModalScreen[None]):
    """Show kubectl describe output for a Kubernetes resource."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("w", "toggle_wrap", "Wrap", show=False),
    ]

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
        self._wrap = True   # resolved at mount time
        self._last_output: str = ""  # cached for wrap reload

    def compose(self) -> ComposeResult:
        with Vertical(id="desc-container"):
            with Horizontal(id="desc-header"):
                yield Static(
                    f"⎈ Describe: {self._kind}/{self._name}",
                    id="desc-title",
                )
                yield Static("[dim]Esc: Back  |  w: Wrap[/dim]", id="desc-hint")
            yield RichLog(id="desc-output", wrap=True, markup=False)
        # No Footer() — DescribeScreen is a ModalScreen.

    async def on_mount(self) -> None:
        self._wrap = self.app.size.width < _WRAP_THRESHOLD
        self.query_one("#desc-output", RichLog).wrap = self._wrap
        self._load_describe()

    def on_resize(self, event) -> None:  # type: ignore[override]
        new_wrap = event.size.width < _WRAP_THRESHOLD
        if new_wrap == self._wrap:
            return
        self._wrap = new_wrap
        self._apply_wrap()

    @work(thread=False)
    async def _load_describe(self) -> None:
        log = self.query_one("#desc-output", RichLog)
        name: str = self._name or ""
        log.write(f"Loading describe for {self._kind}/{name}...\n")
        output = await describe_resource(self._kind, name, self._namespace)
        self._last_output = output
        log.wrap = self._wrap
        log.clear()
        log.write(output)

    def _apply_wrap(self) -> None:
        """Re-render the describe output with the current wrap setting."""
        log = self.query_one("#desc-output", RichLog)
        log.wrap = self._wrap
        if self._last_output:
            log.clear()
            log.write(self._last_output)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_toggle_wrap(self) -> None:
        """Toggle text wrapping for the describe output (w key)."""
        self._wrap = not self._wrap
        self._apply_wrap()
        self.notify(f"Wrap {'on' if self._wrap else 'off'}", timeout=1)
