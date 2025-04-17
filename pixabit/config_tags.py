# pixabit/config_tags.py

# MARK: - MODULE DOCSTRING
"""Provides functionality for interactively setting up OPTIONAL Tag IDs in the .env file.

Fetches existing tags, displays them, groups configuration by feature, and allows
users to select, create, keep existing, or skip/unset tags for predefined roles.
Saves changes back to the .env file using python-dotenv utilities.
"""


# MARK: - IMPORTS
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

# Added set
import requests

# For API exceptions
# Use specific dotenv functions
from dotenv import find_dotenv, get_key, set_key, unset_key

# Local Imports
from .api import HabiticaAPI

# Use themed display components
from .utils.display import (
    Confirm,
    Prompt,
    Rule,
    Table,
    box,
    console,
    # Added Rule
)

# MARK: - CONSTANTS

# Group tag configurations logically for prompting
TAG_CONFIG_GROUPS: Dict[str, Dict[str, str]] = {
    "Challenge/Personal": {
        "Challenge Tag (for challenge tasks)": "CHALLENGE_TAG_ID",
        "Personal Tag (for non-challenge tasks)": "PERSONAL_TAG_ID",
    },
    "Poison Status": {
        "Poisoned Tag (e.g., for poison challenge)": "PSN_TAG_ID",
        "Not Poisoned Tag (default status)": "NOT_PSN_TAG_ID",
    },
    "Attributes": {
        "No Attribute Tag (tasks w/o STR/INT/...)": "NO_ATTR_TAG_ID",
        "Strength Attribute Tag": "ATTR_TAG_STR_ID",
        "Intelligence Attribute Tag": "ATTR_TAG_INT_ID",
        "Constitution Attribute Tag": "ATTR_TAG_CON_ID",
        "Perception Attribute Tag": "ATTR_TAG_PER_ID",
    },
    # Add other logical groups here if needed
}


# Flattened map for easier lookup later
ALL_TAG_CONFIG_KEYS: Dict[str, str] = {
    desc: key for group in TAG_CONFIG_GROUPS.values() for desc, key in group.items()
}


# MARK: - CORE FUNCTION


# & - def interactive_tag_setup(api_client: HabiticaAPI, dotenv_path: Union[str, Path]) -> None:
def interactive_tag_setup(api_client: HabiticaAPI, dotenv_path: Union[str, Path]) -> None:
    """Interactively configures OPTIONAL tag IDs in the .env file, grouped by feature.

    Args:
        api_client: Authenticated HabiticaAPI client.
        dotenv_path: Path to the .env file.
    """
    console.print(
        "\n--- Interactive Optional Tag Configuration ---", style="highlight", justify="center"
    )
    console.print(
        "Configure Tag IDs for optional features. Skip groups or individual tags if unused."
    )
    console.print(f"Using configuration file: [file]'{dotenv_path}'[/]", style="info")

    dotenv_path_str = str(dotenv_path)
    # Ensure string for dotenv functions

    # --- Step 1: Fetch existing tags ---
    all_tags: List[Dict[str, Any]] = []
    try:
        console.print("⏳ Fetching tags from Habitica...", style="info")
        fetched_tags = api_client.get_tags()
        if not isinstance(fetched_tags, list):
            raise TypeError(f"Expected list of tags, got {type(fetched_tags)}")
        all_tags = fetched_tags
        all_tags.sort(key=lambda t: t.get("name", "").lower())
        console.print(f"✅ Found {len(all_tags)} existing tags.", style="success")
    except (requests.exceptions.RequestException, TypeError, Exception) as e:
        console.print(f"❌ Error fetching tags: {e}", style="error")
        console.print("Cannot proceed without tag list.")
        return

    # --- Step 2: Prepare and Display Tags ---
    valid_tags_for_selection = [tag for tag in all_tags if isinstance(tag, dict) and tag.get("id")]
    num_tags_selectable = len(valid_tags_for_selection)

    table = Table(
        title="Available Habitica Tags",
        show_lines=True,
        box=box.ROUNDED,
        border_style="rp_overlay",
    )
    table.add_column("Num", style="subtle", width=4, justify="right")
    table.add_column("Name", style="rp_foam", max_width=40)
    table.add_column("ID", style="rp_rose", no_wrap=True)

    if not valid_tags_for_selection:
        table.add_row("...", "[dim]No existing selectable tags found[/dim]", "...")
    else:
        for i, tag in enumerate(valid_tags_for_selection):
            table.add_row(str(i + 1), tag.get("name", "[dim]N/A[/dim]"), tag.get("id"))
    console.print(table)
    if not valid_tags_for_selection:
        console.print(
            "⚠️ You will need to use 'Create New' or 'Skip' for all tags.", style="warning"
        )

    # --- Step 3: Prompt User for Each Tag GROUP ---
    selected_ids: Dict[str, Optional[str]] = {}
    # Store {env_key: tag_id or None}
    keys_to_unset: Set[str] = set()
    # Track keys currently in .env that user skips

    for group_name, tags_in_group in TAG_CONFIG_GROUPS.items():
        console.print(Rule(f"[highlight]Configure {group_name} Tags[/]", style="rp_overlay"))

        # Ask to configure this group
        if not Confirm.ask(f"set up tags for '{group_name}' feature?", default=True):
            console.print(f"⏭️ Skipping configuration for {group_name} tags.", style="info")

            # Mark existing keys in this group for potential removal
            for env_key in tags_in_group.values():
                if get_key(dotenv_path_str, env_key) is not None:
                    keys_to_unset.add(env_key)
                selected_ids[env_key] = None
            # Mark as not configured in this run
            continue
        # Skip to next group

        # Configure tags within this group
        for tag_description, env_key in tags_in_group.items():
            console.print(
                f"\n-- Tag: [highlight]{tag_description}[/] ([dim]Variable: {env_key}[/]) --"
            )
            current_value_id = get_key(dotenv_path_str, env_key)
            current_display_name = "[dim i]Not Set[/dim i]"
            current_tag_name = None
            # Store name if found
            if current_value_id:
                current_tag = next(
                    (
                        t
                        for t in all_tags
                        if isinstance(t, dict) and t.get("id") == current_value_id
                    ),
                    None,
                )
                if current_tag:
                    current_tag_name = current_tag.get("name", "[dim]Unknown[/dim]")
                    current_display_name = (
                        f" '[rp_foam]{current_tag_name}[/]' ([rp_rose]{current_value_id}[/])"
                    )
                else:
                    current_display_name = f" ID [rp_rose]{current_value_id}[/] ([warning]Tag no longer exists![/warning])"

            tag_configured_successfully = False
            while not tag_configured_successfully:
                try:

                    # --- Build Prompt ---
                    prompt_options_list = []
                    valid_choices_numeric = []
                    if num_tags_selectable > 0:
                        prompt_options_list.append(
                            f"[bold]1[/]-[bold]{num_tags_selectable}[/] Select"
                        )
                        valid_choices_numeric.extend(range(1, num_tags_selectable + 1))
                    prompt_options_list.append("[bold]0[/] Create")
                    valid_choices_numeric.append(0)
                    if current_value_id:
                        prompt_options_list.append("[bold]-1[/] Keep Current")
                        valid_choices_numeric.append(-1)
                    prompt_options_list.append("[bold]S[/] Skip/Unset")
                    valid_choices_str = [str(n) for n in valid_choices_numeric] + ["s", "S"]

                    prompt_text = (
                        f"Action for '[highlight]{tag_description}[/]':\n"
                        f"[dim]Options: {', '.join(prompt_options_list)} | Current: {current_display_name}[/dim]\n"
                        f"Enter choice: "
                    )

                    choice_str = Prompt.ask(
                        prompt_text, choices=valid_choices_str, show_choices=False
                    ).strip()

                    # --- Handle Choice ---
                    if choice_str.lower() == "s":
                        selected_ids[env_key] = None
                        # Explicitly mark as not set
                        if current_value_id:
                            keys_to_unset.add(env_key)
                        # Mark for removal
                        console.print(f"  ⏭️ Skipping/Unsetting '{tag_description}'.", style="info")
                        tag_configured_successfully = True
                    elif choice_str == "-1" and current_value_id:
                        selected_ids[env_key] = current_value_id
                        # Keep existing value
                        if env_key in keys_to_unset:
                            keys_to_unset.remove(env_key)
                        # Don't unset if kept
                        console.print(
                            f"  ➡️ Keeping current value {current_display_name}.", style="info"
                        )
                        tag_configured_successfully = True
                    elif choice_str.isdigit() or (
                        choice_str.startswith("-") and choice_str[1:].isdigit()
                    ):
                        choice = int(choice_str)
                        if 1 <= choice <= num_tags_selectable:
                            selected_tag = valid_tags_for_selection[choice - 1]
                            tag_id = selected_tag.get("id")
                            tag_name = selected_tag.get("name", "[dim]N/A[/dim]")
                            if tag_id:
                                selected_ids[env_key] = tag_id
                                if env_key in keys_to_unset:
                                    keys_to_unset.remove(env_key)
                                console.print(
                                    f"  ✅ Selected '[rp_foam]{tag_name}[/]' ([rp_rose]{tag_id}[/]).",
                                    style="success",
                                )
                                tag_configured_successfully = True
                            else:
                                console.print(
                                    "❌ Internal Error: Selected tag missing ID.", style="error"
                                )
                        elif choice == 0:
                            # Create New Tag
                            default_name = (
                                tag_description.split("(")[0]
                                .strip()
                                .replace(" ", "_")
                                .replace("/", "-")
                            )
                            new_name = Prompt.ask(
                                f"Enter name for new '{tag_description}' tag:",
                                default=default_name,
                            ).strip()
                            if not new_name:
                                console.print("⚠️ Creation cancelled (no name).", style="warning")
                                continue
                            # Re-prompt for this tag
                            if Confirm.ask(
                                f"Create new Habitica tag named '[rp_foam]{new_name}[/]'?"
                            ):
                                try:
                                    console.print(
                                        f"  ⏳ Creating tag '[rp_foam]{new_name}[/]' via API...",
                                        style="info",
                                    )
                                    created_tag = api_client.create_tag(new_name)
                                    # Returns dict or None
                                    if (
                                        created_tag
                                        and isinstance(created_tag, dict)
                                        and created_tag.get("id")
                                    ):
                                        new_id = created_tag["id"]
                                        new_name_api = created_tag.get("name", new_name)
                                        console.print(
                                            f"  ✅ Created '[rp_foam]{new_name_api}[/]' ID: [rp_rose]{new_id}[/]",
                                            style="success",
                                        )
                                        selected_ids[env_key] = new_id

                                        # Add to lists for potential use later in this run
                                        all_tags.append(created_tag)
                                        valid_tags_for_selection.append(created_tag)
                                        num_tags_selectable = len(valid_tags_for_selection)
                                        if env_key in keys_to_unset:
                                            keys_to_unset.remove(env_key)
                                        tag_configured_successfully = True
                                    else:
                                        console.print(
                                            f"❌ API Error: Failed to create tag '{new_name}' or invalid response.",
                                            style="error",
                                        )
                                except (
                                    requests.exceptions.RequestException,
                                    Exception,
                                ) as create_err:
                                    console.print(
                                        f"❌ Error creating tag '{new_name}': {create_err}",
                                        style="error",
                                    )
                            else:
                                console.print("  Creation cancelled.", style="info")
                        else:
                            console.print("❌ Invalid number choice.", style="error")
                    else:
                        console.print(
                            "❌ Invalid input. Please enter a valid number or 'S'.", style="error"
                        )

                except (ValueError, TypeError):
                    console.print("❌ Invalid input. Please enter a number or 'S'.", style="error")
                except Exception as e:
                    # Catch unexpected errors during prompt/handling
                    console.print(
                        f"❌ Unexpected error configuring '{tag_description}': {e}", style="error"
                    )
                    console.print_exception(show_locals=False)

                    # Decide whether to break or continue loop on unexpected error
                    break
    # Break inner loop on unexpected error

    # --- End of loop for tags within group ---

    # --- End of loop for groups ---

    # --- Step 4. Confirm Selections Before Saving ---
    console.print(Rule("[highlight]Review Final Tag Selections[/]", style="rp_overlay"))

    # active_selections = {k: v for k, v in selected_ids.items() if v is not None}
    review_table = Table(
        show_header=True,
        header_style="keyword",
        show_lines=True,
        box=box.ROUNDED,
        border_style="rp_surface",
    )
    review_table.add_column("Configuration Role", style="info", min_width=40)
    review_table.add_column("Selected Tag Name", style="rp_text")
    review_table.add_column("Selected Tag ID / Status", style="info")

    for desc, key in ALL_TAG_CONFIG_KEYS.items():
        tag_id = selected_ids.get(key)
        # Could be None if skipped group or individual tag
        if tag_id is not None:
            # Value was set or kept
            tag_info = next(
                (t for t in all_tags if isinstance(t, dict) and t.get("id") == tag_id), None
            )
            tag_name = (
                f"'[rp_foam]{tag_info.get('name', '[dim]Unknown[/dim]')}[/]'"
                if tag_info
                else "[warning]MISSING TAG[/warning]"
            )
            tag_id_display = f"[rp_rose]{tag_id}[/]"
            review_table.add_row(desc, tag_name, tag_id_display)
        elif key in keys_to_unset:
            # Value existed but was explicitly unset
            review_table.add_row(desc, "[dim i]Will be Unset/Removed[/dim i]", "[dim]---[/dim]")
        else:
            # Value was not set and didn't exist before
            review_table.add_row(desc, "[dim i]Not Set[/dim i]", "[dim]---[/dim]")

    console.print(review_table)
    if keys_to_unset:
        console.print(
            f"⚠️ [warning]Will remove {len(keys_to_unset)} existing setting(s) marked as 'Unset'.[/warning]"
        )
    console.print(Rule(style="rp_overlay"))

    # --- Step 5. Save to .env File ---
    if not Confirm.ask(
        f"\n💾 Apply these changes to [file]'{os.path.basename(dotenv_path_str)}'[/]?",
        default=True,
    ):
        console.print("🚫 Operation cancelled. No changes saved.", style="info")
        return

    try:
        console.print(f"⏳ Updating '[file]{dotenv_path_str}[/]'...", style="info")
        num_set, num_unset_actual = 0, 0

        # set new/kept values (only if not None)
        for key, value in selected_ids.items():
            if value is not None:
                if set_key(dotenv_path_str, key, value, quote_mode="always"):
                    num_set += 1
        # Count if set_key reports change or addition

        # Unset skipped values that previously existed
        for key in keys_to_unset:
            if unset_key(dotenv_path_str, key):
                num_unset_actual += 1
        # Count if unset_key reports success

        console.print(
            f"✅ Successfully updated optional tag configurations: "
            f"{num_set} set/updated, {num_unset_actual} unset/removed "
            f"in [file]{os.path.basename(dotenv_path_str)}[/]!",
            style="success",
        )
        console.print(
            "ℹ️ Restart the application if running for changes to take effect.", style="info"
        )

    except OSError as e:
        console.print(f"❌ Error writing to .env file '{dotenv_path_str}': {e}", style="error")
    except Exception as e:
        console.print(f"❌ Unexpected error saving to .env file: {e}", style="error")


# MARK: - CALLER FUNCTION (for CLI integration)


# & - def configure_tags() -> None:
def configure_tags() -> None:
    """Wrapper to initialize API client and run the interactive tag setup."""
    console.print("\n🚀 Starting interactive optional tag configuration...", style="info")
    dotenv_path_str = find_dotenv(raise_error_if_not_found=False, usecwd=True)
    if not dotenv_path_str:

        # Attempt to find/create it relative to this file's project structure
        try:
            project_root = Path(__file__).resolve().parent.parent
            dotenv_path_candidate = project_root / ".env"
            if not dotenv_path_candidate.exists():

                # If it truly doesn't exist, user needs to run main setup first
                console.print(
                    f"❌ '.env' file not found at expected location: [file]{dotenv_path_candidate}[/].",
                    style="error",
                )
                console.print(
                    "   Please run the main application first to set up mandatory credentials."
                )
                return
            dotenv_path_str = str(dotenv_path_candidate)
        except Exception as e:
            console.print(f"❌ Error determining .env path: {e}", style="error")
            return

    api: Optional[HabiticaAPI] = None
    try:
        api = HabiticaAPI()
        console.print("🔑 Habitica API client initialized successfully.", style="success")
    except ValueError as e:
        console.print(f"❌ API Initialization Error: {e}", style="error")
        console.print("   Cannot configure tags without valid API credentials in .env.")
        return
    except Exception as e:
        console.print(f"❌ Unexpected Error initializing API: {e}", style="error")
        return

    if api and dotenv_path_str:
        try:
            interactive_tag_setup(api, dotenv_path_str)
        except Exception as e:
            console.print(f"\n❌ Error during interactive tag configuration: {e}", style="error")
            console.print_exception(show_locals=False)
    # Show traceback for setup errors
    else:
        console.print("❌ Could not proceed: Missing API client or .env path.", style="error")

    console.print("\n🏁 Optional Tag configuration process finished.", style="info")


# --- End of file ---
