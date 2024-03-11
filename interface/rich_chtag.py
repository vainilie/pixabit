from utils.rich_utils import (
    Table,
    Console,
    Panel,
    box,
    console,
    Columns,
    Confirm,
    Prompt,
    IntPrompt,
)
from actions import category_tags
from interface.mainmenu import all_tasks


def print_tags(tags):
    alltags = []
    
    num=1
    for category in tags:
        for tag in tags[category]:
            alltags.append(tag)

        tag_renderables = [
            f"[b]{num}.[/] [i]{tag['name'][:24]}" 
            for num, tag in enumerate(tags[category], start=num)
        ]
        tag_render = Panel(
            Columns(tag_renderables, column_first=True, padding=(0, 4)            ,
            title=f"[gold][i]{category}",
            expand=False)
        )
        console.print(tag_render,overflow=Ellipsis)
        num += len(tag_renderables)

   # console.print(tag_render)

    while True:
        if Confirm.ask("Replace any tag?", default=False):
            while True:
                del1_n_ = []
                del1_n = Prompt.ask(
                    "Enter the number of the tag you want to replace/base"
                )
                print(del1_n)
                print(del1_n_)
                
                if " " in del1_n:
                    del1_n_ = del1_n.split(" ")
                else:
                    del1_n_.append(del1_n)
                print(del1_n_)


                if len(del1_n_) >0:
                    break
                    
                print(
                        f":pile_of_poo: [prompt.invalid]Number must be between 1 and {len(alltags)}"
                )
            while True:
                add1_n = IntPrompt.ask("Enter the number of the tag you want to add")
                if add1_n > 0 and add1_n <= len(alltags):
                    break
                print(
                    f":pile_of_poo: [prompt.invalid]Number must be between 1 and {len(alltags)}"
                )


            add1 = alltags[add1_n - 1]["id"]
            for d in del1_n_:
                del1_n = int(d)
                del1 = alltags[del1_n - 1]["id"]

                if Confirm.ask("Unlink the first tag?", default=False):
                    category_tags.tags_replace(del1, add1, all_tasks["data"], "replace")
                else:
                    category_tags.tags_replace(del1, add1, all_tasks["data"])
