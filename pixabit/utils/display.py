import io

from art import text2art  # If still used
from rich import box, print
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import track
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

theme = Theme.read("pixabit/utils/styles")
console = Console(
    theme=theme,
    file=io.StringIO(),
    force_terminal=True,
    # width=80,
    # color_system="truecolor",
    legacy_windows=False,
    _environ={},
)


def print(text, **kwargs):
    console.print(text, **kwargs)
