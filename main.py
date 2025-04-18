# pixabit/main.py
# Note: This file likely won't be used directly for the TUI app,
# which will have its own entry point (e.g., calling PixabitTUIApp().run()).
# However, I'll review and format it as requested.

#!/usr/bin/env python3

# SECTION: MODULE DOCSTRING
"""Main entry point script for the Pixabit CLI application (LEGACY Rich version).

This script initializes the necessary components, sets up error handling,
and starts the main application loop defined in the `CliApp` class.
It is preserved for reference but likely replaced by a TUI-specific entry point.
"""

# SECTION: IMPORTS
import os
import sys
import traceback
from typing import Optional

# Attempt to import Pixabit components (assuming run from project root)
try:
    # Assuming cli/app.py is the entry point for the OLD Rich app
    from pixabit.cli.app import CliApp
    from pixabit.utils.display import Rule, console, print
except ImportError as import_err:
    import builtins

    builtins.print(
        "FATAL ERROR: Could not import Pixabit CLI application modules."
    )
    builtins.print(f"Import Error: {import_err}")
    builtins.print(
        "Ensure the script is run from the project root or the path is correct."
    )
    sys.exit(1)
except Exception as general_err:
    import builtins

    builtins.print(
        "FATAL ERROR: An unexpected error occurred during initial imports."
    )
    builtins.print(f"Error: {general_err}")
    traceback.print_exc()
    sys.exit(1)


# SECTION: MAIN EXECUTION BLOCK
if __name__ == "__main__":
    # ─── Welcome Message ───
    try:
        console.print(
            "\n🚀 Welcome to Pixabit - Habitica CLI Assistant (Rich Version) 🚀",
            style="highlight",
            justify="center",
        )
        console.print(Rule(style="rp_overlay"))
    except Exception:
        print("\n─── Welcome to Pixabit (Rich Version) ───")  # Fallback

    # ─── Instantiate and Run App ───
    app_instance: Optional[CliApp] = None  # Type hint
    try:
        app_instance = CliApp()  # Instantiate the Rich CLI App
        app_instance.run()  # Start the main application loop

    # ─── Graceful Exit on Ctrl+C ───
    except KeyboardInterrupt:
        try:
            console.print(
                "\n\n[bold yellow]⌨️ Ctrl+C detected. Exiting Pixabit gracefully.[/bold yellow]"
            )
        except Exception:
            print("\n\nExiting Pixabit (Ctrl+C).")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)  # Force exit if sys.exit is blocked

    # ─── Catch-All for Unexpected Errors ───
    except Exception as e:
        try:
            console.print(
                "\n\n[error]❌ An unexpected critical error occurred:[/error]"
            )
            console.print_exception(show_locals=True, word_wrap=False)
        except Exception as fallback_e:
            print("\n\nFATAL UNEXPECTED ERROR (Console failed):")
            print(f"Original Error Type: {type(e).__name__}")
            print(f"Original Error: {e}")
            print("\n─── Traceback ───")
            traceback.print_exc()
            print("─────────────────")
            print(f"Console fallback error: {fallback_e}")
        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)  # Force exit

    # ─── Final Exit Message (if loop broken normally) ───
    # Typically handled within app.run() when user chooses Exit.
    # try:
    #     console.print("\nPixabit finished.", style="info")
    # except Exception:
    #     print("\nPixabit finished.")
