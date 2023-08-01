from rich import print
from rich.columns import Columns
from rich.table import Table
from rich.panel import Panel


def show_all_tags(tags, key):
    """
    Display the specified key of tags in a rich table.

    Args:
        tags (dict): A dictionary containing tag data categorized by type.
        key (str): The key to display from the tags.

    Example:
        show_tags({"challengeTags": [{"id": "123", "name": "Tag1"}, ...]}, "name")
    """
    for category, tag_list in tags.items():
        tag_ids = [tag[key] for tag in tag_list]
        tags_display = Table.grid()
        columns = Columns(
            (
                f"[b]{num}.[/] {tag}" for num, tag in enumerate(tag_ids)
            ),  # Corrected variable name here
            padding=(0, 2),
            equal=True,
            column_first=True,
            expand=False,
        )
        tags_display.add_row(columns)
        display = Panel(tags_display, title=f"[habitica][b i]{category}")
        print(display)


def list_unused_tags(unused_tags):
    tags_display = Table.grid()
    columns = Columns(
            (
                f"[b]{num}.[/] {tag['name']}" for num, tag in enumerate(unused_tags)
            ),  # Corrected variable name here
            padding=(0, 1)            
        )
    tags_display.add_row(columns)
    display = Panel(tags_display, title=f"[habitica][b i]Unused tags", expand=False,)
    print(display)