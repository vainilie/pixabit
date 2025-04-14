# pixabit/__main__.py
# MARK: - MODULE DOCSTRING
"""Entry point for running the Pixabit package directly using 'python -m pixabit'.

Initializes and runs the main CLI application.
"""

# MARK: - IMPORTS
import os
import sys
import traceback

# --- Relative Imports for running within the package ---
try:
    # Use relative imports because this file is INSIDE the pixabit package
    from .cli.app import CliApp
    from .utils.display import Rule, console, print
except ImportError as import_err:
    # Fallback for potential execution issues
    import builtins

    builtins.print("FATAL ERROR: Could not import Pixabit components in __main__.py.")
    builtins.print(
        "Make sure you are running with 'python -m pixabit' from the directory *above* 'pixabit',"
    )
    builtins.print("or that the package is correctly installed.")
    builtins.print(f"Import Error: {import_err}")
    sys.exit(1)


# MARK: - MAIN EXECUTION FUNCTION
def main():
    """Initializes and runs the Pixabit CLI application."""
    try:
        console.print(
            "\n🚀 Executing Pixabit via `python -m pixabit` 🚀",
            style="highlight",
            justify="center",
        )
        console.print(Rule(style="rp_overlay"))
        app = CliApp()
        app.run()
    except KeyboardInterrupt:
        try:
            console.print(
                "\n\n[bold yellow]⌨️ Ctrl+C detected. Exiting Pixabit gracefully.[/bold yellow]"
            )
        except Exception:
            print("\n\nExiting Pixabit (Ctrl+C).")  # Fallback print
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        try:
            console.print("\n\n[error]❌ An unexpected critical error occurred:[/error]")
            console.print_exception(show_locals=True, word_wrap=False)
        except Exception as fallback_e:
            print("\n\nFATAL UNEXPECTED ERROR (Console failed):")
            print(f"Original Error Type: {type(e).__name__}")
            print(f"Original Error: {e}")
            print("\n--- Traceback ---")
            traceback.print_exc()
            print("-----------------")
            print(f"Console fallback error: {fallback_e}")
        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)


# MARK: - SCRIPT EXECUTION GUARD
if __name__ == "__main__":
    main()
