import sys  # KEEP: Needed for sys.exit

from pixabit.app import CliApp
from pixabit.utils.display import console, print

# This is the main entry point for the Pixabit CLI application.
if __name__ == "__main__":
    try:
        app = CliApp()
        app.run()

    except Exception as e:
        console.print(f"[error]\n--- An Unexpected Error Occurred ---[/error]")
        console.print_exception(show_locals=True)  # More detailed error for debugging
        sys.exit(1)

    except (KeyboardInterrupt, SystemExit):
        console.print(
            "\n[yellow]Operation cancelled by user. Exiting.[/yellow]", justify="center"
        )
        sys.exit(0)
