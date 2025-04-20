from pixabit.tui.widgets.settings_panel import SettingsPanel
from pixabit.tui.widgets.tags_panel import TagsPanel
from pixabit.tui.widgets.tasks_panel import TasksPanel
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Label,
    Markdown,
    Static,
    Tab,
    TabbedContent,
    TabPane,
    Tabs,
)


class TabPanel(Widget):
    """An example of tabbed content."""

    CSS_PATH = "pixabit.tcss"

    BINDINGS = [
        ("l", "show_tab('tags-panel')", "Tags"),
        ("j", "show_tab('tasks-panel')", "Tasks"),
        ("p", "show_tab('settings-panel')", "Settings"),
    ]

    def compose(self) -> ComposeResult:
        """Composes the tabs and their corresponding content panels."""
        # Pestañas
        log.info("cargando el panel")
        with TabbedContent(initial="settings-panel"):
            with TabPane("Tags", id="tags-panel"):
                yield TagsPanel()
            with TabPane("Tasks", id="tasks-panel"):
                yield TasksPanel()
            with TabPane("Settings", id="settings-panel"):
                yield SettingsPanel()

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        tabs = self.get_child_by_type(TabbedContent)
        tabs.active = tab


if __name__ == "__main__":
    app = TabPanel()
    app.run()
