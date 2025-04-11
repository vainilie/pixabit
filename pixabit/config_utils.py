# pixabit/tag_setup.py (or config_utils.py / cli/setup.py etc.)
# MARK: - MODULE DOCSTRING
"""
Provides functionality for interactively setting up specific Tag IDs in the .env file.

This module fetches existing tags from the user's Habitica account, displays them,
and prompts the user to select or create tags for predefined configuration roles
(e.g., Challenge Tag, Attribute Tags). The selected/created tag IDs are then
saved back to the `.env` file.

Functions:
    interactive_tag_setup(api_client): Runs the main interactive setup process.
    configure_tags(): A simple wrapper to initialize API and run setup, useful for CLI commands.

Requires:
    - An authenticated `HabiticaAPI` instance from `.api`.
    - Rich library components (`Confirm`, `Prompt`, `Console`, `IntPrompt`, `Table`)
      likely provided via a `utils.display` module.
    - `python-dotenv` library functions (`find_dotenv`, `get_key`, `set_key`).
"""

# MARK: - IMPORTS
import os
from typing import Any, Dict, List, Optional  # Added Any for tag data

from dotenv import find_dotenv, get_key, set_key

from .api import HabiticaAPI
from .utils.display import Confirm, IntPrompt, Prompt, Table, console, print

# MARK: - CONSTANTS
# Dictionary mapping descriptive names to the .env variable keys for specific tags
TAG_CONFIG_KEYS: Dict[str, str] = {
    "Challenge Tag (for challenge tasks)": "CHALLENGE_TAG_ID",
    "Personal/Owned Tag (for non-challenge tasks)": "PERSONAL_TAG_ID",
    "Poisoned Tag (for poison challenge)": "PSN_TAG_ID",
    "Not Poisoned Tag (default status)": "NOT_PSN_TAG_ID",
    "No Attribute Tag (for tasks w/o STR/INT/etc)": "NO_ATTR_TAG_ID",
    "Strength Attribute Tag": "ATTR_TAG_STR_ID",
    "Intelligence Attribute Tag": "ATTR_TAG_INT_ID",
    "Constitution Attribute Tag": "ATTR_TAG_CON_ID",
    "Perception Attribute Tag": "ATTR_TAG_PER_ID",
    # Add any other specific configuration tags you need here
}


# MARK: - CORE FUNCTIONS
def interactive_tag_setup(api_client: HabiticaAPI) -> None:
    """
    Interactively configures specific tag IDs in the .env file.

    Fetches all tags from the user's Habitica account via the provided API client.
    Displays the tags in a table. Prompts the user to select an existing tag,
    create a new tag (via API), or keep the current value (if one exists in
    .env) for each tag type defined in `TAG_CONFIG_KEYS`. Finally, confirms
    with the user before saving the chosen tag IDs back to the .env file.

    Args:
        api_client (HabiticaAPI): An authenticated instance of the HabiticaAPI client.

    Returns:
        None: The function modifies the .env file directly.

    Raises:
        requests.exceptions.RequestException: If API calls to fetch or create tags fail.
        IOError: If reading from or writing to the .env file fails.
        Exception: Catches and reports other unexpected errors during the process.
    """
    CONSOLE.print(
        "[bold cyan]--- Interactive Tag Configuration ---[/]", justify="center"
    )

    # --- 1. Find .env file path ---
    # find_dotenv() searches upwards from the current file or CWD
    dotenv_path = find_dotenv(
        raise_error_if_not_found=False, usecwd=True
    )  # Search CWD too
    if not dotenv_path or not os.path.exists(dotenv_path):
        # If not found, try creating one at project root (similar to config.py logic)
        try:
            # Assume this script is somewhere within the project structure
            # Resolve needed for parent.parent if __file__ is relative
            project_root = Path(__file__).resolve().parent.parent
            dotenv_path_candidate = project_root / ".env"
            CONSOLE.print(
                f"No .env found automatically, checking/creating: [cyan]{dotenv_path_candidate}[/]"
            )
            if not os.path.exists(dotenv_path_candidate):
                # Create empty file if it doesn't exist
                open(dotenv_path_candidate, "a").close()
                CONSOLE.print(".env file created.")
            dotenv_path = str(dotenv_path_candidate)  # Use the created path
        except Exception as e:
            CONSOLE.print(f"[bold red]Could not find or create .env file: {e}[/]")
            CONSOLE.print("Please ensure a .env file exists in your project root.")
            return
    CONSOLE.print(f"Using configuration file: [cyan]{dotenv_path}[/]")

    # --- 2. Fetch existing tags ---
    all_tags: List[Dict[str, Any]] = []
    try:
        CONSOLE.print("Fetching all available tags from Habitica...")
        all_tags = api_client.get_tags()  # get_tags should return a list
        if not isinstance(all_tags, list):  # Add explicit type check
            CONSOLE.print(
                f"[bold red]Error:[/bold red] Expected a list of tags from API, but received {type(all_tags)}. Cannot proceed."
            )
            return
        if not all_tags:
            CONSOLE.print(
                "[yellow]No tags found in your Habitica account. You can create them during this setup.[/]"
            )
            # Allow proceeding even if no tags exist yet

        # Sort tags for consistent display
        all_tags.sort(key=lambda t: t.get("name", "").lower())
        CONSOLE.print(f"Found {len(all_tags)} tags.")

    except Exception as e:
        CONSOLE.print(f"[bold red]Error fetching tags from Habitica API: {e}[/]")
        return  # Cannot proceed without tags list

    # --- 3. Display tags ---
    # Filter out tags without IDs just before display/selection, keep original list intact
    valid_tags_for_selection = [tag for tag in all_tags if tag.get("id")]
    num_tags_selectable = len(valid_tags_for_selection)

    table = Table(
        title="Available Habitica Tags", show_lines=True, expand=False, min_width=60
    )
    table.add_column("Num", style="dim", width=4, justify="right")
    table.add_column("Name", style="cyan", max_width=40)  # Adjust width as needed
    table.add_column("ID", style="magenta", no_wrap=True)

    if not valid_tags_for_selection:
        table.add_row("...", "[italic]No existing tags found[/italic]", "...")
    else:
        for i, tag in enumerate(valid_tags_for_selection):
            # Use i+1 for display number, matching valid list index+1
            table.add_row(
                str(i + 1), tag.get("name", "[i]No Name[/i]"), tag.get("id", "N/A")
            )

    CONSOLE.print(table)
    if not valid_tags_for_selection:
        CONSOLE.print(
            "[yellow]You'll need to use the 'Create New' option for all tags.[/]"
        )

    # --- 4. Prompt user for each required tag ---
    selected_ids: Dict[str, str] = {}  # Store chosen env_key: tag_id pairs

    for tag_description, env_key in TAG_CONFIG_KEYS.items():
        CONSOLE.print(
            f"\n--- Configuring: [bold green]{tag_description}[/bold green] (Variable: {env_key}) ---"
        )
        # Get current value from .env to show the user and allow keeping it
        current_value_id = get_key(
            dotenv_path, env_key
        )  # Returns None if key not found
        current_display = ""
        current_name = None
        if current_value_id:
            # Find the name corresponding to the current ID
            current_tag = next(
                (t for t in all_tags if t.get("id") == current_value_id), None
            )
            if current_tag:
                current_name = current_tag.get("name", "[i]Unknown Name[/i]")
                current_display = f" (Current: '[cyan]{current_name}[/cyan]')"
            else:
                # ID exists in .env but not in fetched tags (maybe deleted in Habitica?)
                current_display = f" (Current ID: [magenta]{current_value_id}[/magenta] - [yellow]Tag not found in API list![/yellow])"

        # Inner loop to handle retries on invalid input for a single tag type
        while True:
            try:
                # Build prompt text dynamically based on available options
                prompt_options = ""
                valid_choices = [
                    str(i) for i in range(num_tags_selectable + 1)
                ]  # 0 to N
                if num_tags_selectable > 0:
                    prompt_options += f"1-{num_tags_selectable} Select Existing, "
                prompt_options += "0 Create New"
                if current_value_id:
                    prompt_options += ", -1 Keep Current"
                    valid_choices.append("-1")

                prompt_text = f"Enter number for '[bold]{tag_description}[/bold]'\n({prompt_options}){current_display}: "

                # Use IntPrompt, allowing negative numbers only if 'Keep Current' is an option
                choice = IntPrompt.ask(
                    prompt_text, choices=valid_choices, show_choices=False
                )

                # --- Handle different choices ---
                if choice == -1:
                    if current_value_id:
                        # User wants to keep the current value
                        selected_ids[env_key] = current_value_id
                        CONSOLE.print(
                            f"  Keeping current value '[cyan]{current_name or current_value_id}[/cyan]' for {tag_description}."
                        )
                        break  # Exit inner loop, proceed to next tag type
                    else:
                        CONSOLE.print(
                            "[prompt.invalid]Cannot keep current value as none is set. Please select or create.[/]"
                        )
                        # Continue inner loop to re-prompt

                elif 1 <= choice <= num_tags_selectable:
                    # Existing tag selected - use the valid_tags_for_selection list
                    selected_index = choice - 1
                    selected_tag = valid_tags_for_selection[
                        selected_index
                    ]  # Get from the filtered list
                    tag_id = selected_tag.get("id")
                    tag_name = selected_tag.get("name", "[i]No Name[/i]")
                    if tag_id:
                        selected_ids[env_key] = tag_id
                        CONSOLE.print(
                            f"  Selected '[cyan]{tag_name}[/cyan]' ([magenta]{tag_id}[/magenta]) for {tag_description}."
                        )
                        break  # Exit inner loop
                    else:  # Should not happen if valid_tags_for_selection is built correctly
                        CONSOLE.print(
                            "[bold red]Internal Error:[/bold red] Selected tag has no ID. Please report this."
                        )

                elif choice == 0:
                    # User wants to create a new tag
                    if Confirm.ask(
                        f"Create a new Habitica tag for '[bold]{tag_description}[/bold]'?"
                    ):
                        # Suggest a default name based on the description
                        default_name = (
                            tag_description.split("(")[0]
                            .strip()
                            .replace("/", "_")
                            .replace(" ", "_")
                        )
                        new_name = Prompt.ask(
                            "Enter name for the new tag", default=default_name
                        )

                        if new_name:
                            try:
                                CONSOLE.print(
                                    f"Creating tag '[cyan]{new_name}[/cyan]' via API..."
                                )
                                # Call the API to create the tag
                                created_tag_data = api_client.create_tag(new_name)
                                if created_tag_data and created_tag_data.get("id"):
                                    new_id = created_tag_data["id"]
                                    new_name_from_api = created_tag_data.get(
                                        "name", new_name
                                    )  # Use name from API response
                                    CONSOLE.print(
                                        f"[bold green]Successfully created tag '[cyan]{new_name_from_api}[/cyan]' with ID: [magenta]{new_id}[/magenta][/]"
                                    )
                                    selected_ids[env_key] = new_id

                                    # Add to local lists to make it selectable *if* needed later in this same run
                                    # (Note: the displayed table doesn't update dynamically)
                                    all_tags.append(created_tag_data)
                                    valid_tags_for_selection.append(created_tag_data)
                                    num_tags_selectable = len(
                                        valid_tags_for_selection
                                    )  # Update count

                                    break  # Tag created and selected, exit inner loop
                                else:
                                    CONSOLE.print(
                                        f"[bold red]API Error:[/bold red] Did not return valid data for created tag '{new_name}'. Please select an existing tag or try again."
                                    )
                            except Exception as create_err:
                                CONSOLE.print(
                                    f"[bold red]Error creating tag '{new_name}': {create_err}[/]"
                                )
                                # Allow user to retry or select existing by continuing loop
                        else:
                            CONSOLE.print("Tag creation cancelled (no name entered).")
                            # Continue inner loop
                    else:
                        CONSOLE.print("Tag creation cancelled.")
                        # Continue inner loop
                else:
                    # Invalid number entered (should be caught by IntPrompt choices, but maybe not)
                    CONSOLE.print(
                        f"[prompt.invalid]Invalid choice.[/] Please use options: {prompt_options}."
                    )
                    # Continue inner loop

            except (
                ValueError
            ):  # Catches non-integer input if IntPrompt fails validation
                CONSOLE.print(
                    f"[prompt.invalid]Please enter a valid number ({prompt_options}).[/]"
                )
                # Continue inner loop
            except NotImplementedError:  # From DummyIntPrompt if Rich unavailable
                CONSOLE.print(
                    "[bold red]Error:[/bold red] Rich library components are required for interaction."
                )
                return  # Exit function if interaction isn't possible

        # --- End of inner while True loop ---
    # --- End of for tag_description... loop ---

    # --- 5. Confirm before saving ---
    CONSOLE.print("\n" + "=" * 60)
    CONSOLE.print("[bold yellow]Review Final Selections:[/]")
    all_selections_valid = True
    for desc, key in TAG_CONFIG_KEYS.items():
        tag_id = selected_ids.get(key)
        if tag_id:
            # Find the name again for confirmation display (including potentially newly created ones)
            tag_info = next((t for t in all_tags if t.get("id") == tag_id), None)
            tag_name = (
                tag_info.get("name", "[i]Unknown Name[/i]")
                if tag_info
                else "[yellow]MISSING TAG[/yellow]"
            )
            CONSOLE.print(
                f"  [field]{desc:<45}[/field]: '[cyan]{tag_name}[/cyan]' ([magenta]{tag_id}[/magenta])"
            )
        else:
            CONSOLE.print(
                f"  [field]{desc:<45}[/field]: [bold red]** Not Set **[/bold red]"
            )
            all_selections_valid = False  # Mark if any tag is missing
    CONSOLE.print("=" * 60)

    if not all_selections_valid:
        CONSOLE.print(
            "[bold red]Warning:[/bold red] Not all required tags have been assigned. Saving is incomplete."
        )
        if not Confirm.ask(
            "Some tags are missing. Continue saving the assigned tags anyway?",
            default=False,
        ):
            CONSOLE.print("Operation cancelled. No changes saved.")
            return
        else:
            CONSOLE.print("Proceeding to save assigned tags...")

    if not Confirm.ask(
        f"\nSave these selections to [cyan]'{os.path.basename(dotenv_path)}'[/cyan]?",
        default=True,
    ):
        CONSOLE.print("Operation cancelled. No changes saved.")
        return

    # --- 6. Write to .env file ---
    try:
        CONSOLE.print(f"Updating '[cyan]{dotenv_path}[/cyan]'...")
        num_updated = 0
        for key, value in selected_ids.items():
            # set_key returns True if value was changed, False otherwise (or raises error)
            updated = set_key(dotenv_path, key, value, quote_mode="always")
            if updated:
                num_updated += 1  # Count only actual changes/additions
        CONSOLE.print(
            f"[bold green]:heavy_check_mark: Successfully set/updated {len(selected_ids)} key(s) in [cyan]{os.path.basename(dotenv_path)}[/cyan]! ({num_updated} actually changed)[/]"
        )
        CONSOLE.print("Restart the application if needed for changes to take effect.")
    except IOError as e:
        CONSOLE.print(
            f"[bold red]Error writing to .env file at '{dotenv_path}': {e}[/]"
        )
    except Exception as e:  # Catch potential errors from set_key itself
        CONSOLE.print(f"[bold red]Unexpected error saving to .env file: {e}[/]")


# --- End of interactive_tag_setup ---


# MARK: - EXAMPLE CALLER FUNCTION
def configure_tags() -> None:
    """
    Runs the interactive tag setup process.

    Initializes the HabiticaAPI client (assuming configuration allows it)
    and then calls `interactive_tag_setup`. Handles potential initialization errors.
    This function is suitable for calling from a CLI command.

    Returns:
        None
    """
    CONSOLE.print("[bold blue]Starting interactive tag configuration...[/]")
    try:
        # Need an API client instance first. This assumes the basic
        # USER_ID and API_TOKEN might already be in .env or config.
        api = HabiticaAPI()
    except ValueError as e:
        CONSOLE.print(f"[bold red]API Initialization Error:[/bold red] {e}")
        CONSOLE.print("Cannot proceed without valid API credentials.")
        return
    except Exception as e:
        CONSOLE.print(f"[bold red]Unexpected Error initializing API: {e}[/]")
        return

    # Run the interactive setup using the initialized API client
    try:
        interactive_tag_setup(api)
    except Exception as e:
        # Catch errors from the setup process itself
        CONSOLE.print(f"[bold red]Error during tag configuration: {e}[/]")

    CONSOLE.print("[bold blue]Tag configuration finished.[/]")


# Example of direct execution (less common for setup utilities)
# if __name__ == "__main__":
#     configure_tags()
