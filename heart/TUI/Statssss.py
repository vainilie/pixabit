
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label
import asyncio
from importlib.metadata import version
from heart.basis.auth_keys import get_user_id, get_api_token

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

BASEURL = "https://habitica.com/api/v3/"
USER_ID = get_user_id()
API_TOKEN = get_api_token()

HEADERS = {
    "x-api-user": USER_ID,
    "x-api-key": API_TOKEN,
    "Content-Type": "application/json",
}
class MyCustomAuth(httpx.Auth):

    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        # Send the request, with a custom X-Authentication header.
        request.headers['X-Authentication'] = self.token
        yield request

class StarCount(Vertical):
    """Widget to get and display stats with custom colors."""

    DEFAULT_CSS = """
    StarCount {
        height: 6;
        layout: horizontal;
        padding: 0 1;
    }
    
    #lvl Label, #lvl Digits {
        color: #FFD700;  /* Gold for Level */
    }
    #mp Label, #mp Digits {
        color: #00BFFF;  /* Deep Sky Blue for Mana */
    }
    #hp Label, #hp Digits {
        color: #FF4500;  /* Orange Red for Health */
    }
    #exp Label, #exp Digits {
        color: #32CD32;  /* Lime Green for Experience */
    }
    #gp Label, #gp Digits {
        color: #DAA520;  /* Goldenrod for Gold */}
        dock: top;
        height: 6;
        border-bottom: hkey $background;
        border-top: hkey $background;
        layout: horizontal;
        background: $boost;
        padding: 0 1;
        Label { text-style: bold; color: $foreground; }
        LoadingIndicator { background: transparent !important; }
        Digits { width: auto; margin-right: 1; }
        Label { margin-right: 1; }
        align: center top;
        &>Horizontal { max-width: 100;} 
    }
    """

    lvl = reactive(0, recompose=True)
    mp = reactive(0, recompose=True)
    hp = reactive(0, recompose=True)
    gp = reactive(0, recompose=True)
    exp = reactive(0, recompose=True)

    @work
    async def get_stars(self):
        """Worker to get stats from Habitica API."""
        try:
            async with httpx.AsyncClient() as client:
                stats_json = (await client.get(BASEURL + "user?userFields=stats", headers=HEADERS)).json()
            self.lvl = stats_json["data"]["stats"]["lvl"]
            self.mp = stats_json["data"]["stats"]["mp"]
            self.hp = stats_json["data"]["stats"]["hp"]
            self.exp = stats_json["data"]["stats"]["exp"]
            self.gp = stats_json["data"]["stats"]["gp"]
        except Exception:
            self.notify("Unable to fetch stats. Please try again.", title="Error", severity="error")

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="lvl"):
                lvl = 
                yield Label("Level ★")
                yield Digits(f"{self.lvl}").with_tooltip(f"Level: {self.lvl}")

            with Vertical(id="mp"):
                yield Label("Mana")
                yield Digits(f"{self.mp}").with_tooltip(f"Mana: {self.mp}")

            with Vertical(id="hp"):
                yield Label("Health")
                yield Digits(f"{self.hp}").with_tooltip(f"Health: {self.hp}")

            with Vertical(id="exp"):
                yield Label("Experience")
                yield Digits(f"{self.exp}").with_tooltip(f"Experience: {self.exp}")

            with Vertical(id="gp"):
                yield Label("Gold")
                yield Digits(f"{round(self.gp)}").with_tooltip(f"Gold: {self.gp}")

    def on_mount(self) -> None:
        """Fetch stats on mount."""
        self.get_stars()

    def on_click(self) -> None:
        """Refresh stats on click."""
        self.get_stars()