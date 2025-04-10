#!/usr/bin/env python3

"""
mainmenu.py

Provides the user interface for selecting actions within the Habitica CLI application.
Includes a main menu and categorized submenus for easier navigation.
"""

from 
from utils.rich_utils import Confirm, IntPrompt, Panel, Columns, console, print
from core.auth_file import check_auth_file
from get import bkup_challenges, get_tags, get_tasks, get_stats, get_userdata
from interface import rich_stats, rich_tags
from actions import (
    unused_tags,
    filter_task,
    sleeping,
    category_tags,
    setattr,
    challenges,
    sort
)
from art import text2art
from rich import box, print
from rich.layout import Layout
from rich.text import Text


# Initialize data
def initialize_data():
    """
    Initializes or refreshes data from Habitica.
    """
    console.print("[bold green]Refreshing data...[/bold green]")
    global tags, all_tasks, stats, unused
    tags = get_tags.get_tags()
    all_tasks = get_tasks.process_tasks(tags)
    stats = get_stats.get_user_stats(all_tasks["cats"])
    unused = unused_tags.get_unused_tags(tags, all_tasks["cats"]["tags"])
    console.print("[bold green]Data refreshed successfully![/bold green]")


def display_menu(title, options):
    """
    Displays a menu with a given title and options.

    Args:
        title (str): Title of the menu.
        options (list): List of menu options.

    Returns:
        int: The user's selected option number.
    """

    # Render menu

    menu_renderable = [
        f"[b]{num}.[/] [i]{option}" for num, option in enumerate(options, start=1)
    ]
    menu_renderable.insert(0, "[b]0.[/] [i]Return to previous menu")

    layout = Layout()
    layout.split_row(Layout(name="left", ratio=10), Layout(name="right", ratio=5))

    layout["left"].update(Text(text2art("Pixabit", font="rnd-small"), style="#cba6f7"))
    layout["right"].update(
        Panel(
            Columns(menu_renderable),
            title=f"[#ebcb8b][b]{title}[/b]",
            border_style="#ebcb8b",
            box=box.HEAVY,
        )
    )
    console.print(Panel(layout, height=10, border_style="#ebcb8b", box=box.HEAVY))
    selected = IntPrompt.ask("Enter the number of the action you want to perform")
    return selected


def display_main_menu():
    """
    Displays the main menu and navigates to selected submenus.

    Returns:
        None
    """
    categories = {
        "Challenges": ["Backup Challenges", "List Challenges"],
        "Tasks": ["Broken tasks", "Sort alphabetically"],
        "Tags": ["Print tags", "Unused tags", "Fix tags"],
        "Stats": ["Print stats", "Save all"],
        "Others": ["Toogle Sleeping", "Refresh Data"],
    }

    while True:
        main_menu_options = list(categories.keys()) + ["Exit"]
        selected_category = display_menu("Main Menu", main_menu_options)

        if selected_category == 0:  # Return to previous menu
            console.print(
                "[bold yellow]You are already in the main menu![/bold yellow]"
            )
            continue

        if selected_category == len(main_menu_options):  # Exit option
            console.print("\n[bold red]Exiting Pixabit. Goodbye![/bold red]")
            exit()

        if 1 <= selected_category <= len(main_menu_options) - 1:
            selected_category_name = main_menu_options[selected_category - 1]
            submenu_options = categories[selected_category_name]
            while True:
                selected_action = display_menu(
                    f"{selected_category_name} Menu", submenu_options
                )
                if selected_action == 0:  # Return to main menu
                    break
                elif selected_action <= len(submenu_options):
                    action_name = submenu_options[selected_action - 1]
                    if action_name == "Refresh Data":
                        initialize_data()
                    else:
                        select_option(action_name)
                else:
                    console.print(
                        f"[bold red]Invalid selection. Please choose a number between 0 and {len(submenu_options)}.[/bold red]"
                    )


def select_option(selected_action):
    """
    Executes the action based on the user's selection.

    Args:
        selected_action (str): The action selected by the user.
    """

    if selected_action == "Backup Challenges":
        if Confirm.ask("Backup [i]challenges[/i]?", default=False):
            bkup_challenges.join_challenges_and_tasks()
            print("Challenges Saved")

    elif selected_action == "List Challenges":
        if Confirm.ask("List [i]challenges[/i]?", default=False):
            challenges.list_challenges(all_tasks)
            print("Challenges listed")

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
        if Confirm.ask("Fix attribute [i]tags[/i]?", default=False):
            setattr.set_attr(all_tasks["data"])

    elif selected_action == "Print stats":
        if Confirm.ask("Print [i]stats[/i]?", default=False):
            rich_stats.print_stats(stats)

    elif selected_action == "Print tags":
        if Confirm.ask("Print [i]tags[/i]?", default=False):
            rich_tags.print_tags(tags)

    elif selected_action == "Save all":
        if Confirm.ask("Save all [i]user data[/i]?", default=False):
            get_userdata.save_all_user_data()

    elif selected_action == "Toogle Sleeping":
        new_sleeping_status = "awake" if stats["sleeping"] else "sleeping"
        sleeping.toggle_sleeping_status(stats["sleeping"], new_sleeping_status)

    elif selected_action == "Unused tags":
        if Confirm.ask("Print [i]unused tags[/i]?", default=False):
            rich_tags.print_unused(unused)
        if Confirm.ask("Delete [i]unused tags[/i]?", default=False):
            unused_tags.delete_unused_tags(unused)
            
            
    elif selected_action == "Sort alphabetically":
        if Confirm.ask("Sort [i]all tasks alphabetically[/i]?", default=False):
            sort.sort_alpha(all_tasks["data"])