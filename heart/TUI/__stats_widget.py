"""Generate stats from the Habitica API."""

from heart.basis.__get_data import get_user_stats  # Import API logic
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label


class StatsCount(Vertical):
    """Widget to display Habitica stats with custom colors."""

    DEFAULT_CSS = """
    StarCount {
        dock: none;
        height: 6;
        layout: horizontal;
        padding: 0 1;
        border-bottom: hkey $background;
        border-top: hkey $background;
        background: $boost;
        Label { text-style: bold; color: $foreground; }
        LoadingIndicator { background: transparent !important; }
        Digits { width: auto; margin-right: 1; margin-left: 1; }
        Label { width: auto; margin-right: 1; margin-left: 1; }
        align: center top;
        &>Horizontal { max-width: 100;} 
    }
    /* Define custom colors for each stat */
    #lvl Digits { color: $primary-lighten-3; }  /* Gold */
    #mp Digits { color: $primary; }   /* Deep Sky Blue */
    #hp Digits { color: $error; }   /* Orange Red */
    #gp Digits { color: $warning; }   /* Goldenrod */
    #exp Digits { color: $success; } /* Lime Green */
    """

    # & Define stats with default values
    hp = reactive(0, recompose=True)
    mp = reactive(0, recompose=True)
    gp = reactive(0, recompose=True)
    exp = reactive(0, recompose=True)
    lvl = reactive(0, recompose=True)
    max_exp = reactive(0, recompose=True)
    max_hp = reactive(0, recompose=True)
    max_mp = reactive(0, recompose=True)

    @work
    async def fetch_stats(self):
        """Fetch stats from the Habitica API."""
        try:
            data = await get_user_stats()
            print("Fetched stats:", data)  # Debug: Print the fetched stats

            self.hp = data["hp"]
            self.mp = data["mp"]
            self.gp = data["gp"]
            self.exp = data["exp"]
            self.lvl = data["lvl"]
            self.max_exp = data["toNextLevel"]
            self.max_hp = data["maxHealth"]
            self.max_mp = data["maxMP"]

        except Exception as e:
            self.notify(
                f"Error fetching stats: {str(e)}", title="Error", severity="error"
            )

    def compose(self) -> ComposeResult:
        """Create UI components dynamically."""
        # & Set up the layout display
        with Horizontal():
            with Vertical(id="lvl"):
                lvl = round(self.lvl)
                yield Label("Level")
                yield Digits(f"{lvl}lvl").with_tooltip(f"Level: {self.lvl}")

            with Vertical(id="mp"):
                mp = round(self.mp)
                yield Label("Mana")
                yield Digits(f"{mp}mp").with_tooltip(f"Mana: {self.mp}/{self.max_mp}")

            with Vertical(id="hp"):
                hp = round(self.hp)  # Ensures consistency with other stats
                yield Label("Health")
                yield Digits(f"{hp}hp").with_tooltip(f"Health: {self.hp}/{self.max_hp}")

            with Vertical(id="gp"):
                gp = round(self.gp)  # Ensures consistent formatting
                yield Label("Gold")
                yield Digits(f"{gp}gp").with_tooltip(f"Gold: {self.gp}")

            with Vertical(id="exp"):
                exp = round(self.exp)  # Ensures consistent formatting
                yield Label("Experience")
                yield Digits(f"{exp}XP").with_tooltip(
                    f"Experience: {self.exp}/{self.max_exp}"
                )

    def on_mount(self) -> None:
        """Fetch stats on mount."""
        self.fetch_stats()

    def on_click(self) -> None:
        """Refresh stats on click."""
        self.fetch_stats()
