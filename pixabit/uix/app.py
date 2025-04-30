# pixabit/ui/app.py


import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, Switch, Tab, TabbedContent, TabPane

from pixabit.api.client import HabiticaClient
from pixabit.config import HABITICA_DATA_PATH
from pixabit.helpers._logger import log
from pixabit.models.game_content import StaticContentManager
from pixabit.models.user import User
from pixabit.services.data_manager import DataManager
from pixabit.uix.widgets.markdown_table_widget import MarkdownTableWidget
from pixabit.uix.widgets.sidebar_stats import SidebarStats
from pixabit.uix.widgets.sleep_toggle import SleepToggle

# Importar widgets modulares
from pixabit.uix.widgets.stats_count import StatsCount


class HabiticaApp(App):
    """Textual App for Habitica with sidebar and improved UI."""

    CSS = """

    #app-container {

        width: 100%;

        height: 100%;

        layout: grid;

        grid-size: 2;

        grid-columns: 1fr 3fr;

        grid-rows: 100%;

    }



    #sidebar {

        width: 100%;

        height: 100%;

        overflow-y: auto;

            & #api-status-label {

            margin-top: 1;

            padding: 1;

            background: $surface-darken-1;

            border: solid $accent;

            text-align: center;

        }

    }



    #main-content {

        width: 100%;

        height: 100%;

        background: $surface;

    }



    #header {

        dock: top;

        height: 1;

        background: $panel;

    }



    #user-info-container {

        width: 100%;

        background: $panel-lighten-1;

    }



    #user-info-static {

        width: 100%;

        text-align: center;

        text-style: bold;

        color: $text;

    }



    #content {

        padding: 1;





    }



    .loading {

        color: $warning;

        background: $panel-darken-1;

        padding: 1;

        text-align: center;

    }



    .success {

        color: $success;

    }



    .error {

        color: $error;

    }



    .warning {

        color: $warning;

    }

    Label{



        content-align: left middle;



    }

    """
    BINDINGS = [
        Binding(key="q", action="quit", description="Salir"),
        Binding(key="escape", action="quit", description="Salir"),
    ]

    def __init__(self):

        super().__init__()

        self.data_manager: DataManager | None = None

        self.api_client = HabiticaClient()

        self.quest_data: Dict[str, Any] = {}

        self.sidebar_stats = None

    async def on_mount(self) -> None:
        """Runs when the app starts: setup the data manager."""
        log.info("--- HabiticaApp: Starting DataManager setup ---")

        # Setup Dependencies

        api_client = HabiticaClient()

        static_cache_dir = HABITICA_DATA_PATH / "static_content"

        content_manager = StaticContentManager(cache_dir=static_cache_dir)

        cache_dir = HABITICA_DATA_PATH

        self.data_manager = DataManager(api_client=api_client, static_content_manager=content_manager, cache_dir=cache_dir)

        # Get references to important widgets

        self.sidebar_stats = self.query_one(SidebarStats)

        # Update status

        self.update_status("Loading Habitica data...", "loading")

        # Load All Data

        data_loaded = False

        processing_successful = False

        try:

            data_loaded = await self.data_manager.load_all_data(force_refresh=False)

            if data_loaded:

                processing_successful = await self.data_manager.process_loaded_data()

                # Try to get quest data if user is on quest

                if processing_successful and self.data_manager.user:

                    if getattr(self.data_manager.user, "is_on_quest", False):

                        # This is a placeholder - in a real implementation,

                        # you would fetch actual quest data

                        self.quest_data = await self._get_quest_data()

        except Exception as e:

            log.error(f"Data loading error: {e}")

        # Update UI with loaded data

        await self.update_ui_with_data(data_loaded, processing_successful)

        # Update final status

        if data_loaded and processing_successful:

            self.update_status("Data loaded successfully", "success")

        else:

            self.update_status("Failed to load data", "error")

    async def _get_quest_data(self) -> Dict[str, Any]:
        """Gets quest data from the API or data manager.

        In a real implementation, this would fetch actual quest data.

        This is a placeholder that creates some sample data.

        """
        # Placeholder for quest data - in real app, get from API

        if not self.data_manager or not self.data_manager.user:

            return {}

        # Check if user is on a boss quest

        is_boss = getattr(self.data_manager.user, "is_on_boss_quest", False)

        # Create sample quest data based on boss or collection type

        if is_boss:

            return {
                "type": "boss",
                "title": "The Mighty Dragon",
                "progress": 150,  # Current damage
                "progressNeeded": 500,  # Boss HP
                "boss": {"hp": 500, "name": "Dragon"},
            }

        else:

            # Collection quest

            return {
                "type": "collect",
                "title": "Gather Supplies",
                "progress": 7,  # Items collected
                "progressNeeded": 15,  # Items needed
                "collect": {"items": [{"name": "Wood", "count": 3}, {"name": "Stone", "count": 4}]},
            }

    def update_status(self, message: str, status_class: str = "") -> None:
        """Actualiza el mensaje de estado en la barra lateral.

        Args:
            message: Mensaje a mostrar

            status_class: Clase CSS para el estilo del mensaje

        """
        if self.sidebar_stats:

            self.sidebar_stats.update_status(message, status_class)

        else:

            log.warning(f"No sidebar stats available to show message: {message}")

    async def update_ui_with_data(self, data_loaded: bool, processing_successful: bool) -> None:
        """Update UI widgets with data from DataManager."""
        if not self.data_manager:

            log.error("DataManager is not initialized when trying to update UI.")

            return

        try:

            # Get widget references

            try:

                user_info_widget = self.query_one("#user-info-static", Static)

                stats_widget = self.query_one(StatsCount)

                sidebar_stats = self.query_one(SidebarStats)

                sleep_toggle = self.query_one(SleepToggle)

            except Exception as e:

                log.error(f"Error getting widget references: {e}")

                return

            # Update widgets if data is available

            if self.data_manager.user and data_loaded and processing_successful:

                # User info with emoji

                username = self.data_manager.user.username

                # Get user class and sleeping status

                user_class = self.data_manager.user.klass

                is_sleeping = False

                try:

                    is_sleeping = getattr(self.data_manager.user, "is_sleeping", False)

                except Exception:

                    pass

                # Update sleep toggle widget

                sleep_toggle.update_sleep_state(self.data_manager.user)

                # Format user info with emojis

                class_emoji = {"warrior": "🗡️", "wizard": "🧙", "healer": "💚", "rogue": "⚔️", "": "👤"}.get(user_class.lower(), "👤")

                sleep_emoji = "💤" if is_sleeping else "👁️"

                # Quest status

                quest_status = "No active quest"

                if getattr(self.data_manager.user, "is_on_quest", False):

                    quest_type = "Boss" if getattr(self.data_manager.user, "is_on_boss_quest", False) else "Collection"

                    quest_status = f"On {quest_type} Quest"

                user_info_widget.update(f"{class_emoji} [b]{username}[/b]")

                # Update stats widgets

                stats_widget.update_display(self.data_manager.user)

                sidebar_stats.update_sidebar_stats(self.data_manager.user, self.quest_data)

            else:

                # Reset widgets if no data

                user_info_widget.update("Failed to load user data")

                stats_widget.update_display(None)

                sidebar_stats.update_sidebar_stats(None)

                sleep_toggle.update_sleep_state(None)

        except Exception as e:

            log.error(f"Error updating UI with data: {e}")

    async def on_sleep_toggled(self, success: bool, sleep_value: bool) -> None:
        """Handle sleep toggle callback from SleepToggle widget.

        Args:
            success: Whether the toggle was successful

            sleep_value: The new sleep state

        """
        if success:

            # Reload user data

            self.update_status("Reloading user data...", "loading")

            data_reloaded = await self.data_manager.load_user(force_refresh=True)

            if data_reloaded:

                processing_success = await self.data_manager.process_loaded_data()

                if processing_success:

                    await self.update_ui_with_data(True, True)

                    self.update_status("Data refreshed after sleep toggle", "success")

                else:

                    self.update_status("Sleep toggled but error processing data", "warning")

            else:

                self.update_status("Sleep toggled but error reloading data", "warning")

    def compose(self) -> ComposeResult:
        """Create the UI layout with sidebar and main content."""
        with Container(id="app-container"):

            # Sidebar

            with Vertical(id="sidebar"):

                with Vertical(id="header"):

                    yield Static("Loading user...", id="user-info-static")

                # Sidebar stats

                yield SidebarStats()

            # Main content area

            with Vertical(id="main-content"):

                with Vertical(id="content"):

                    with TabbedContent(id="main-tabs"):

                        # Paneles de pestañas

                        with TabPane("User", id="user"):

                            yield Static("Main content area - Tasks will display here")

                            yield StatsCount()

                            yield SleepToggle(
                                api_client=self.api_client,
                                status_update_callback=self.update_status,  # Usar el método de la aplicación
                                on_sleep_toggled=self.on_sleep_toggled,
                            )

                        with TabPane("Tasks", id="tasks"):

                            yield Static("Challenges content goes here")

                        with TabPane("Tags", id="tags"):

                            yield Static("Party content goes here")

                        with TabPane("Challenges", id="challenges"):

                            # Placeholder for main content (tasks, etc.)

                            yield Static("Main content area - Tasks will display here")

                        with TabPane("Party", id="party"):

                            yield Static("Party content goes here")

                        with TabPane("Messages", id="messages"):

                            yield Static("Messages content goes here")

                        with TabPane("Settings", id="settings"):

                            yield Static("Settings content goes here")


if __name__ == "__main__":

    app = HabiticaApp()

    app.run()
