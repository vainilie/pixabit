# previous_tui_files/backup.py (GENERIC EXAMPLE - Not App Specific)

# SECTION: MODULE DOCSTRING
"""GENERIC EXAMPLE: Demonstrates various Textual Button styles and states.
Not directly related to Pixabit backup functionality. Can be discarded.
"""

# SECTION: IMPORTS
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static


# SECTION: EXAMPLE WIDGET
# KLASS: ButtonsApp (Generic Example)
class ButtonsApp(Vertical):
    """A widget demonstrating button variants."""

    DEFAULT_CSS = """
    ButtonsApp { /* Renamed from root Screen selector */
        /* Basic styling for the container */
        padding: 1;
        border: thick $accent;
    }
    Button {
        margin: 1 2; /* Spacing around buttons */
    }
    Horizontal > VerticalScroll {
        width: 24; /* Width for columns if used */
    }
    .header {
        margin: 1 0 0 2;
        text-style: bold;
    }
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the button examples."""
        yield Horizontal(
            VerticalScroll(
                Static("Standard Buttons", classes="header"),
                Button("Default", id="btn_default"),
                Button("Primary!", variant="primary", id="btn_primary"),
                Button.success("Success!", id="btn_success"),
                Button.warning("Warning!", id="btn_warning"),
                Button.error("Error!", id="btn_error"),
            ),
            VerticalScroll(
                Static("Disabled Buttons", classes="header"),
                Button("Default", disabled=True),
                Button("Primary!", variant="primary", disabled=True),
                Button.success("Success!", disabled=True),
                Button.warning("Warning!", disabled=True),
                Button.error("Error!", disabled=True),
            ),
        )

    # FUNC: on_button_pressed
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button press events for the example."""
        # In a real app, this would trigger an action or post a message
        self.log(
            f"Button pressed: id='{event.button.id}', label='{event.button.label}'"
        )
        # Example exit based on button press (not typical for a real widget)
        # self.app.exit(f"Pressed: {event.button.id or event.button.label}")


# Example App Runner (Not needed for Pixabit integration)
# if __name__ == "__main__":
#     class ExampleRunner(App):
#         def compose(self) -> ComposeResult: yield ButtonsApp()
#     app = ExampleRunner()
#     app.run()
