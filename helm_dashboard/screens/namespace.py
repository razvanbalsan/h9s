from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static


class NamespaceScreen(ModalScreen[str | None]):
    """Namespace selection dropdown."""

    BINDINGS = [Binding("escape", "cancel", "Close")]

    CSS = """
    NamespaceScreen {
        align: center middle;
    }

    #ns-box {
        width: 50;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #ns-title {
        width: 1fr;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }

    #ns-list {
        height: auto;
        max-height: 22;
    }
    """

    def __init__(self, namespaces: list[str], current: str) -> None:
        super().__init__()
        self._namespaces = namespaces
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="ns-box"):
            yield Static("⎈ Select Namespace", id="ns-title")
            option_list = OptionList(id="ns-list")
            yield option_list

    def on_mount(self) -> None:
        ol = self.query_one("#ns-list", OptionList)
        highlight_idx = 0
        for i, ns in enumerate(self._namespaces):
            label = f"  {ns}" if ns != self._current else f"▸ {ns}"
            ol.add_option(ns)
            if ns == self._current:
                highlight_idx = i
        ol.highlighted = highlight_idx
        ol.focus()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)
