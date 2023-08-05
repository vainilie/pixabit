from utils.rich_utils import Table, Console, Panel, box, console, Markdown, Confirm, IntPrompt
from core import habitica_api


def find(data, look):
    """Extract text from user dict."""
    title = data[look]["text"]
    types = data[look]["_type"]
    content = Markdown(f"{title} - {types}")
    return content


# def find_broken(data, look):

#     user_renderables = [Panel(find(data, loo), expand=False) for loo in look]
#     console.print(Columns(user_renderables, width=30, expand=True,align="center"))


def delete_broken(data, look):
    broken_challenges = {}
    options = {}
    for num, loo in enumerate(look):
        broken_challenges.update({data[loo]["challenge_id"]: data[loo]["challenge"]})
    broken_challenges = dict(sorted(broken_challenges.items()))
    table = Table.grid()
    for num, challenge in enumerate(broken_challenges, start=1):
        options.update({num: {"id": challenge, "name": broken_challenges[challenge]}})
    for opt in options:
        table.add_row(f"[b]{str(opt)}.", options[opt]["name"], options[opt]["id"])

    console.print(table)
    while True:
        number = IntPrompt.ask("Enter the number of the challenge you want to unlink")
        if number > 0 and number <= len(options):
            break
        print(":pile_of_poo: [prompt.invalid]Number must be between 1 and 10")

    if Confirm.ask(
        f"Unlink and delete tasks of {options.get(number).get('name')}?", default=False
    ):
        habitica_api.post(
            "tasks/unlink-all/" + options.get(number).get("id") + "?keep=remove-all"
        )
        list_broken(data, look)
    else:
        exit()


def list_broken(data, look):
    table = Table(
        title="Broken Tasks", safe_box=True, row_styles=("dim",), box=box.MINIMAL
    )
    table.add_column("#")
    table.add_column("Type")
    table.add_column("Text")
    table.add_column("Challenge")
    table.add_column("Tags", width=15, overflow="fold")

    for num, loo in enumerate(look):
        sorted_look = sorted(look, key=lambda x: data[x]["challenge"])

    for num, loo in enumerate(sorted_look):
        task = data[loo]
        tags_names = task.get("tags_names", [])

        # Convert tags_names array to a comma-separated string if it is an array
        if isinstance(tags_names, list):
            tags_names = ", ".join(tags_names)

        table.add_row(
            str(num),
            task["_type"],
            Markdown(task["text"]),
            task["challenge"],
            tags_names,
        )
    console.print(table)


#     user_renderables = [Panel(find(data, loo), expand=False) for loo in look]
#     console.print(Columns(user_renderables, width=30, expand=True,align="center"))


# curl -X "POST"
