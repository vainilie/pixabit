from typing import Callable

from heart.__common.__save_file import save_file
from heart.basis import __get_data as get
from processors import backup_challenges
from TUI.rich_utils import Columns, Confirm, IntPrompt, Panel, console


def backup_challenges():
    if Confirm.ask("Backup [i]challenges[/i]?", default=False):
        backup_challenges.join_challenges_and_tasks()
        print("Challenges Saved")


def save_user_data():
    if Confirm.ask("Save all [i]user data[/i]?", default=False):
        save_file(get.userdata(), "userdata", "data")
        print("User Data Saved")


def list_challenges():
    if Confirm.ask("List [i]challenges[/i]?", default=False):
        challenges.list_challenges(all_tasks)
        print("Challenges listed")


def check_broken_tasks():
    if Confirm.ask("Check [i]broken tasks[/i]?", default=False):
        if stats["broken"] > 0:
            filter_task.list_broken(all_tasks["data"], all_tasks["cats"]["broken"])
            if Confirm.ask("Unlink [i]broken tasks[/i]?", default=False):
                filter_task.delete_broken(
                    all_tasks["data"], all_tasks["cats"]["broken"]
                )
        else:
            print("No broken tasks")


def fix_tags():
    if Confirm.ask("Fix [i]tags[/i]?", default=False):
        category_tags.ischallenge_or_personal_tags(all_tasks["data"])
    if Confirm.ask("Fix poisoned [i]tags[/i]?", default=False):
        category_tags.ispsn_ornot(all_tasks["data"])
    if Confirm.ask("Fix attribute [i]tags[/i]?", default=False):
        setattr.set_attr(all_tasks["data"])


def print_stats():
    if Confirm.ask("Print [i]stats[/i]?", default=False):
        rich_stats.print_stats(stats)


def print_tags():
    if Confirm.ask("Print [i]tags[/i]?", default=False):
        rich_tags.print_tags(tags)


def toggle_sleeping():
    new_sleeping_status = "awake" if stats["sleeping"] else "sleeping"
    sleeping.toggle_sleeping_status(stats["sleeping"], new_sleeping_status)


def handle_unused_tags():
    if Confirm.ask("Print [i]unused tags[/i]?", default=False):
        rich_tags.print_unused(unused)
    if Confirm.ask("Delete [i]unused tags[/i]?", default=False):
        unused_tags.delete_unused_tags(unused)


def sort_alphabetically():
    if Confirm.ask("Sort [i]all tasks alphabetically[/i]?", default=False):
        sort.sort_alpha(all_tasks["data"])


# Dispatch dictionary mapping actions to functions
ACTION_MAP: dict[str, Callable[[], None]] = {
    "Backup Challenges": backup_challenges,
    "List Challenges": list_challenges,
    "Broken tasks": check_broken_tasks,
    "Fix tags": fix_tags,
    "Print stats": print_stats,
    "Print tags": print_tags,
    "Save user data": save_user_data,
    "Toogle Sleeping": toggle_sleeping,
    "Unused tags": handle_unused_tags,
    "Sort alphabetically": sort_alphabetically,
}


def select_option(selected_action: str):
    """
    Executes the action based on the user's selection.

    Args:
        selected_action (str): The action selected by the user.
    """
    action = ACTION_MAP.get(selected_action)
    if action:
        action()
    else:
        print(f"[b]Unknown action: {selected_action}[/b]")
