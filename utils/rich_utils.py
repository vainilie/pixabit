# rich_utils.py - Module


from rich import box
from rich import print
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.prompt import Confirm, Prompt
from rich.prompt import IntPrompt
from rich.table import Table
from rich.theme import Theme

# Read the theme from "styles" file and initialize the console with the theme
theme = Theme.read("utils/styles")
console = Console(theme=theme)
