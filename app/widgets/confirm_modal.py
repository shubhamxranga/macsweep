"""
MacSweep — Confirmation Modal
Reusable modal screen for confirming potentially destructive actions.
"""

from textual.screen import ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, Input
from textual.app import ComposeResult
from textual.binding import Binding

class ConfirmModal(ModalScreen[bool]):
    """Modal screen for action confirmation."""
    
    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #modal-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #modal-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    
    #modal-desc {
        text-align: center;
        margin-bottom: 1;
    }
    
    #modal-danger-input {
        margin-bottom: 1;
        border: tall $error;
    }
    
    #modal-buttons {
        align: center middle;
        margin-top: 1;
    }
    
    #modal-buttons Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        title: str,
        description: str,
        require_yes: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.title_text = title
        self.desc_text = description
        self.require_yes = require_yes

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(self.title_text, id="modal-title")
            yield Label(self.desc_text, id="modal-desc")
            
            if self.require_yes:
                yield Label("Type 'yes' to confirm high-risk operation:", classes="warning")
                yield Input(placeholder="type yes here...", id="modal-danger-input")
                
            with Horizontal(id="modal-buttons"):
                yield Button("Confirm", variant="error", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        if self.require_yes:
            self.query_one("#confirm-btn", Button).disabled = True
            self.query_one("#modal-danger-input", Input).focus()
        else:
            self.query_one("#confirm-btn", Button).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.require_yes and event.input.id == "modal-danger-input":
            self.query_one("#confirm-btn", Button).disabled = (event.value.strip().lower() != "yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
