import os
import sys

from rich import print
from rich.columns import Columns
from rich.table import Table

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel

from rich.theme import Theme

theme = Theme.read("styles")
console = Console(theme=theme)


def Show(Tags, key):
    """Get key of the tags

    Args:
        Tags (dict): dict of Tags
        key (key): Key to get
    """
    for Cat in Tags:
        ids = []

        for idx, x in enumerate(Tags[Cat]):
            ids.append(x[key])
        TagsDisplay = Table.grid()
        columns = Columns(
            (f"[b]{num}.[/] {tag}" for num, tag in enumerate(ids)),
            padding=(0, 2),
            equal=True,
            column_first=True,
            expand=True,
            
        )
        TagsDisplay.add_row(columns)
        Display = Panel(TagsDisplay, title=f"[habitica][b i]{Cat}")
        print(Display)


def IDs(Tags):
    """Get list of id of tags

    Args:
        Tags (dict): dict tags
    """
    ids = []
    for Cat in Tags:
        for idx, x in enumerate(Tags[Cat]):
            ids.append(x["id"])
    return sorted(set(ids))
