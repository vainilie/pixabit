import Requests
from rich.prompt import Confirm
from rich import print
from rich.console import Console
from rich.theme import Theme

theme = Theme.read("styles")
console = Console(theme=theme)

#
# ─── % TOGGLE SLEEPING ──────────────────────────────────────────────────────────
#


def Sleeping(on, off):
    prompt = f"You are {on}. Toggle {off} status?"
    if Confirm.ask(prompt, default=False):
        Requests.PostAPI("user/sleep")
        print(f"[b]You're now {off} :cherry_blossom:")
    else:
        print(f"[b]OK, you are still {on} :cherry_blossom:")
