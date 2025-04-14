# pixabit/config_auth.py
# MARK: - MODULE DOCSTRING
"""Manages the creation and verification of the application's .env configuration file
specifically for MANDATORY credentials (Habitica User ID, API Token).

Provides functions to interactively create a `.env` file using prompts and
confirmations from the Rich library (via the `utils.display` helper module).
Includes `check_env_file` to verify existence and trigger creation if missing.
"""

# MARK: - IMPORTS
import datetime
import sys
from pathlib import Path

# Use themed display components
try:
    from .utils.display import Confirm, Prompt, console, print
except ImportError:  # Fallback for potential direct script execution or import issues
    import builtins

    print = builtins.print

    # Define dummy components if Rich is not available
    def Prompt_ask(prompt, **kwargs):
        return input(prompt)

    def Confirm_ask(prompt, **kwargs):
        return input(f"{prompt} [y/N]: ").lower() == "y"

    class DummyConsole:
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print(*args)

    console = DummyConsole()
    Prompt = type("DummyPrompt", (), {"ask": staticmethod(Prompt_ask)})()
    Confirm = type("DummyConfirm", (), {"ask": staticmethod(Confirm_ask)})()

# MARK: - CONSTANTS
# (No specific constants needed here, path is passed in)

# MARK: - CORE FUNCTIONS


# & - def create_env_file(env_path: Path) -> bool:
def create_env_file(env_path: Path) -> bool:
    """Interactively creates or overwrites mandatory credentials in a .env file.

    Prompts for Habitica User ID and API Token. Confirms overwrite.
    Creates file with placeholders if interactive help is declined.

    Args:
        env_path: The Path object for the .env file.

    Returns:
        bool: True if the file was created/updated successfully, False otherwise.
    """
    filename_display = f"[file]{env_path.name}[/]"
    filepath_display = f"[file]{env_path}[/]"
    interactive_mode = False  # Track if user actively provided credentials

    # --- 1. Check overwrite ---
    if env_path.exists():
        console.print(f"[warning]File {filename_display} exists.[/warning]")
        if not Confirm.ask(
            f"Overwrite MANDATORY credentials (User ID, API Token) in {filename_display}?",
            default=False,
        ):
            console.print(
                f"[info]ℹ️ Keeping existing mandatory credentials in {filename_display}. Optional tags can be configured separately.[/info]"
            )
            return True  # File exists and user chose not to modify essentials

    # --- 2. Get User Input ---
    console.print(f"\n⚙️ Setting up MANDATORY credentials in {filename_display}.")
    if Confirm.ask("Provide credentials now? (Choose No to create placeholders)", default=True):
        interactive_mode = True  # User chose interactive setup
        console.print(
            "\n[bold yellow]🔑 Enter Habitica API Credentials[/bold yellow]"
            "\n[dim](Find at: https://habitica.com/user/settings/api)[/dim]"
        )
        input_userid = ""
        while not input_userid or input_userid == "YOUR_HABITICA_USER_ID_HERE":
            input_userid = Prompt.ask(
                "  Enter your [info]Habitica User ID[/info]", default="YOUR_HABITICA_USER_ID_HERE"
            )
            if not input_userid or input_userid == "YOUR_HABITICA_USER_ID_HERE":
                console.print("[error]User ID cannot be empty or the placeholder.[/error]")
                if not Confirm.ask("Try again?", default=True):
                    input_userid = "YOUR_HABITICA_USER_ID_HERE"  # Reset to placeholder
                    console.print("[warning]Creating file with placeholder User ID.[/warning]")
                    interactive_mode = False  # Switched to placeholder mode
                    break  # Exit loop, use placeholder

        input_apitoken = ""
        # Only ask for token if we successfully got a real User ID in interactive mode
        if interactive_mode and input_userid != "YOUR_HABITICA_USER_ID_HERE":
            while not input_apitoken or input_apitoken == "YOUR_API_TOKEN_HERE":
                input_apitoken = Prompt.ask(
                    "  Enter your [info]Habitica API Token[/info]",
                    default="YOUR_API_TOKEN_HERE",
                    password=True,
                )
                if not input_apitoken or input_apitoken == "YOUR_API_TOKEN_HERE":
                    console.print("[error]API Token cannot be empty or the placeholder.[/error]")
                    if not Confirm.ask("Try again?", default=True):
                        input_apitoken = "YOUR_API_TOKEN_HERE"  # Reset to placeholder
                        console.print(
                            "[warning]Creating file with placeholder API Token.[/warning]"
                        )
                        interactive_mode = False  # Switched to placeholder mode
                        break  # Exit loop, use placeholder

        elif interactive_mode:  # User ID is placeholder, so token must be too
            input_apitoken = "YOUR_API_TOKEN_HERE"
            interactive_mode = False  # No longer truly interactive

    else:  # User chose No for interactive help initially
        console.print("\nCreating file with placeholder values for manual editing.")
        input_userid = "YOUR_HABITICA_USER_ID_HERE"
        input_apitoken = "YOUR_API_TOKEN_HERE"
        interactive_mode = False

    # --- 3. Build Content ---
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env_content = f"""# Habitica Credentials (MANDATORY)
# Generated by pixabit setup script on {timestamp}
# Find these values at: https://habitica.com/user/settings/api

HABITICA_USER_ID="{input_userid}"
HABITICA_API_TOKEN="{input_apitoken}"

# --- Optional Tag IDs (Configure via 'pixabit setup-tags' or manually) ---
# CHALLENGE_TAG_ID=""
# PERSONAL_TAG_ID=""
# PSN_TAG_ID=""
# NOT_PSN_TAG_ID=""
# NO_ATTR_TAG_ID=""
# ATTR_TAG_STR_ID=""
# ATTR_TAG_INT_ID=""
# ATTR_TAG_CON_ID=""
# ATTR_TAG_PER_ID=""
""".strip()

    # --- 4. Write File ---
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        with env_path.open("w", encoding="utf-8") as envfile:
            envfile.write(env_content + "\n")

        console.print(
            f"\n[success]✅ Mandatory credentials saved/updated in {filepath_display}.[/success]"
        )
        # Use the interactive_mode flag to give appropriate next steps
        if (
            not interactive_mode
            or input_userid == "YOUR_HABITICA_USER_ID_HERE"
            or input_apitoken == "YOUR_API_TOKEN_HERE"
        ):
            console.print(
                f"[warning]⚠️ Remember to manually edit {filename_display} and replace placeholder values if needed.[/warning]"
            )
        else:
            console.print(
                "[info]ℹ️ You can now configure optional tags if desired (e.g., `pixabit setup-tags`).[/info]"
            )

        console.print(
            f"[warning]🔒 IMPORTANT:[/warning] Ensure {filename_display} is in `.gitignore`!"
        )
        return True  # File written successfully

    except OSError as e:
        console.print(f"[error]❌ Error writing file {filepath_display}: {e}[/error]")
        return False
    except Exception as e:
        console.print(f"[error]❌ Unexpected error writing {filepath_display}: {e}[/error]")
        return False


# MARK: - HELPER ENTRY FUNCTION


# & - def check_env_file(env_path: Path) -> None:
def check_env_file(env_path: Path) -> None:
    """Checks if the .env file exists and prompts for creation if missing. Exits if creation fails or is skipped.

    Args:
        env_path: Path object for the .env file.
    """
    filename_display = f"[file]{env_path.name}[/]"
    filepath_display = f"[file]{env_path}[/]"

    console.log(f"⌛ Checking for configuration file: {filepath_display}")
    if not env_path.exists():
        console.print(f"[warning]⚠️ File {filename_display} not found.[/warning]")
        if Confirm.ask(
            f"\nCreate the {filename_display} configuration file now? (Needed for credentials)",
            default=True,
        ):
            if not create_env_file(env_path):  # Call creation function
                console.print(
                    "[error]❌ Failed to create .env file. Application cannot continue.[/error]"
                )
                sys.exit(1)  # Exit if creation failed
        else:
            console.print(
                f"[error]❌ Skipping {filename_display} creation. Application requires credentials and cannot continue.[/error]"
            )
            sys.exit(1)  # Exit if user skips creation
    else:
        console.print(
            f"[success]✅ Configuration file {filename_display} found at {filepath_display}.[/success]"
        )
