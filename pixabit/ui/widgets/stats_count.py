# pixabit/ui/widgets/stats_count.py

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label

from pixabit.helpers._logger import log
from pixabit.models.user import User


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
