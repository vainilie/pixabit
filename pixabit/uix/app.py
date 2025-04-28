import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Static

from pixabit.api.client import HabiticaClient
from pixabit.config import HABITICA_DATA_PATH
from pixabit.helpers._logger import log
from pixabit.models.challenge import Challenge, ChallengeList
from pixabit.models.game_content import StaticContentManager
from pixabit.models.task import Daily, Task, TaskList
from pixabit.services.data_manager import DataManager


class StaticApp(App):
    """Textual App that manages its own DataManager."""

    def __init__(self):
        super().__init__()
        self.data_manager: DataManager | None = None

    async def on_mount(self) -> None:
        """Runs when the app starts: setup the data manager."""
        log.info("--- StaticApp: Starting DataManager setup ---")

        # 1. Setup Dependencies
        api_client = HabiticaClient()
        static_cache_dir = HABITICA_DATA_PATH / "static_content"
        content_manager = StaticContentManager(cache_dir=static_cache_dir)
        test_cache_dir = HABITICA_DATA_PATH
        self.data_manager = DataManager(api_client=api_client, static_content_manager=content_manager, cache_dir=test_cache_dir)

        log.info(f"DataManager instantiated (Cache: {test_cache_dir}).")

        # 2. Load All Data
        log.info("Loading all data using DataManager...")
        await self.data_manager.load_all_data(force_refresh=False)  # Considera force_refresh=True para probar carga API

        # **OPCIONAL PERO RECOMENDADO:** Logea si el usuario se cargó en load_all_data
        if self.data_manager.user:
            log.success(f"User data loaded: {self.data_manager.user.username}")
        else:
            log.error("User data failed to load.")

        # 3. Process Loaded Data
        log.info("Processing loaded data...")
        processing_successful = await self.data_manager.process_loaded_data()
        if not processing_successful:
            log.error("Data processing phase failed. Results may be incomplete.")
            # Aunque el procesamiento falle, el usuario cargado *podría* estar disponible

        log.success("Data loading and processing phases complete.")

        # 4. Find the user_info_static widget and update its content
        user_info_widget = self.query_one("#user-info-static", Static)  # Busca el widget por su ID

        if self.data_manager and self.data_manager.user:
            user_info_widget.update(f"User: {self.data_manager.user.username}")  # Actualiza el texto
            # O si quieres mostrar MP: user_info_widget.update(f"User MP: {self.data_manager.user.mp}")
            log.info(f"Updated user info widget with username: {self.data_manager.user.username}")
        else:
            user_info_widget.update("Failed to load user data.")  # Muestra un mensaje de fallo
            log.error("Could not update user info widget: user data not available.")

        # self.refresh() # Ya no es necesario llamar refresh() aquí, update() se encarga de la visualización

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        # Un Container es útil para organizar widgets
        # yield Container(
        #     Static("Hello, world!"),
        #     Static("Loading user data...", id="user-info-static"), # Dale un ID al widget Static
        # )
        # O simplemente yield directamente si no necesitas el contenedor por ahora:
        yield Static("Hello, world!")
        yield Static("Loading user data...", id="user-info-static")  # Dale un ID al widget Static


if __name__ == "__main__":
    app = StaticApp()
    app.run()
