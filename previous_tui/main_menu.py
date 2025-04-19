# previous_tui_files/main_menu.py (LEGACY CLI MENU)

# SECTION: MODULE DOCSTRING
"""
LEGACY: Provides the user interface functions for the old Rich-based CLI.

Includes functions for displaying menus and dispatching actions based on user
input using Rich prompts and synchronous logic. This file is for **reference only**.
The TUI uses Textual widgets and event handling for menus and actions.
"""

# SECTION: IMPORTS
from typing import Any, List, Dict, Callable # Added typing

# Optional: Art for header
try: from art import text2art
except ImportError: text2art = lambda t: t # type: ignore

# Local Imports (These point to OLD structure - DEPRECATED)
# from basis import api_check # Old check
# from heart.basis import __get_data as get # Old sync API calls
# from processors import (backup_challenges, fix_attributes, fix_unused_tags, # Old processors
#                         process_stats, process_tags, process_task)
# from TUI.main_functions import select_option # Old dispatcher
# from TUI.rich_utils import Columns, Confirm, IntPrompt, Panel, console, print, box # Old Rich utils

# Define dummy fallbacks if imports fail during review
try:
    from pixabit.cli.rich_utils_fallback import Confirm, IntPrompt, Panel, Columns, console, print, box # Fallback Rich utils
except ImportError:
     import builtins
     class Confirm: @staticmethod # type: ignore
     def ask(*a,**kw): return False
     class IntPrompt: @staticmethod # type: ignore
     def ask(*a,**kw): return 0
     class Panel: pass; class Columns: pass; console=None; print=builtins.print; class box: ROUNDED = None # type: ignore
     print = builtins.print

# Old dispatcher function (Reference only)
def select_option_legacy(action_name: str) -> None: pass

# SECTION: LEGACY FUNCTIONS

# FUNC: initialize_data (Legacy - Reference Only)
def initialize_data_legacy() -> List[Any]:
    """Legacy: Initializes or refreshes data from Habitica synchronously."""
    print("[bold green]Refreshing data (Legacy Sync)...[/bold green]")
    # tags = process_tags.process_tags() # Old processor call
    # tasks = process_task.process_tasks() # Old processor call
    # stats = process_stats.process_tasks() # Old processor call
    # used_tags = tasks["categories"]["tags"] # Accessing old structure
    print("[bold green]Data refreshed successfully! (Legacy Placeholder)[/bold green]")
    # return [tags, tasks, stats, used_tags]
    return [[], {}, {}, set()] # Return dummy data structure


# FUNC: display_menu (Legacy - Reference Only)
def display_menu_legacy(title: str, options: List[str]) -> int:
    """Legacy: Displays a menu using Rich and returns user choice."""
    menu_renderable = [f"[b]{num}.[/] [i]{option}" for num, option in enumerate(options, start=1)]
    menu_renderable.insert(0, "[b]0.[/] [i]Return/Exit[/]") # Adjusted label
    try: # Wrap Rich usage
        panel = Panel(
            Columns(menu_renderable, equal=True, expand=True), # Try Columns
            title=f"[#ebcb8b][b]{title}[/b]", border_style="#ebcb8b",
            box=box.ROUNDED, padding=1, expand=False
        )
        console.print(panel)
    except Exception as e:
         print(f"Error displaying menu with Rich: {e}")
         # Fallback display
         print(f"\n--- {title} ---")
         for item in menu_renderable: print(item.replace("[b]", "").replace("[/]", "").replace("[i]", "")) # Basic print
         print("---------------")

    try:
        selected = IntPrompt.ask("Enter choice number", choices=[str(i) for i in range(len(options)+1)])
        return selected
    except Exception as e_ask:
         print(f"Input error: {e_ask}")
         return -1 # Indicate error


# FUNC: display_main_menu (Legacy - Reference Only)
def display_main_menu_legacy() -> None:
    """Legacy: Displays the main menu and navigates submenus (Sync)."""
    categories: Dict[str, List[str]] = {
        "Backup": ["Backup Challenges", "Save user data"],
        "Challenges": ["List Challenges"],
        "Tasks": ["Broken tasks", "Sort alphabetically"],
        "Tags": ["Print tags", "Unused tags", "Fix tags"],
        "Stats": ["Print stats"],
        "Others": ["Toogle Sleeping", "Refresh Data"],
    }

    # Initial data load (placeholder call)
    # tags, tasks, stats, used_tags = initialize_data_legacy() # Example state management

    while True:
        main_menu_options = list(categories.keys()) + ["Exit"]
        selected_category_num = display_menu_legacy("Main Menu (Legacy)", main_menu_options)

        if selected_category_num == -1: continue # Error
        if selected_category_num == 0: # Exit from Main Menu
             console.print("\n[bold red]Exiting Pixabit (Legacy). Goodbye![/bold red]")
             exit()
        if selected_category_num == len(main_menu_options): # Explicit Exit option
            console.print("\n[bold red]Exiting Pixabit (Legacy). Goodbye![/bold red]")
            exit()

        if 1 <= selected_category_num <= len(categories):
            selected_category_name = main_menu_options[selected_category_num - 1]
            submenu_options = categories[selected_category_name]
            while True: # Submenu loop
                selected_action_num = display_menu_legacy(f"{selected_category_name} Menu (Legacy)", submenu_options)
                if selected_action_num == -1: continue # Error
                if selected_action_num == 0: break # Return to main menu

                if 1 <= selected_action_num <= len(submenu_options):
                    action_name = submenu_options[selected_action_num - 1]
                    if action_name == "Refresh Data":
                        # tags, tasks, stats, used_tags = initialize_data_legacy() # Refresh state
                        print("Data Refreshed (Legacy Placeholder)")
                    else:
                        select_option_legacy(action_name) # Call old dispatcher
                else:
                    console.print(f"[bold red]Invalid selection. Choose 0 to {len(submenu_options)}.[/bold red]")
        else:
             console.print(f"[bold red]Invalid selection. Choose 0 to {len(main_menu_options)}.[/bold red]")

