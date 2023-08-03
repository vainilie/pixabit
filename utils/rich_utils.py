# rich_utils.py
from rich.prompt import Confirm, Prompt
from rich.theme import Theme
from rich.console import Console
from rich import print

# Read the theme from "styles" file and initialize the console with the theme
theme = Theme.read("utils/styles")
console = Console(theme=theme)
