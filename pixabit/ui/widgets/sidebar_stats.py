# pixabit/ui/widgets/sidebar_stats.py

from typing import Any, Dict

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static

from pixabit.helpers._logger import log
from pixabit.models.user import User


class SidebarStats(Vertical):
    """Widget that displays detailed user stats in the sidebar."""

    DEFAULT_CSS = """
    SidebarStats {
        width: 100%;
        height: auto;
        background: $panel;
    }

    #stats-container {
        width: 100%;
        padding: 1;
    }

    #api-status-label {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;

        & Label {
        width:15;
        max-width: 15
        }

        & .section-title {
            text-style: bold;
            color: $accent;
            padding: 0 1;
        }

        & .stat-label {
            width: 100%;
            padding-left: 1;
        }

        & .progress-label {
            width: 100%;
            text-align: center;
            margin-bottom: 0;
        }

        & ProgressBar {
            margin-bottom: 1;
        }

        & #day-start-time {
            color: $text;
        }

        & #needs-cron {
            color: $warning;
            text-style: bold;
        }

        & #last-log {
            height: auto;
        }
    }
    """

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None):
        """Inicializa el widget de estadísticas de la barra lateral."""
        super().__init__(name=name, id=id, classes=classes)
        self._status_label = None

    # Reactive variables
    user_class: reactive[str] = reactive("Unknown")
    is_sleeping: reactive[bool] = reactive(False)
    quest_progress: reactive[float] = reactive(0.0)
    quest_name: reactive[str] = reactive("")
    total_damage: reactive[float] = reactive(0.0)
    day_start: reactive[str] = reactive("00:00")
    needs_cron: reactive[bool] = reactive(False)
    last_log: reactive[str] = reactive("")

    def on_mount(self):
        """Se ejecuta cuando el widget es montado."""
        self._status_label = self.query_one("#api-status-label", Label)
        self._status_label.update("Esperando datos...")

    def update_sidebar_stats(self, user_data: User | None, quest_data: Dict[str, Any] | None = None) -> None:
        """Updates sidebar stats with user and quest data."""
        if not user_data:
            self.user_class = "Unknown"
            self.is_sleeping = False
            self.quest_progress = 0.0
            self.quest_name = "No Quest"
            self.total_damage = 0.0
            self.day_start = "00:00"
            self.needs_cron = False
            self.last_log = "No activity logs available"
            return

        # Sleep status with emoji
        try:
            self.is_sleeping = getattr(user_data, "is_sleeping", False)
        except Exception:
            self.is_sleeping = False

        # Quest data
        if quest_data:
            self.quest_name = quest_data.get("title", "Unknown Quest")
            # Calculate quest progress as a percentage
            progress = quest_data.get("progress", 0)
            total = quest_data.get("progressNeeded")
            self.quest_progress = (progress / total) if total > 0 else 0
        else:
            self.quest_name = "No quest"
            self.quest_progress = 0.0

        # Total damage - assume we have a method or attribute for this
        self.total_damage = getattr(user_data, "total_damage", 0.0)

        # Day start time - format: "HH:MM"
        preferences = user_data.preferences
        if preferences:
            day_start = preferences.day_start
            self.day_start = f"{day_start:02d}:00"
        else:
            self.day_start = "00:00"

        # Needs cron check
        self.needs_cron = getattr(user_data, "needs_cron", False)

        # Last activity log (simplified - in real app, get from actual logs)
        # In a real implementation, you'd fetch this from user history or activity logs
        last_action = getattr(user_data, "last_action", None)
        if last_action:
            self.last_log = f"{last_action.get('timestamp', 'Unknown time')}: {last_action.get('message', 'Unknown action')}"
        else:
            self.last_log = "No recent activity"

    def watch_is_sleeping(self, sleeping: bool) -> None:
        """Updates the sleep status label when sleep state changes."""
        try:
            emoji = "💤" if sleeping else "👁️‍🗨️"
            status = "Sleeping" if sleeping else "Awake"
            self.query_one("#sleep-status", Label).update(f"{emoji} {status}")
        except Exception as e:
            log.error(f"Error updating sleep status: {e}")

    def watch_quest_progress(self, progress: float) -> None:
        """Updates the quest progress bar when progress changes."""
        try:
            progress_bar = self.query_one("#quest-progress", ProgressBar)
            progress_bar.update(progress)
        except Exception as e:
            log.error(f"Error updating quest progress: {e}")

    def watch_quest_name(self, name: str) -> None:
        """Updates the quest name when it changes."""
        try:
            self.query_one("#quest-name", Label).update(f"🐣 {name}")
        except Exception as e:
            log.error(f"Error updating quest name: {e}")

    def watch_user_class(self, class_name: str) -> None:
        """Updates the user class label when it changes."""
        try:
            self.query_one("#user-class", Label).update(class_name)
        except Exception as e:
            log.error(f"Error updating user class: {e}")

    def watch_total_damage(self, damage: float) -> None:
        """Updates the total damage when it changes."""
        try:
            self.query_one("#total-damage", Label).update(f"💥 {damage:.1f}")
        except Exception as e:
            log.error(f"Error updating total damage: {e}")

    def watch_day_start(self, time: str) -> None:
        """Updates the day start time when it changes."""
        try:
            self.query_one("#day-start-time", Label).update(f"🌙 {time}")
        except Exception as e:
            log.error(f"Error updating day start time: {e}")

    def watch_needs_cron(self, needs_cron: bool) -> None:
        """Updates the cron status when it changes."""
        try:
            label = self.query_one("#needs-cron", Label)
            if needs_cron:
                label.update("⚠️ Cron needed!")
                label.add_class("needs-action")
            else:
                label.update("🆗 Cron")
                label.remove_class("needs-action")
        except Exception as e:
            log.error(f"Error updating cron status: {e}")

    def watch_last_log(self, log_text: str) -> None:
        """Updates the last activity log when it changes."""
        try:
            self.query_one("#last-log", Static).update(log_text)
        except Exception as e:
            self.update_status(f"Error updating last log: {e}")

    def update_status(self, message: str, status_class: str = "") -> None:
        """Updates the status label with a message and optional CSS class."""
        try:
            if self._status_label is None:
                self._status_label = self.query_one("#api-status-label", Label)

            # Limpiar clases anteriores
            self._status_label.remove_class("loading", "success", "error", "warning")

            # Añadir nueva clase si se proporciona
            if status_class:
                self._status_label.add_class(status_class)
            self._status_label.update(message)
        except Exception as e:
            log.error(f"Failed to update status: {e}")

    def compose(self) -> ComposeResult:
        """Create sidebar components."""
        yield Label("", id="sleep-status", classes="stat-label")

        yield Label("", id="quest-name", classes="stat-label")
        yield Label("", id="total-damage", classes="stat-label")

        yield Label("", id="day-start-time", classes="stat-label")
        yield Label("", id="needs-cron", classes="stat-label")

        yield Static("Loading activity...", id="last-log")
        yield Label("", id="api-status-label")
