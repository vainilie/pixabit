#!/usr/bin/env python3

# main.py
# MARK: - MODULE DOCSTRING
"""Main entry point script for the Pixabit CLI application.

This script initializes the necessary components, sets up error handling,
and starts the main application loop defined in the `CliApp` class.
"""

# MARK: - IMPORTS
import os
import sys
import traceback  # For fallback error printing

# --- Add project root to path if necessary ---
# This ensures that 'import pixabit' works correctly even if the script
# is run from a different directory, though often not needed if run from root.
# try:
#     project_root = Path(__file__).resolve().parent
#     if str(project_root) not in sys.path:
#         sys.path.insert(0, str(project_root))
# except NameError: # __file__ might not be defined in some contexts
#      if str(Path.cwd()) not in sys.path:
#          sys.path.insert(0, str(Path.cwd()))

# --- Import Core Application Components ---
# Attempt to import after potentially modifying path
try:
    from pixabit.cli.app import CliApp

    # Import the themed console for top-level messages/errors
    from pixabit.utils.display import Rule, console, print
except ImportError as import_err:
    # Use standard print for this critical error
    import builtins

    builtins.print("FATAL ERROR: Could not import Pixabit application modules.")
    builtins.print(
        "Ensure the script is run from the project root directory containing the 'pixabit' folder."
    )
    builtins.print(f"Import Error: {import_err}")
    sys.exit(1)
except Exception as general_err:
    # Catch other potential errors during import (rare)
    import builtins

    builtins.print("FATAL ERROR: An unexpected error occurred during initial imports.")
    builtins.print(f"Error: {general_err}")
    traceback.print_exc()  # Print full traceback for unexpected import errors
    sys.exit(1)


# MARK: - MAIN EXECUTION BLOCK
if __name__ == "__main__":
    # --- Welcome Message ---
    # Use the themed console if available
    try:
        console.print(
            "\n🚀 Welcome to Pixabit - Habitica CLI Assistant 🚀",
            style="highlight",
            justify="center",
        )
        console.print(Rule(style="rp_overlay"))  # Themed separator
    except Exception:  # Fallback if console failed somehow
        print("\n--- Welcome to Pixabit ---")

    # --- Instantiate and Run App ---
    try:
        app = CliApp()
        app.run()  # Start the main application loop

    # --- Graceful Exit on Ctrl+C ---
    except KeyboardInterrupt:
        try:
            # Use themed console for exit message
            console.print(
                "\n\n[bold yellow]⌨️ Ctrl+C detected. Exiting Pixabit gracefully.[/bold yellow]"
            )
        except Exception:
            print("\n\nExiting Pixabit (Ctrl+C).")
        # Attempt a clean exit
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)  # Force exit if sys.exit is blocked

    # --- Catch-All for Unexpected Errors ---
    except Exception as e:
        # Try using the themed console first for a nice traceback
        try:
            console.print("\n\n[error]❌ An unexpected critical error occurred:[/error]")
            # Show detailed traceback using Rich
            console.print_exception(show_locals=True, word_wrap=False)
        except Exception as fallback_e:
            # Fallback to standard printing if console fails
            print("\n\nFATAL UNEXPECTED ERROR (Console failed):")
            print(f"Original Error Type: {type(e).__name__}")
            print(f"Original Error: {e}")
            print("\n--- Traceback ---")
            traceback.print_exc()
            print("-----------------")
            print(f"Console fallback error: {fallback_e}")
        # Exit with a non-zero code to indicate failure
        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)  # Force exit

    # --- Final Exit Message (if loop broken normally) ---
    # The exit message is typically handled within app.run() when the user chooses Exit.
    # Adding one here might be redundant unless app.run() can return without printing.
    # try:
    #     console.print("\nPixabit finished.", style="info")
    # except Exception:
    #     print("\nPixabit finished.")
