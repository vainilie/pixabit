from utils.rich_utils import Confirm, IntPrompt, Panel, Columns, console, print
from core.auth_file import check_auth_file
from get import bkup_challenges, get_tags, get_tasks, get_stats, get_userdata
from interface import rich_stats, rich_tags, mainmenu
from actions import unused_tags, filter_task, sleeping, category_tags, setattr
from art import text2art
from rich import box, text

from rich import print
from rich.layout import Layout
from rich.text import Text

# Check authentication file
check_auth_file()

tags = get_tags.get_tags()
all_tasks = get_tasks.process_tasks(tags)
stats = get_stats.get_user_stats(all_tasks["cats"])
unused = unused_tags.get_unused_tags(tags, all_tasks["cats"]["tags"])


def display_main_menu():
    while True:
        actions = [
            "Backup Challenges",
            "Broken tasks",
            "Fix tags",
            "Print stats",
            "Print tags",
            "Save all",
            "Sleeping",
            "Unused tags",
        ]

        # Render actions menu
        actions_renderable = [
            f"[b]{num}.[/] [i]{action}" for num, action in enumerate(actions, start=1)
        ]

        layout = Layout()

        layout.split_row(
            Layout(
                name="left",
                ratio=10,
            ),
            Layout(
                name="right",
                ratio=5,
            ),
        )

        layout["right"].update(
            Panel(
                Columns(actions_renderable),
                title="[#ebcb8b][b]Available Actions",
                border_style="#ebcb8b",
                box=box.HEAVY,
            )
        )
        layout["left"].update(
            Text(text2art("Pixabit", font="rnd-small"), style="#cba6f7")
        )

        console.print(layout, height=10)

        selected_action_number = IntPrompt.ask(
            "Enter the number of the action you want to perform"
        )
        if 0 == selected_action_number:
            exit()
        if 0 < selected_action_number <= len(actions):
            selected_action = actions[selected_action_number - 1]
            return selected_action

        print(
            ":pile_of_poo: [prompt.invalid]Number must be between 1 and",
            len(actions),
        )


def select_option(selected_action):
    if selected_action == "Backup Challenges":
        if Confirm.ask("Backup [i]challenges[/i]?", default=False):
            bkup_challenges.join_challenges_and_tasks()
            print("Challenges Saved")

    elif selected_action == "Broken tasks":
        if Confirm.ask("Check [i]broken tasks[/i]?", default=False):
            if stats["broken"] > 0:
                filter_task.list_broken(all_tasks["data"], all_tasks["cats"]["broken"])
                if Confirm.ask("Unlink [i]broken tasks[/i]?", default=False):
                    filter_task.delete_broken(
                        all_tasks["data"], all_tasks["cats"]["broken"]
                    )
            else:
                print("No broken tasks")

    elif selected_action == "Fix tags":
        if Confirm.ask("Fix [i]tags[/i]?", default=False):
            category_tags.ischallenge_or_personal_tags(all_tasks["data"])
        if Confirm.ask("Fix poisoned [i]tags[/i]?", default=False):
            category_tags.ispsn_ornot(all_tasks["data"])

    elif selected_action == "Print stats":
        if Confirm.ask("Print [i]stats[/i]?", default=False):
            rich_stats.print_stats(stats)
            setattr.set_attr(all_tasks["data"])

    elif selected_action == "Print tags":
        if Confirm.ask("Print [i]tags[/i]?", default=False):
            rich_tags.print_tags(tags)

    elif selected_action == "Save all":
        if Confirm.ask("Save all [i]user data[/i]?", default=False):
            get_userdata.save_all_user_data()

    elif selected_action == "Sleeping":
        new_sleeping_status = "awake" if stats["sleeping"] else "sleeping"
        sleeping.toggle_sleeping_status(stats["sleeping"], new_sleeping_status)

    elif selected_action == "Unused tags":
        if Confirm.ask("Print [i]unused tags[/i]?", default=False):
            rich_tags.print_unused(unused)
        if Confirm.ask("Delete [i]unused tags[/i]?", default=False):
            unused_tags.delete_unused_tags(unused)
