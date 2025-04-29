# SECTION: LEGACY WIDGET CLASS
# KLASS: StatsCount (Legacy Widget)
class StatsCount(Vertical):  # Renamed from StarCount? Keep consistent.

    DEFAULT_CSS = """
    StatsCount { /* Renamed selector */
        /* Layout */
        dock: top; /* Example docking */
        height: auto; /* Adjust height as needed */
        layout: horizontal; /* Arrange stat groups horizontally */
        padding: 1 1;
        border: round $accent; /* Example border */
        background: $panel; /* Example background */
        align: center middle; /* Vertically center content */
        width: 100%; /* Take full width */

        /* Child Alignment */
        &> Vertical { /* Target inner Vertical groups for each stat */
             width: auto;
             height: auto;
             margin: 0 1; /* Spacing between stats */
             align: center top; /* Label above digits */
        }
        Label { width: auto; text-style: bold; color: $text; margin-bottom: 1; }
        Digits { width: auto; } /* Let digits size naturally */

        /* Stat-specific Colors (Using Textual standard variables) */
        #lvl Digits { color: $warning; } /* Gold/Yellow */
        #mp Digits { color: $primary; } /* Blue */
        #hp Digits { color: $error; }   /* Red */
        #gp Digits { color: $warning-darken-2; } /* Darker Gold */
        #exp Digits { color: $success; } /* Green */
    }
    """

    # Reactive variables (Potentially reusable)
    hp: reactive[float] = reactive(0.0)
    mp: reactive[float] = reactive(0.0)
    gp: reactive[float] = reactive(0.0)
    exp: reactive[float] = reactive(0.0)
    lvl: reactive[int] = reactive(0)
    max_exp: reactive[int] = reactive(0)
    max_hp: reactive[int] = reactive(0)
    max_mp: reactive[int] = reactive(0)

    # FUNC: update_display (NEW - Required for new architecture)
    def update_display(self, stats_data: dict[str, Any] | None) -> None:
        """Updates the widget's display based on data from the DataStore.

        Args:
            stats_data: The stats dictionary (e.g., from DataStore.get_user_stats()).
        """
        if not stats_data:
            self.log.warning("StatsCount received no data to display.")
            # Reset to defaults or show placeholders
            self.hp = 0.0
            self.mp = 0.0
            self.gp = 0.0
            self.exp = 0.0
            self.lvl = 0
            self.max_exp = 0
            self.max_hp = 50
            self.max_mp = 30
            return

        # Update reactive variables from the provided dictionary
        self.hp = stats_data.get("hp", 0.0)
        self.mp = stats_data.get("mp", 0.0)
        self.gp = stats_data.get("gp", 0.0)
        self.exp = stats_data.get("exp", 0.0)
        self.lvl = stats_data.get("level", 0)
        self.max_exp = stats_data.get("toNextLevel", 0)
        self.max_hp = stats_data.get("maxHealth", 50)
        self.max_mp = stats_data.get("maxMP", 0)  # Get actual calculated max

        # Update Tooltips directly
        try:
            self.query_one("#lvl Digits", Digits).tooltip = f"Level: {self.lvl}"
            self.query_one("#mp Digits", Digits).tooltip = f"Mana: {self.mp:.1f} / {self.max_mp}"
            self.query_one("#hp Digits", Digits).tooltip = f"Health: {self.hp:.1f} / {self.max_hp}"
            self.query_one("#exp Digits", Digits).tooltip = f"Experience: {self.exp:.0f} / {self.max_exp}"
            self.query_one("#gp Digits", Digits).tooltip = f"Gold: {self.gp:.2f}"
        except Exception as e:
            self.log.error(f"Error updating StatsCount tooltips: {e}")

    # Watch methods to update Digits display
    def watch_lvl(self, value: int) -> None:
        try:
            self.query_one("#lvl Digits", Digits).update(f"{value} Lvl")  # Add unit
        except Exception:
            pass

    def watch_mp(self, value: float) -> None:
        try:
            self.query_one("#mp Digits", Digits).update(f"{value:.1f}")
        except Exception:
            pass

    def watch_hp(self, value: float) -> None:
        try:
            self.query_one("#hp Digits", Digits).update(f"{value:.1f}")
        except Exception:
            pass

    def watch_exp(self, value: float) -> None:
        try:
            self.query_one("#exp Digits", Digits).update(f"{value:.0f} XP")  # Add unit
        except Exception:
            pass

    def watch_gp(self, value: float) -> None:
        try:
            self.query_one("#gp Digits", Digits).update(f"{value:.2f} GP")  # Add unit
        except Exception:
            pass

    # FUNC: compose (Layout structure looks reusable)
    def compose(self) -> ComposeResult:
        """Create UI components dynamically."""
        # Arrange stats horizontally using Vertical containers for Label+Digits
        # Horizontal container is implicitly created by the layout: horizontal in CSS
        with Vertical(id="lvl"):
            yield Label("Level")
            yield Digits(f"{self.lvl} Lvl")  # Display initial value

        with Vertical(id="mp"):
            yield Label("Mana")
            yield Digits(f"{self.mp:.1f}")

        with Vertical(id="hp"):
            yield Label("Health")
            yield Digits(f"{self.hp:.1f}")

        with Vertical(id="gp"):
            yield Label("Gold")
            yield Digits(f"{self.gp:.2f} GP")

        with Vertical(id="exp"):
            yield Label("Experience")
            yield Digits(f"{self.exp:.0f} XP")
