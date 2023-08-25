from utils.rich_utils import Table, Console, Panel, box, console, Columns
from interface import rich_chtag

def print_tags(tags):
    for category in tags:
        tag_renderables = [
            f"[b]{num}.[/] [i]{tag['name']}"
            for num, tag in enumerate(tags[category], start=1)
        ]
        tag_render = Panel(
            Columns(tag_renderables, column_first=True, padding=(0, 4)),
            expand=False,
            width=50,
            title=f"[gold][i]{category}",
        )
        console.print(tag_render)
    rich_chtag.print_tags(tags)



def print_unused(tags):
    tag_renderables = [
        f"[b]{num}.[/] [i]{tag['name']}[/]\n{tag['category']}"
        for num, tag in enumerate(tags, start=1)
    ]
    tag_render = Panel(
        Columns(tag_renderables, column_first=True, padding=(0, 4)),
        expand=True,
        title="[gold][i]Unused Tags",
    )
    console.print(tag_render)
