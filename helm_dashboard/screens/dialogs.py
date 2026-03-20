from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ConfirmDialog(ModalScreen[bool]):
    """Yes/No confirmation dialog."""

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog-box"):
            yield Label(f"[bold]{self._title}[/bold]")
            yield Label(self._message)
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", variant="error", id="btn-yes")
                yield Button("No", variant="primary", id="btn-no")

    @on(Button.Pressed, "#btn-yes")
    def on_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def on_no(self) -> None:
        self.dismiss(False)

    def key_y(self) -> None:
        self.dismiss(True)

    def key_n(self) -> None:
        self.dismiss(False)

    def key_escape(self) -> None:
        self.dismiss(False)


class InputDialog(ModalScreen[tuple[str, str] | None]):
    """Two-field input dialog (e.g., for adding a repo)."""

    def __init__(self, title: str, label1: str, label2: str) -> None:
        super().__init__()
        self._title = title
        self._label1 = label1
        self._label2 = label2

    def compose(self) -> ComposeResult:
        with Vertical(id="input-dialog-box"):
            yield Label(f"[bold]{self._title}[/bold]")
            yield Label(self._label1)
            yield Input(id="input-field-1", placeholder=self._label1)
            yield Label(self._label2)
            yield Input(id="input-field-2", placeholder=self._label2)
            with Horizontal(id="input-buttons"):
                yield Button("OK", variant="success", id="btn-ok")
                yield Button("Cancel", variant="primary", id="btn-cancel")

    @on(Button.Pressed, "#btn-ok")
    def on_ok(self) -> None:
        v1 = self.query_one("#input-field-1", Input).value.strip()
        v2 = self.query_one("#input-field-2", Input).value.strip()
        self.dismiss((v1, v2) if v1 and v2 else None)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)
