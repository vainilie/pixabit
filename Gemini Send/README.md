--- START OF FILE Readme.md ---

# Pixabit - Habitica CLI/TUI Assistant

A personal command-line interface (CLI) tool written in Python to interact with the Habitica API (v3) for managing tasks, tags, challenges, stats, and performing various account actions.

**🚨 Current Status: Migrating from Rich CLI to Textual TUI 🚨**

This project is undergoing a major refactoring from a synchronous, Rich-based command-line application to an asynchronous, Textual-based Terminal User Interface (TUI). The core data handling and API interaction layer have been refactored to support this.

# Features (Post-Refactor & Target TUI Features)

- **Asynchronous Core:** Uses `httpx` for non-blocking API calls and `asyncio` for managing background tasks.
- **Central Data Store:** A `PixabitDataStore` manages application state, orchestrates API calls, processes data using models, and notifies the UI of updates.
- **Data Models:** Clear Python classes (`models/`) represent Habitica entities (User, Task, Challenge, Tag, etc.).
- **Lazy Content Caching:** Game content (`content.json`) is cached locally and loaded on demand (`GameContent` manager).
- **TUI Interface (In Progress):** A Textual-based interface providing interactive views for:
  - User Stats Dashboard
  - Task Lists (Habits, Dailies, Todos, Rewards) with filtering and actions (scoring, etc.)
  - Challenge Lists with actions (leaving, etc.)
  - Tag Lists with management actions
  - Navigation via menus/keybindings.
- **Tag Management (via DataStore):**
  - Display all/unused tags.
  - Delete unused tags globally (with confirmation).
  - _Conditional Syncing (based on `.env` config):_ Challenge vs. personal tags, poison status tags, attribute tags. (Logic moved to `DataStore`).
- **Challenge Management (via DataStore):**
  - Leave joined challenges (with task handling options).
  - _(Planned)_ Backup/Restore challenges.
- **Task Management (via DataStore):**
  - Handle broken tasks (viewing, unlinking).
  - _(Planned)_ Replicate setup between challenges.
  - _(Planned)_ Full Task CRUD operations.
  - _(Planned)_ Checklist management.
- **User Actions (via DataStore):**
  - Toggle sleep status.
  - _(Planned)_ Set Custom Day Start.
- **Data Export (via Sync Helpers):**
  - Save raw user data, raw tasks, processed tasks, tags to JSON. (Can be triggered from TUI via `run_in_thread`).
- **Configuration:**
  - Mandatory credentials setup via `.env` (`config_auth.py`).
  - Optional Tag IDs setup via interactive script (`config_tags.py`) or TUI action.

# Requirements

- Python 3.10+
- Libraries listed in `pyproject.toml` (or `requirements.txt`). Key dependencies:
  - `textual`
  - `httpx`
  - `python-dotenv`
  - `python-dateutil`
  - `tzlocal`
  - `emoji-data-python`
  - `pathvalidate`
  - _(Optional for specific features)_ `art`

# Installation & Setup

1.  **Clone Repository:**
    ```bash
    git clone <your-repository-url>
    cd pixabit
    ```
2.  **Create & Activate Virtual Environment:** (Recommended)
    ```bash
    python -m venv .venv
    # Windows: .\.venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    # If using pyproject.toml with Poetry:
    # poetry install
    # Or using pip:
    pip install -r requirements.txt # Or pip install .
    ```
4.  **Initial Configuration (Mandatory Credentials):**

    - Run the application once. It will detect if `.env` is missing or invalid.
      ```bash
      python -m pixabit.tui.app # Example TUI entry point
      ```
    - Follow the prompts (**run `config_auth.py` logic**) to create/update `.env` with your **Habitica User ID** and **API Token**.
    - Alternatively, manually create a `.env` file in the project root with:
      ```dotenv
      HABITICA_USER_ID="YOUR_USER_ID_HERE"
      HABITICA_API_TOKEN="YOUR_API_TOKEN_HERE"
      ```
    - **Security:** Ensure `.env` is added to your `.gitignore` file!

5.  **Configure Optional Tags (Recommended):**
    - Run the interactive tag setup script (if kept separate):
      ```bash
      python -m pixabit.cli.config_tags # Example script entry point
      ```
    - _(Or implement this as a TUI action)_
    - This fetches existing tags and guides you through assigning them to roles (Challenge Tag, Strength Tag, etc.), saving selections to `.env`.

# Usage (TUI)

1.  Ensure your virtual environment is active.
2.  Run the main TUI application script from the project root directory:
    ```bash
    python -m pixabit.tui.app # Adjust entry point as needed
    ```
3.  Use the key bindings (shown in the footer) or UI elements (menus, lists) to navigate and interact.

# `.env` Configuration Variables

- `HABITICA_USER_ID` **(Mandatory)**: Your Habitica User ID (from Settings -> API).
- `HABITICA_API_TOKEN` **(Mandatory)**: Your Habitica API Token (from Settings -> API).
- `CHALLENGE_TAG_ID` (Optional): Tag ID used for challenge tasks.
- `PERSONAL_TAG_ID` (Optional): Tag ID used for non-challenge tasks.
- `PSN_TAG_ID` (Optional): Tag ID for "Poisoned" status.
- `NOT_PSN_TAG_ID` (Optional): Tag ID for "Not Poisoned" status.
- `NO_ATTR_TAG_ID` (Optional): Tag ID for tasks with no specific attribute.
- `ATTR_TAG_STR_ID` (Optional): Tag ID representing the Strength attribute.
- `ATTR_TAG_INT_ID` (Optional): Tag ID representing the Intelligence attribute.
- `ATTR_TAG_CON_ID` (Optional): Tag ID representing the Constitution attribute.
- `ATTR_TAG_PER_ID` (Optional): Tag ID representing the Perception attribute.
- `LEGACY_TAG_ID` (Optional): Tag ID for legacy tasks (if used).

# Pixabit Textual TUI TODO List

_(See `Migration.md` for the detailed, up-to-date TODO list reflecting the TUI migration progress.)_

# License

_(Choose a license - e.g., MIT License)_

--- END OF FILE Readme.md ---
