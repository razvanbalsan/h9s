"""Kubernetes context switching screen."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static


class _BoundedOptionList(OptionList):
    """OptionList that stops at first/last item instead of wrapping."""

    def action_cursor_up(self) -> None:
        if self.highlighted is not None and self.highlighted > 0:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.highlighted is not None and self.highlighted < self.option_count - 1:
            super().action_cursor_down()


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
            yield _BoundedOptionList(id="ctx-list")

    def on_mount(self) -> None:
        ol = self.query_one("#ctx-list", _BoundedOptionList)
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
