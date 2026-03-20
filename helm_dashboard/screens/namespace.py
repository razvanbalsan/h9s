from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, SelectionList, Static


class _BoundedSelectionList(SelectionList[str]):
    """SelectionList that stops at first/last item instead of wrapping."""

    def action_cursor_up(self) -> None:
        if self.highlighted is not None and self.highlighted > 0:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.highlighted is not None and self.highlighted < self.option_count - 1:
            super().action_cursor_down()


class NamespaceScreen(ModalScreen[frozenset[str] | None]):
    """Multi-namespace selector.  Returns the selected set (empty = All), or None if cancelled."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    CSS = """
    NamespaceScreen {
        align: center middle;
    }

    #ns-box {
        width: 52;
        height: auto;
        max-height: 38;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #ns-title {
        width: 1fr;
        text-style: bold;
        color: $accent;
        margin: 0 0 0 0;
    }

    #ns-hint {
        width: 1fr;
        color: $text-muted;
        margin: 0 0 1 0;
    }

    #ns-list {
        height: auto;
        max-height: 22;
    }

    #ns-buttons {
        height: 3;
        align: center middle;
        margin: 1 0 0 0;
    }

    #ns-buttons Button {
        margin: 0 1;
        min-width: 14;
    }
    """

    def __init__(self, namespaces: list[str], current: frozenset[str]) -> None:
        super().__init__()
        self._namespaces = namespaces
        self._current = current

    def compose(self) -> ComposeResult:
        selections = [(ns, ns, ns in self._current) for ns in self._namespaces]
        with Vertical(id="ns-box"):
            yield Static("⎈ Select Namespaces", id="ns-title")
            yield Static("[dim]Space: toggle  Enter: confirm  Esc: cancel[/dim]", id="ns-hint")
            yield _BoundedSelectionList(*selections, id="ns-list")
            with Horizontal(id="ns-buttons"):
                yield Button("Confirm", id="btn-confirm", variant="primary")
                yield Button("All", id="btn-all", variant="default")
                yield Button("Cancel", id="btn-cancel", variant="error")

    def on_mount(self) -> None:
        self.query_one("#ns-list", _BoundedSelectionList).focus()

    def action_confirm(self) -> None:
        sl = self.query_one("#ns-list", _BoundedSelectionList)
        self.dismiss(frozenset(str(v) for v in sl.selected))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-confirm")
    def _on_confirm(self) -> None:
        self.action_confirm()

    @on(Button.Pressed, "#btn-all")
    def _on_all(self) -> None:
        self.dismiss(frozenset())

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)
