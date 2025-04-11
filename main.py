# --- Entry Point ---
# In your main.py (or similar root script):
#
import sys  # KEEP: Needed for sys.exit

from pixabit.menu import CliApp
from pixabit.utils.display import console, print

#
if __name__ == "__main__":
    try:
        app = CliApp()
        app.run()
    except KeyboardInterrupt:
        print("\n[yellow]Operation cancelled by user. Exiting.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]\n--- An Unexpected Error Occurred ---[/bold red]")
        console.print_exception(show_locals=True)  # More detailed error for debugging
        sys.exit(1)
