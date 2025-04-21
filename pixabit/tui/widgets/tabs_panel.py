from typing import Optional  # Import Optional

from pixabit.tui.widgets.settings_panel import SettingsPanel
from pixabit.tui.widgets.tags_panel import TagsPanel
from pixabit.tui.widgets.tasks_panel import TaskListWidget
from textual import log, on  # Import on decorator
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
        log.info("Composing TabPanel...")  # Use instance log
        # Pass initial TabPanes directly
        with TabbedContent(initial="settings-panel", id="main-tabs"):
            with TabPane("Tags", id="tags-panel"):
                yield TagsPanel()
            with TabPane("Tasks", id="tasks-panel"):
                yield TaskListWidget()
            with TabPane("Settings", id="settings-panel"):
                yield SettingsPanel()
            # Add Challenges pane later when widget exists
            # with TabPane("Challenges", ChallengeListWidget(), id="challenges-panel"):
            #      pass

    # FUNC: action_show_tab
    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab when triggered by a binding."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabbed_content.active = tab
            self.log(f"Switched to tab: {tab}")
        except Exception as e:
            self.log.error(f"Failed to switch tab to '{tab}': {e}")

    # FUNC: get_active_content_widget (Helper for App)
    def get_active_content_widget(self) -> Optional[Widget]:
        """Returns the main content widget within the currently active TabPane."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_pane = tabbed_content.active_pane
            if active_pane and active_pane.children:
                # Assume the first child of the pane is the main content widget
                return active_pane.children[0]
        except Exception as e:
            self.log.error(f"Error getting active content widget: {e}")
        return None

    # Optional: Handle tab activation to load data when tab is first shown
    @on(TabbedContent.TabActivated)
    async def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Load data for a tab when it becomes active, if needed."""
        self.log(f"Tab activated: {event.tab.id}")
        pane = event.pane
        if pane:
            content_widget = pane.children[0]  # Get the content widget
            # Check if it needs loading and has the method
            if hasattr(content_widget, "load_or_refresh_data"):
                # Check if data is already loaded? (Could add a flag to widgets)
                # if not getattr(content_widget, "_data_loaded", False):
                self.log(f"Triggering initial load for {content_widget.id}")
                self.app.run_worker(content_widget.load_or_refresh_data, exclusive=True)
                # Set flag after worker starts? Or rely on widget internal state?
                # setattr(content_widget, "_data_loaded", True)


# Example Runner (Not needed for Pixabit)
# class TabPanelApp(App):
#     def compose(self) -> ComposeResult: yield TabPanel()
# if __name__ == "__main__":
#     app = TabPanelApp(); app.run()
