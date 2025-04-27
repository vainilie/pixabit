# pixabit/cli/config_auth.py (Utility)

# SECTION: MODULE DOCSTRING
"""Manages creation/verification of MANDATORY credentials in the .env file.

Provides functions to interactively create a `.env` file using prompts.
Used during initial application setup.
"""

# SECTION: IMPORTS
import datetime
import sys
from pathlib import Path
from typing import Any  # For fallback type hints

# Use themed display components
try:
    from pixabit.helpers._rich import (
        Confirm,
        Prompt,
        console,
        print,
    )  # Use .. for parent utils
except (
    ImportError
):  # Fallback for potential direct script execution or import issues
    import builtins

    print = builtins.print

    def Prompt_ask(prompt: str, **kwargs: Any) -> str:
        return input(prompt)

    def Confirm_ask(prompt: str, **kwargs: Any) -> bool:
        return input(f"{prompt} [y/N]: ").lower() == "y"

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

    console = DummyConsole()
    # Create dummy classes matching Prompt/Confirm interface
    Prompt = type("DummyPrompt", (), {"ask": staticmethod(Prompt_ask)})()  # type: ignore
    Confirm = type("DummyConfirm", (), {"ask": staticmethod(Confirm_ask)})()  # type: ignore
    print(
        "[Warning] Could not import display utils in config_auth.py. Using fallbacks."
    )

# SECTION: FUNCTIONS


# FUNC: create_env_file
def create_env_file(env_path: Path) -> bool:
    """Interactively creates or overwrites mandatory credentials in a .env file.

    Args:
        env_path: The Path object for the .env file.

    Returns:
        True if the file was created/updated successfully, False otherwise.
    """
    filename_display = f"[file]{env_path.name}[/]"
    filepath_display = f"[file]{env_path}[/]"
    interactive_mode = False

    # Check overwrite
    if env_path.exists():
        console.print(f"[warning]File {filename_display} exists.[/warning]")
        if not Confirm.ask(
            f"Overwrite MANDATORY credentials in {filename_display}?",
            default=False,
        ):
            console.print(
                f"[info]ℹ️ Keeping existing mandatory credentials in {filename_display}.[/info]"
            )
            return True  # Keep existing, success

    # Get User Input
    console.print(
        f"\n⚙️ Setting up MANDATORY credentials in {filename_display}."
    )
    if Confirm.ask(
        "Provide credentials now? (No = create placeholders)", default=True
    ):
        interactive_mode = True
        console.print(
            "\n[bold yellow]🔑 Enter Habitica API Credentials[/]\n[dim](Find at: https://habitica.com/user/settings/api)[/dim]"
        )

        # Get User ID
        input_userid = ""
        placeholder_userid = "YOUR_HABITICA_USER_ID_HERE"
        while not input_userid or input_userid == placeholder_userid:
            input_userid = Prompt.ask(
                "  Enter your [info]Habitica User ID[/info]",
                default=placeholder_userid,
            )
            if not input_userid or input_userid == placeholder_userid:
                console.print(
                    "[error]User ID cannot be empty or the placeholder.[/error]"
                )
                if not Confirm.ask("Try again?", default=True):
                    input_userid = placeholder_userid
                    interactive_mode = False
                    console.print(
                        "[warning]Creating file with placeholder User ID.[/warning]"
                    )
                    break

        # Get API Token only if User ID was entered interactively
        input_apitoken = ""
        placeholder_token = "YOUR_API_TOKEN_HERE"
        if interactive_mode and input_userid != placeholder_userid:
            while not input_apitoken or input_apitoken == placeholder_token:
                input_apitoken = Prompt.ask(
                    "  Enter your [info]Habitica API Token[/info]",
                    default=placeholder_token,
                    password=True,
                )
                if not input_apitoken or input_apitoken == placeholder_token:
                    console.print(
                        "[error]API Token cannot be empty or the placeholder.[/error]"
                    )
                    if not Confirm.ask("Try again?", default=True):
                        input_apitoken = placeholder_token
                        interactive_mode = False
                        console.print(
                            "[warning]Creating file with placeholder API Token.[/warning]"
                        )
                        break
        elif interactive_mode:  # User ID is placeholder, so token must be too
            input_apitoken = placeholder_token
            interactive_mode = False

    else:  # User chose No for interactive setup
        console.print(
            "\nCreating file with placeholder values for manual editing."
        )
        input_userid = "YOUR_HABITICA_USER_ID_HERE"
        input_apitoken = "YOUR_API_TOKEN_HERE"
        interactive_mode = False

    # Build Content
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env_content = f"""# Habitica Credentials (MANDATORY)
# Generated by pixabit setup script on {timestamp}
# Find these values at: https://habitica.com/user/settings/api
HABITICA_USER_ID="{input_userid}"
HABITICA_API_TOKEN="{input_apitoken}"

# --- Optional Tag IDs (Configure via application menu or manually) ---
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

    # Write File
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            env_content + "\n", encoding="utf-8"
        )  # Simpler write
        console.print(
            f"\n[success]✅ Mandatory credentials saved/updated in {filepath_display}.[/success]"
        )
        if (
            not interactive_mode
            or input_userid == placeholder_userid
            or input_apitoken == placeholder_token
        ):
            console.print(
                f"[warning]⚠️ Remember to manually edit {filename_display} and replace placeholders if needed.[/warning]"
            )
        else:
            console.print(
                "[info]ℹ️ Mandatory setup complete. Optional tags can be configured via the app menu.[/info]"
            )
        console.print(
            f"[warning]🔒 IMPORTANT:[/warning] Ensure {filename_display} is in `.gitignore`!"
        )
        return True
    except OSError as e:
        console.print(
            f"[error]❌ Error writing file {filepath_display}: {e}[/error]"
        )
        return False
    except Exception as e:
        console.print(
            f"[error]❌ Unexpected error writing {filepath_display}: {e}[/error]"
        )
        return False


# FUNC: check_env_file
def check_env_file(env_path: Path) -> None:
    """Checks if the .env file exists and prompts for creation if missing.

    Exits the application if the .env file is missing and creation fails or is skipped.

    Args:
        env_path: Path object for the .env file.
    """
    filename_display = f"[file]{env_path.name}[/]"
    filepath_display = f"[file]{env_path}[/]"

    console.log(f"⌛ Checking for configuration file: {filepath_display}")
    if not env_path.exists():
        console.print(
            f"[warning]⚠️ Configuration file {filename_display} not found.[/warning]"
        )
        if Confirm.ask(
            f"\nCreate the {filename_display} configuration file now?",
            default=True,
        ):
            if not create_env_file(env_path):
                console.print(
                    "[error]❌ Failed to create .env file. Application cannot continue.[/error]"
                )
                sys.exit(1)
        else:
            console.print(
                f"[error]❌ Skipping {filename_display} creation. Application requires credentials.[/error]"
            )
            sys.exit(1)
    # else: console.print(f"[success]✅ Configuration file {filename_display} found.[/success]") # Becomes verbose
