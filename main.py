#!/usr/bin/env python3

from utils.rich_utils import Confirm, IntPrompt, Panel, Columns, console
from core.auth_file import check_auth_file
from get import bkup_challenges, get_tags, get_tasks, get_stats, get_userdata
from interface import rich_stats, rich_tags, mainmenu
from actions import unused_tags, filter_task, sleeping, category_tags, challenges, sort

"""
main.py

Entry point for the Habitica CLI application. 
This application provides an interface to manage tasks, tags, challenges, and user data in Habitica.

Modules:
    - utils.rich_utils: Provides utilities for rich CLI formatting and input.
    - core.auth_file: Handles authentication file checks.
    - get: Contains functions to fetch Habitica data (tasks, tags, stats, etc.).
    - interface: Manages the user interface with rich visuals.
    - actions: Includes utilities for managing tags, tasks, and challenges.

Functions:
    - main(): Main event loop for the CLI application.
"""

from utils.rich_utils import Panel, Columns, console
from core.auth_file import check_auth_file
from get import get_tags, get_tasks, get_stats, get_userdata
from interface import mainmenu
from actions import sort

def main():
    """
    Main event loop for the Habitica CLI application.

    Continuously displays the main menu, captures user selections, 
    and delegates actions based on the selected menu option.
    """
    try:
        while True:
            # Display the main menu and get user selection
            selected_action = mainmenu.display_main_menu()
            
            # Execute the selected menu option
            mainmenu.select_option(selected_action)
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting Pixabit. Goodbye![/bold red]")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")

if __name__ == "__main__":
    main()
