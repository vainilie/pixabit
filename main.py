#!/usr/bin/env python3

from heart.TUI.rich_utils import Confirm, IntPrompt, Panel, Columns, console
from heart.TUI import main_menu
from rich.text import Text
from art import text2art
from heart.basis.api_check import check_api_status


def main():
    """
    Main event loop for the Habitica CLI application.

    Continuously displays the main menu, captures user selections,
    and delegates actions based on the selected menu option.
    """
    try:
        console.print(Text(text2art("Pixabit", font="rnd-small"), style="#cba6f7"))
        # Check authentication file
        check_api_status()
        # Call initialize_data on startup
        main_menu.initialize_data()
        main_menu.display_main_menu()

        while True:
            # Display the main menu and get user selection
            selected_action = main_menu.display_main_menu()

            # Execute the selected menu option
            main_menu.select_option(selected_action)
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting Pixabit. Goodbye![/bold red]")
        
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")


if __name__ == "__main__":
    main()
