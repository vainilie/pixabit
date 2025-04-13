import io
import os

from art import text2art
from rich import rule  # Added Rule
from rich import box, print
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn,
                           track)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# >> All the rich and display items
# Define the path to your theme file
theme_file_path = "pixabit/utils/styles"

# Check if the theme file exists
if not os.path.exists(theme_file_path):
    print(f"⛔ Error: Theme file not found at {theme_file_path}")
    # Optionally create a default theme or exit
    custom_theme = Theme({}, inherit=False)  # Or Theme({}) for an empty one
else:
    try:
        # Open the file and load the theme
        with open(theme_file_path, "rt", encoding="utf-8") as theme_file:
            custom_theme = Theme.from_file(theme_file, source=theme_file_path)
            console = Console(theme=custom_theme)
            console.log(
                f"✅ Successfully loaded theme from {theme_file_path}",
                style="success",
            )
    except Exception as e:
        print(f"⛔ Error loading theme from {theme_file_path}: {e}")
        # Fallback to default theme
        custom_theme = Theme({}, inherit=False)


# Create a Console instance using the loaded theme
console = Console(theme=custom_theme)

# # Now you can use the styles defined in your theme file
# console.print("This is informational text.", style="info")
# console.print("This is a warning message.", style="warning")
# console.print("[danger]This is a danger alert![/danger]")  # Using style tags
# console.print("Operation successful.", style="success")
# console.print("This is regular text.", style="regular")
# console.print("This text is [highlight]highlighted[/highlight].")
# console.print("This is subtle text.", style="subtle")
# console.print(
#     "This style is not in the theme.", style="nonexistent_style"
# )  # Will use default
