#!/usr/bin/env python3

"""
mainmenu.py

Provides the user interface for selecting actions within the Habitica CLI application.
Includes a main menu and categorized submenus for easier navigation.
"""
from art import text2art
from basis import api_check
from heart.basis import __get_data as get
from processors import (backup_challenges, fix_attributes, fix_unused_tags,
                        process_stats, process_tags, process_task)
from rich import box, print
from rich.layout import Layout
from rich.text import Text
from TUI.main_functions import select_option
from TUI.rich_utils import Columns, Confirm, IntPrompt, Panel, console, print


# Initialize data
def initialize_data():
    """
    Initializes or refreshes data from Habitica.
    """

    console.print("[bold green]Refreshing data...[/bold green]")
    tags = process_tags.process_tags()
    tasks = process_task.process_tasks()
    stats = process_stats.process_tasks()
    used_tags = tasks["categories"]["tags"]

    console.print("[bold green]Data refreshed successfully![/bold green]")
    return [tags, tasks, stats, used_tags]


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
    menu_renderable.insert(0, "[b]0.[/] [i]Return")

    panel = Panel(
        Columns(menu_renderable),
        title=f"[#ebcb8b][b]{title}[/b]",
        border_style="#ebcb8b",
        box=box.ROUNDED,
        width=20,
    )

    console.print(panel)
    selected = IntPrompt.ask("Enter the number of the action you want to perform")
    return selected


def display_main_menu():
    """
    Displays the main menu and navigates to selected submenus.

    Returns:
        None
    """
    categories = {
        "Backup": ["Backup Challenges", "Save user data"],
        "Challenges": ["List Challenges"],
        "Tasks": ["Broken tasks", "Sort alphabetically"],
        "Tags": ["Print tags", "Unused tags", "Fix tags"],
        "Stats": ["Print stats"],
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
