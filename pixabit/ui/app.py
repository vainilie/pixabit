# pixabit/ui/app.py
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from textual import events, on
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
from pixabit.ui.widgets.sidebar_stats import SidebarStats
from pixabit.ui.widgets.sleep_toggle import SleepToggle

# Importar widgets modulares
from pixabit.ui.widgets.stats_count import StatsCount
from pixabit.ui.widgets.task_widget import TaskDetailPanel, TaskListWidget, TaskTabContainer


class HabiticaApp(App):
    """Textual App for Habitica with sidebar and improved UI."""

    CSS_PATH = "style.tcss"
    BINDINGS = [
        Binding(key="q", action="quit", description="Salir"),
        Binding(key="escape", action="quit", description="Salir"),
        Binding(key="r", action="refresh_data", description="Actualizar datos"),
        # Add task-specific bindings
        Binding(key="c", action="complete_task", description="Complete task", show=False),
        Binding(key="e", action="edit_task", description="Edit task", show=False),
        Binding(key="d", action="delete_task", description="Delete task", show=False),
    ]

    def __init__(self):
        super().__init__()
        # Inicializar componentes principales
        self._initialize_dependencies()
        # Estado de la aplicación
        self.quest_data: Dict[str, Any] = {}
        self.sidebar_stats = None
        self.widgets_initialized = False
        self.task_container = None

    def _initialize_dependencies(self) -> None:
        """Inicializa las dependencias principales de la aplicación."""
        log.info("Initializing core dependencies")
        # Setup API client
        self.api_client = HabiticaClient()
        # Setup Static Content Manager
        static_cache_dir = HABITICA_DATA_PATH / "static_content"
        content_manager = StaticContentManager(cache_dir=static_cache_dir)
        # Setup Data Manager
        cache_dir = HABITICA_DATA_PATH
        self.data_manager = DataManager(api_client=self.api_client, static_content_manager=content_manager, cache_dir=cache_dir)

    async def on_mount(self) -> None:
        """Runs when the app starts: setup and load initial data."""
        # Get references to important widgets
        self.sidebar_stats = self.query_one(SidebarStats)
        self.task_container = self.query_one("#task-tab-container", TaskTabContainer)
        self.widgets_initialized = True

        # Initial data load
        await self.load_and_refresh_data(show_status=True)

    async def load_and_refresh_data(self, force_refresh: bool = False, show_status: bool = True) -> bool:
        """Carga todos los datos necesarios y actualiza la UI.

        Args:
            force_refresh: Si es True, forzar la recarga desde la API
            show_status: Si es True, mostrar mensajes de estado

        Returns:
            bool: True si los datos se cargaron y procesaron correctamente
        """
        if show_status:
            self.update_status("Loading Habitica data...", "loading")

        success = False
        try:
            # Paso 1: Cargar datos
            data_loaded = await self.data_manager.load_all_data(force_refresh=force_refresh)

            # Paso 2: Procesar datos
            if data_loaded:
                processing_successful = await self.data_manager.process_loaded_data()

                # Paso 3: Obtener datos de quest si el usuario está en una
                if processing_successful and self.data_manager.user:
                    if getattr(self.data_manager.user, "is_on_quest", False):
                        self.quest_data = await self._get_quest_data()

                # Paso 4: Actualizar UI con los datos cargados
                await self.update_ui_with_data(data_loaded, processing_successful)

                # Establecer éxito general
                success = processing_successful

                if show_status:
                    if success:
                        self.update_status("Data loaded successfully", "success")
                    else:
                        self.update_status("Error processing data", "error")
            else:
                if show_status:
                    self.update_status("Failed to load data", "error")

        except Exception as e:
            log.error(f"Data loading error: {e}")
            if show_status:
                self.update_status(f"Error: {str(e)}", "error")

        return success

    async def _get_quest_data(self) -> Dict[str, Any]:
        """Gets quest data from the API or data manager."""
        if not self.data_manager or not self.data_manager.user:
            return {}

        # En una implementación real, obtendrías estos datos de party.quest
        # Este es solo un placeholder
        is_boss = getattr(self.data_manager.user, "is_on_boss_quest", False)

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
        if self.sidebar_stats and self.widgets_initialized:
            self.sidebar_stats.update_status(message, status_class)
        else:
            log.info(f"Status update: {message}")

    async def update_ui_with_data(self, data_loaded: bool, processing_successful: bool) -> None:
        """Update UI widgets with data from DataManager."""
        if not self.data_manager or not self.widgets_initialized:
            log.error("DataManager is not initialized or widgets not ready when trying to update UI.")
            return

        try:
            # Get widget references
            user_info_widget = self.query_one("#user-info-static", Static)
            stats_widget = self.query_one(StatsCount)
            sidebar_stats = self.query_one(SidebarStats)
            sleep_toggle = self.query_one(SleepToggle)

            # Update widgets if data is available
            if self.data_manager.user and data_loaded and processing_successful:
                # Update user info
                username = self.data_manager.user.username
                user_class = self.data_manager.user.klass
                is_sleeping = getattr(self.data_manager.user, "is_sleeping", False)

                # Emojis
                class_emoji = {"warrior": "🗡️", "wizard": "🧙", "healer": "💚", "rogue": "⚔️", "": "👤"}.get(user_class.lower(), "👤")

                # Update widgets
                user_info_widget.update(f"{class_emoji} [b]{username}[/b]")
                stats_widget.update_display(self.data_manager.user)
                sidebar_stats.update_sidebar_stats(self.data_manager.user, self.quest_data)
                sleep_toggle.update_sleep_state(self.data_manager.user)

                # Refresh task data if task container is initialized
                if self.task_container:
                    await self.task_container.refresh_data()
            else:
                # Reset widgets if no data
                user_info_widget.update("Failed to load user data")
                stats_widget.update_display(None)
                sidebar_stats.update_sidebar_stats(None)
                sleep_toggle.update_sleep_state(None)
        except Exception as e:
            log.error(f"Error updating UI with data: {e}")

    async def on_data_changed(self, event_data: Dict[str, Any] = None) -> None:
        """Manejador de eventos para cuando cambian los datos.
        Esto puede ser invocado por cualquier widget que modifique los datos.

        Args:
            event_data: Datos opcionales sobre el cambio
        """
        log.info(f"Data changed event received: {event_data}")
        await self.load_and_refresh_data(force_refresh=True)

    async def action_refresh_data(self) -> None:
        """Action handler for manual data refresh (key binding 'r')."""
        self.update_status("Manually refreshing data...", "loading")
        await self.load_and_refresh_data(force_refresh=True)

    # Task-related action handlers

    async def action_complete_task(self) -> None:
        """Complete the currently selected task."""
        if not self.task_container:
            return

        # Use direct widget references for simplicity
        detail_panel = self.task_container.query_one(TaskDetailPanel)
        if detail_panel and detail_panel.current_task:
            task_id = detail_panel.current_task.get("id", "")
            detail_panel.post_message(TaskDetailPanel.CompleteTask(task_id))

    async def action_edit_task(self) -> None:
        """Edit the currently selected task."""
        if not self.task_container:
            return

        detail_panel = self.task_container.query_one(TaskDetailPanel)
        if detail_panel and detail_panel.current_task:
            task_id = detail_panel.current_task.get("id", "")
            detail_panel.post_message(TaskDetailPanel.EditTask(task_id))

    async def action_delete_task(self) -> None:
        """Delete the currently selected task."""
        if not self.task_container:
            return

        detail_panel = self.task_container.query_one(TaskDetailPanel)
        if detail_panel and detail_panel.current_task:
            task_id = detail_panel.current_task.get("id", "")
            detail_panel.post_message(TaskDetailPanel.DeleteTask(task_id))

    # Event handlers for task-related messages

    @on(TaskTabContainer.ScoreTaskRequest)
    async def handle_score_task_request(self, message: TaskTabContainer.ScoreTaskRequest) -> None:
        """Handle scoring a task."""
        if not self.data_manager:
            self.update_status("No data manager available to score tasks", "error")
            return

        try:
            if await self.data_manager.score_task(message.task_id, message.direction):
                self.update_status(f"Task scored {message.direction}", "success")
                # Refresh data after scoring
                await self.load_and_refresh_data(force_refresh=True, show_status=False)
            else:
                self.update_status("Failed to score task", "error")
        except Exception as e:
            log.error(f"Error scoring task: {e}")
            self.update_status(f"Error: {str(e)}", "error")

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
                            # Pasamos una referencia del método on_data_changed para que el widget
                            # pueda notificar cambios en los datos
                            yield SleepToggle(api_client=self.api_client, status_update_callback=self.update_status, on_data_changed=self.on_data_changed)
                        with TabPane("Tasks", id="tasks"):
                            # Integramos el contenedor de tareas aquí
                            yield TaskTabContainer(
                                id="task-tab-container", data_manager=self.data_manager, api_client=self.api_client, on_data_changed=self.on_data_changed
                            )
                        with TabPane("Tags", id="tags"):
                            yield Static("Tags content goes here")
                        with TabPane("Challenges", id="challenges"):
                            yield Static("Challenges content goes here")
                        with TabPane("Party", id="party"):
                            yield Static("Party content goes here")
                        with TabPane("Messages", id="messages"):
                            yield Static("Messages content goes here")
                        with TabPane("Settings", id="settings"):
                            yield Static("Settings content goes here")


if __name__ == "__main__":
    app = HabiticaApp()
    app.run()
