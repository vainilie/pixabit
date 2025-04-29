import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Digits, Label, ProgressBar, Static, Switch

from pixabit.api.client import HabiticaClient
from pixabit.config import HABITICA_DATA_PATH
from pixabit.helpers._logger import log
from pixabit.models.challenge import Challenge, ChallengeList
from pixabit.models.game_content import StaticContentManager
from pixabit.models.task import Daily, Task, TaskList
from pixabit.models.user import User
from pixabit.services.data_manager import DataManager


class StatsCount(Horizontal):
    """Widget that displays user stats in a horizontal layout."""

    DEFAULT_CSS = """
    StatsCount {
        /* Layout */
        height: auto;
        padding: 1 1;
        background: $panel;
        align: center middle;
        width: 100%;

        /* Child Alignment */
        &> Vertical {
            width: auto;
            height: auto;
            margin: 0 1;
            align: center top;
        }

        Label { width: auto; text-style: bold; color: $text; margin-bottom: 1; }
        Digits { width: auto; }

        /* Stat-specific Colors */
        #lvl-container Digits { color: $warning; }
        #mp-container Digits { color: $primary; }
        #hp-container Digits { color: $error; }
        #gp-container Digits { color: $warning-darken-2; }
        #exp-container Digits { color: $success; }
    }
    """

    # Reactive variables
    hp: reactive[int] = reactive(0)
    mp: reactive[int] = reactive(0)
    gp: reactive[int] = reactive(0)
    exp: reactive[int] = reactive(0)
    lvl: reactive[int] = reactive(0)
    max_exp: reactive[int] = reactive(0)
    max_hp: reactive[int] = reactive(50)  # Default values
    max_mp: reactive[int] = reactive(30)  # Default values

    def update_display(self, user_data: User | None) -> None:
        """Updates the widget's display based on data from the User model."""
        if not user_data or not hasattr(user_data, "stats") or user_data.stats is None:
            log.warning("StatsCount received no user data or user stats to display. Resetting.")
            # Reset to default values
            self.hp = 0
            self.mp = 0
            self.gp = 0
            self.exp = 0
            self.lvl = 0
            self.max_exp = 0
            self.max_hp = 50
            self.max_mp = 30
        else:
            # Update reactive variables with safe attribute handling
            self.hp = int(getattr(user_data.stats, "hp", 0))
            self.mp = int(getattr(user_data.stats, "mp", 0))
            self.gp = int(getattr(user_data.stats, "gp", 0))
            self.exp = int(getattr(user_data.stats, "exp", 0))
            self.lvl = int(getattr(user_data, "level", 0))

            # Use getattr with defaults for potentially missing attributes
            self.max_exp = int(getattr(user_data.stats, "max_exp", getattr(user_data.stats, "toNextLevel", 0)))
            self.max_hp = int(getattr(user_data.stats, "max_hp", getattr(user_data.stats, "maxHealth", 50)))
            self.max_mp = int(getattr(user_data.stats, "max_mp", getattr(user_data.stats, "maxMana", 30)))

        # Update tooltips
        self._update_tooltips()

    def _update_tooltips(self) -> None:
        """Updates tooltips for stat widgets."""
        try:
            self.query_one("#lvl-digit", Digits).tooltip = f"Level: {self.lvl}"
            self.query_one("#mp-digit", Digits).tooltip = f"Mana: {self.mp} / {self.max_mp}"
            self.query_one("#hp-digit", Digits).tooltip = f"Health: {self.hp} / {self.max_hp}"
            self.query_one("#exp-digit", Digits).tooltip = f"Experience: {self.exp} / {self.max_exp}"
            self.query_one("#gp-digit", Digits).tooltip = f"Gold: {self.gp}"
        except Exception as e:
            log.error(f"Error updating tooltips: {e}")

    # Watch methods to update UI when reactive variables change
    def watch_lvl(self, value: int) -> None:
        try:
            self.query_one("#lvl-digit", Digits).update(f"{value}LVL")
        except Exception as e:
            log.error(f"Error in watch_lvl: {e}")

    def watch_mp(self, value: int) -> None:
        try:
            self.query_one("#mp-digit", Digits).update(f"{value}MP")
        except Exception as e:
            log.error(f"Error in watch_mp: {e}")

    def watch_hp(self, value: int) -> None:
        try:
            self.query_one("#hp-digit", Digits).update(f"{value}HP")
        except Exception as e:
            log.error(f"Error in watch_hp: {e}")

    def watch_exp(self, value: int) -> None:
        try:
            self.query_one("#exp-digit", Digits).update(f"{value}XP")
        except Exception as e:
            log.error(f"Error in watch_exp: {e}")

    def watch_gp(self, value: int) -> None:
        try:
            self.query_one("#gp-digit", Digits).update(f"{value}GP")
        except Exception as e:
            log.error(f"Error in watch_gp: {e}")

    def compose(self) -> ComposeResult:
        """Create UI components."""
        with Vertical(id="lvl-container"):
            yield Digits(f"{self.lvl}LVL", id="lvl-digit")

        with Vertical(id="mp-container"):
            yield Digits(f"{self.mp}MP", id="mp-digit")

        with Vertical(id="hp-container"):
            yield Digits(f"{self.hp}HP", id="hp-digit")

        with Vertical(id="gp-container"):
            yield Digits(f"{self.gp}GP", id="gp-digit")

        with Vertical(id="exp-container"):
            yield Digits(f"{self.exp}XP", id="exp-digit")


class SidebarStats(Vertical):
    """Widget that displays detailed user stats in the sidebar."""

    DEFAULT_CSS = """
    SidebarStats {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface-darken-1;
        border-right: solid $accent;

        & Label {
            margin-bottom: 1;
        }

        & .section-title {
            text-style: bold;
            color: $accent;
            background: $panel-lighten-1;
            padding: 0 1;
            border-bottom: solid $accent;
            text-align: center;
            margin-top: 1;
            margin-bottom: 1;
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
            color: $text-muted;
        }

        & #needs-cron {
            color: $warning;
            text-style: bold;
        }

        & #last-log {
            background: $surface-darken-2;
            padding: 1;
            border: solid $accent;
            height: auto;
            max-height: 5;
            overflow-y: auto;
        }
    }
    """

    # Reactive variables
    user_class: reactive[str] = reactive("Unknown")
    is_sleeping: reactive[bool] = reactive(False)
    quest_progress: reactive[float] = reactive(0.0)
    quest_name: reactive[str] = reactive("")
    total_damage: reactive[float] = reactive(0.0)
    day_start: reactive[str] = reactive("00:00")
    needs_cron: reactive[bool] = reactive(False)
    last_log: reactive[str] = reactive("")

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

        # User class with emoji
        class_name = getattr(user_data, "class", "warrior")
        class_emojis = {"warrior": "⚔️", "mage": "🧙‍♂️", "healer": "💚", "rogue": "🗡️", "": "👤"}  # Default for no class
        self.user_class = f"{class_emojis.get(class_name.lower(), '👤')} {class_name.capitalize()}"

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
            self.quest_name = "No Active Quest"
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
            emoji = "💤" if sleeping else "👁️"
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
            self.query_one("#quest-name", Label).update(f"📜 {name}")
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
            self.query_one("#total-damage", Label).update(f"💥 Damage: {damage:.1f}")
        except Exception as e:
            log.error(f"Error updating total damage: {e}")

    def watch_day_start(self, time: str) -> None:
        """Updates the day start time when it changes."""
        try:
            self.query_one("#day-start-time", Label).update(f"🕒 Day starts at: {time}")
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
                label.update("✅ Cron up to date")
                label.remove_class("needs-action")
        except Exception as e:
            log.error(f"Error updating cron status: {e}")

    def watch_last_log(self, log_text: str) -> None:
        """Updates the last activity log when it changes."""
        try:
            self.query_one("#last-log", Static).update(log_text)
        except Exception as e:
            log.error(f"Error updating last log: {e}")

    def compose(self) -> ComposeResult:
        """Create sidebar components."""
        yield Label("User Stats", classes="section-title")
        yield Label("", id="user-class", classes="stat-label")
        yield Label("", id="sleep-status", classes="stat-label")

        yield Label("Quest", classes="section-title")
        yield Label("", id="quest-name", classes="stat-label")
        yield Label("Progress:", classes="progress-label")
        yield ProgressBar(id="quest-progress")
        yield Label("", id="total-damage", classes="stat-label")

        yield Label("Day Settings", classes="section-title")
        yield Label("", id="day-start-time", classes="stat-label")
        yield Label("", id="needs-cron", classes="stat-label")

        yield Label("Recent Activity", classes="section-title")
        yield Static("Loading activity...", id="last-log")


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
        background: $surface-darken-1;
        overflow-y: auto;
    }

    #main-content {
        width: 100%;
        height: 100%;
        background: $surface;
    }

    #header {
        dock: top;
        height: auto;
        background: $panel;
        border-bottom: solid $accent;
        padding: 1;
    }

    #user-info-container {
        width: 100%;
        height: auto;
        padding: 1;
        background: $panel-lighten-1;
        border-bottom: solid $accent;
    }

    #user-info-static {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $text;
    }

    #sleep-toggle-container {
        padding: 1;
        margin-top: 1;
        background: $panel;
        border: solid $accent;
        height: auto;
        align: center middle;
    }

    #sleep-label {
        margin-right: 2;
    }

    #content {
        padding: 1;

        & #api-status-label {
            margin-top: 1;
            padding: 1;
            background: $surface-darken-1;
            border: solid $accent;
            text-align: center;
        }
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
    """

    def __init__(self):
        super().__init__()
        self.data_manager: DataManager | None = None
        self.api_client = HabiticaClient()
        self.quest_data: Dict[str, Any] = {}
        # Flag to prevent toggle loop
        self._updating_ui = False
        # Flag to track the last known sleep state to avoid unnecessary API calls
        self._last_sleep_state = None

    async def on_mount(self) -> None:
        """Runs when the app starts: setup the data manager."""
        log.info("--- HabiticaApp: Starting DataManager setup ---")

        # Setup Dependencies
        api_client = HabiticaClient()
        static_cache_dir = HABITICA_DATA_PATH / "static_content"
        content_manager = StaticContentManager(cache_dir=static_cache_dir)
        cache_dir = HABITICA_DATA_PATH
        self.data_manager = DataManager(api_client=api_client, static_content_manager=content_manager, cache_dir=cache_dir)

        # Update status
        self._update_status("Loading Habitica data...", "loading")

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

                    # Store the initial sleep state
                    self._last_sleep_state = getattr(self.data_manager.user, "is_sleeping", False)

        except Exception as e:
            log.error(f"Data loading error: {e}")

        # Update UI with loaded data
        await self.update_ui_with_data(data_loaded, processing_successful)

        # Update final status
        if data_loaded and processing_successful:
            self._update_status("Data loaded successfully", "success")
        else:
            self._update_status("Failed to load data", "error")

            # Disable sleep toggle
            try:
                sleep_switch = self.query_one("#sleep-toggle", Switch)
                sleep_switch.disabled = True
            except Exception:
                pass

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

    def _update_status(self, message: str, status_class: str = "") -> None:
        """Updates the status label with a message and optional CSS class."""
        try:
            status_label = self.query_one("#api-status-label", Static)
            status_label.update(message)

            # Remove all status classes
            status_label.remove_class("loading")
            status_label.remove_class("success")
            status_label.remove_class("error")
            status_label.remove_class("warning")

            # Add the requested class
            if status_class:
                status_label.add_class(status_class)
        except Exception as e:
            log.error(f"Failed to update status: {e}")

    async def update_ui_with_data(self, data_loaded: bool, processing_successful: bool) -> None:
        """Update UI widgets with data from DataManager."""
        if not self.data_manager:
            log.error("DataManager is not initialized when trying to update UI.")
            return

        # Set flag to prevent event triggering during UI update
        self._updating_ui = True

        try:
            # Get widget references
            try:
                user_info_widget = self.query_one("#user-info-static", Static)
                stats_widget = self.query_one(StatsCount)
                sidebar_stats = self.query_one(SidebarStats)
                sleep_toggle = self.query_one("#sleep-toggle", Switch)
            except Exception as e:
                log.error(f"Error getting widget references: {e}")
                return

            # Update widgets if data is available
            if self.data_manager.user and data_loaded and processing_successful:
                # User info with emoji
                username = getattr(self.data_manager.user, "username", "Unknown User")

                # Get user class and sleeping status
                user_class = getattr(self.data_manager.user, "class", "")
                is_sleeping = False
                try:
                    is_sleeping = getattr(self.data_manager.user, "is_sleeping", False)
                except Exception:
                    pass

                # Update sleep toggle without triggering events - we're using the flag to prevent loops
                sleep_toggle.value = is_sleeping

                # Format user info with emojis
                class_emoji = {"warrior": "⚔️", "mage": "🧙‍♂️", "healer": "💚", "rogue": "🗡️", "": "👤"}.get(user_class.lower(), "👤")

                sleep_emoji = "💤" if is_sleeping else "👁️"

                # Quest status
                quest_status = "No active quest"
                if getattr(self.data_manager.user, "is_on_quest", False):
                    quest_type = "Boss" if getattr(self.data_manager.user, "is_on_boss_quest", False) else "Collection"
                    quest_status = f"On {quest_type} Quest"

                user_info_widget.update(f"{class_emoji} {username} {sleep_emoji} • {quest_status}")

                # Update stats widgets
                stats_widget.update_display(self.data_manager.user)
                sidebar_stats.update_sidebar_stats(self.data_manager.user, self.quest_data)

                # Update our last known sleep state
                self._last_sleep_state = is_sleeping

            else:
                # Reset widgets if no data
                user_info_widget.update("Failed to load user data")
                stats_widget.update_display(None)
                sidebar_stats.update_sidebar_stats(None)
                sleep_toggle.disabled = True
        finally:
            # Clear flag after UI update is complete
            self._updating_ui = False

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle events."""
        if event.switch.id == "sleep-toggle" and not self._updating_ui:
            # Only proceed with toggle if it's a genuine user action (not during UI update)
            # And if the new state is different from what we have cached
            if event.value != self._last_sleep_state:
                await self._toggle_sleep(event.value)
            else:
                # If the switch was somehow triggered but the state is already what we want,
                # just ignore it to prevent unnecessary API calls
                log.info(f"Ignoring sleep toggle event - sleep state already set to {event.value}")

    async def _toggle_sleep(self, sleep_value: bool) -> None:
        """Toggle user sleep state."""
        if not self.data_manager or not self.api_client:
            self._update_status("Error: API client not initialized", "error")
            return

        self._update_status("Toggling sleep state...", "loading")

        try:
            # Call API to toggle sleep
            api_success = await self.api_client.toggle_user_sleep()

            if api_success:
                self._update_status("Sleep state changed successfully", "success")

                # Update our cached sleep state immediately to prevent multiple toggles
                self._last_sleep_state = sleep_value

                # Reload user data
                data_reloaded = await self.data_manager.load_user(force_refresh=True)

                if data_reloaded:
                    processing_success = await self.data_manager.process_loaded_data()

                    if processing_success:
                        await self.update_ui_with_data(True, True)
                        self._update_status("Data refreshed after sleep toggle", "success")
                    else:
                        self._update_status("Sleep toggled but error processing data", "warning")
                else:
                    self._update_status("Sleep toggled but error reloading data", "warning")
            else:
                self._update_status("Failed to toggle sleep state", "error")
                # Reset switch to previous state without triggering events
                self._updating_ui = True
                try:
                    switch = self.query_one("#sleep-toggle", Switch)
                    switch.value = not sleep_value
                except Exception as e:
                    log.error(f"Error resetting sleep switch: {e}")
                finally:
                    self._updating_ui = False

        except Exception as e:
            self._update_status(f"Error: {e}", "error")
            # Reset switch to previous state
            self._updating_ui = True
            try:
                switch = self.query_one("#sleep-toggle", Switch)
                switch.value = not sleep_value
            except Exception:
                pass
            finally:
                self._updating_ui = False

    def compose(self) -> ComposeResult:
        """Create the UI layout with sidebar and main content."""
        with Container(id="app-container"):
            # Sidebar
            with Vertical(id="sidebar"):
                with Vertical(id="header"):
                    yield Static("Loading user...", id="user-info-static")
                    yield StatsCount()

                # Sleep toggle with label
                with Horizontal(id="sleep-toggle-container"):
                    yield Label("Sleep Mode:", id="sleep-label")
                    yield Switch(value=False, id="sleep-toggle")

                # Sidebar stats
                yield SidebarStats()

            # Main content area
            with Vertical(id="main-content"):
                with Vertical(id="content"):
                    # Placeholder for main content (tasks, etc.)
                    yield Static("Main content area - Tasks will display here")

                    # API status indicator
                    yield Static("Ready", id="api-status-label")


if __name__ == "__main__":
    app = HabiticaApp()
    app.run()
