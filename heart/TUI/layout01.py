from textual.app import App, ComposeResult
from textual.widgets import Header


class HeaderApp(App):

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, time_format="%H:%M:%S", name="PIXABIT")

    def on_mount(self) -> None:
        self.title = "PIXABIT"
        self.sub_title = "Habitica TUI Client"


if __name__ == "__main__":
    app = HeaderApp()
    app.run()
