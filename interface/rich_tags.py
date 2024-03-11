from utils.rich_utils import Table, Console, Panel, box, console, Columns
from interface import rich_chtag

def print_tags(tags):
    # num=1
    # for category in tags:
    #     tag_renderables = [
    #         f"[b]{num}.[/] [i]{tag['name'][:24]}" 
    #         for num, tag in enumerate(tags[category], start=num)
    #     ]
    #     tag_render = Panel(
    #         Columns(tag_renderables, column_first=True, padding=(0, 4)            ,
    #         title=f"[gold][i]{category}",
    #         expand=False)
    #     )
    #     console.print(tag_render,overflow=Ellipsis)
    #     num += len(tag_renderables)

    rich_chtag.print_tags(tags)



def print_unused(tags):
    tag_renderables = [
        f"[b]{num}.[/] [i]{tag['name']}[/]\n{tag['category']}"
        for num, tag in enumerate(tags, start=1)
    ]
    tag_render = Panel(
        Columns(tag_renderables, column_first=True, padding=(0, 4),        expand=True,
),
        title="[gold][i]Unused Tags",
    )
    console.print(tag_render)
