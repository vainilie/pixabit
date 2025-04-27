# app.py
# Starter Structure – Grid Layout in Textual
# Here’s a basic layout using textual.app.App and textual.widgets

from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane, Tabs


class HabiticaTUI(App):
    CSS_PATH = "style.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(id="main-grid")
        yield Footer()

    def on_mount(self) -> None:
        grid = self.query_one("#main-grid", Grid)
        grid.add_class("main-layout")
        grid.place(
            sidebar=Static("Sidebar"),  # Replace with actual Menu widget
            main=TabbedContent(
                Tabs("Tasks", "Challenges", "Messages", "Party", "Settings"),
                TabPane("Tasks", id="tasks"),
                TabPane("Challenges", id="challenges"),
                TabPane("Messages", id="messages"),
                TabPane("Party", id="party"),
                TabPane("Settings", id="settings"),
                id="main-tabs",
            ),
        )


if __name__ == "__main__":
    HabiticaTUI().run()
