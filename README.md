# Pixabit - Habitica CLI Assistant

A personal command-line interface (CLI) tool written in Python to interact with the Habitica API (v3) for managing tasks, tags, challenges, stats, and performing various account actions. Uses the Rich library for enhanced terminal output.

#

# Features (Implemented/Refined)

- **Data Refresh & Display:** Fetches and displays user stats (Dashboard), tags (all/unused), and broken tasks. Optimized data fetching via central `refresh_data` passing data down to components. Caches game content data (`content_cache.json`).
- **Tag Management:**
  - Interactively configure optional tags (`Configure Special Tags` menu option).
  - Display all tags and unused tags.
  - Interactively delete unused tags globally (requires confirmation).
  - Interactively add/replace tags on tasks based on other existing tags.
  - _Optional Feature Syncing (Conditional based on `.env` config):_
    - Sync challenge vs. personal tags.
    - Ensure poison status tags (poisoned/not poisoned).
    - Sync attribute tags (STR/INT/CON/PER/None) with task's attribute field.
- **Challenge Management:**
  - Backup challenges (including associated, cleaned tasks) to individual JSON files.
  - Leave a joined challenge (prompts for task handling, updates local cache).
- **Task Management:**
  - Handle broken tasks: View tasks grouped by broken challenge, unlink individually or in bulk per challenge (with keep/remove option).
  - Replicate setup (attributes, tags, optionally position) from an old/broken challenge's tasks to a new challenge's tasks via fuzzy text matching.
- **User Actions:**
  - Toggle sleep status (Inn/Tavern).
- **Data Export:**
  - Save raw user data (`/user` endpoint).
  - Save raw tasks (`/tasks/user` endpoint, with emoji processing).
  - Save processed tasks dictionary (from `TaskProcessor`).
  - Save all tags (categorized by challenge/personal).
- **Configuration:**
  - Interactive setup for mandatory credentials (`.env` file creation/check).
  - Interactive setup for optional Tag IDs.
- **UI:**
  - Rich-based themed console output (using Catppuccin/Rosé Pine inspired theme defined in `styles` file).
  - Progress bars for lengthy operations (refresh, batch API calls).
  - Clear menus, prompts, and confirmations.

#

# Requirements

- Python 3.9+
- Libraries listed in `requirements.txt`. Key dependencies:
  - `requests`
  - `rich`
  - `python-dotenv`
  - `python-dateutil`
  - `tzlocal`
  - `emoji-data-python`
  - `pathvalidate`
  - `timeago`
  - `art` (Optional, for potential future ASCII art headers)

#

# Installation & Setup

1.  **Clone Repository:**
    ```bash
    git clone <your-repository-url>
    cd pixabit
    ```
2.  **Create & Activate Virtual Environment:**
    ```bash
    python -m venv .venv
    ```

# Windows:

# .venv\Scripts\activate

# macOS/Linux:

# source .venv/bin/activate

    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Initial Configuration (Mandatory Credentials):**
    - Run the application once. It will detect if `.env` is missing.
      ```bash
      python main.py
      ```

# Or however you plan to run the app

      ```
    - Follow the prompts to interactively create the `.env` file and enter your **Habitica User ID** and **API Token**.
    - Alternatively, manually create a `.env` file in the project root with:
      ```dotenv
      HABITICA_USER_ID="YOUR_USER_ID_HERE"
      HABITICA_API_TOKEN="YOUR_API_TOKEN_HERE"
      ```
    - **Security:** Ensure `.env` is added to your `.gitignore` file!

5.  **Configure Optional Tags (Recommended):**
    - Run the interactive tag setup via the application menu:
      - Start the app: `python main.py`
      - Navigate to: `Application` -> `Configure Special Tags`
    - This will fetch your existing Habitica tags and guide you through assigning them to roles like "Challenge Tag", "Strength Attribute Tag", etc., saving the selections to your `.env` file. You can skip features you don't use.

#

# Usage

1.  Ensure your virtual environment is active (`source .venv/bin/activate` or equivalent).
2.  Run the main application script from the project root directory:
    ```bash
    python main.py
    ```
    _(Replace `main.py` with your actual entry point script name if different)._
3.  Use the number keys to navigate the menus and follow the on-screen prompts.

#

# `.env` Configuration Variables

- `HABITICA_USER_ID` **(Mandatory)**: Your Habitica User ID (from Settings -> API).
- `HABITICA_API_TOKEN` **(Mandatory)**: Your Habitica API Token (from Settings -> API).
- `CHALLENGE_TAG_ID` (Optional): Tag ID used by `TagManager` to identify challenge tasks.
- `PERSONAL_TAG_ID` (Optional): Tag ID used by `TagManager` for non-challenge tasks.
- `PSN_TAG_ID` (Optional): Tag ID for "Poisoned" status.
- `NOT_PSN_TAG_ID` (Optional): Tag ID for "Not Poisoned" status.
- `NO_ATTR_TAG_ID` (Optional): Tag ID for tasks with no specific attribute or conflicting attribute tags.
- `ATTR_TAG_STR_ID` (Optional): Tag ID representing the Strength attribute.
- `ATTR_TAG_INT_ID` (Optional): Tag ID representing the Intelligence attribute.
- `ATTR_TAG_CON_ID` (Optional): Tag ID representing the Constitution attribute.
- `ATTR_TAG_PER_ID` (Optional): Tag ID representing the Perception attribute.

_(Note: Optional Tag IDs are typically set via the interactive "Configure Special Tags" menu.)_

#

# License

_(Choose a license - e.g., MIT License, Apache 2.0, or specify if it's for personal use only)_

Example: MIT License

---

# Consolidated TODO List for Pixabit (Updated Based on Refinement)

_(Reflects current state after implementing code structure)_

#

# Core API & Processing

- [✅ Done] Optimize `refresh_data` to fetch data centrally and pass down.
- [✅ Done] Implement content caching (`_get_content_cached`).
- [✅ Done] Implement challenge caching (`_fetch_challenges_cached`).
- [✅ Done] Calculate potential daily damage in `TaskProcessor`.
- [✅ Done] Calculate effective CON in `TaskProcessor`.
- [✅ Done] Implement `get_user_stats` using processed/fetched data.

#

# Tag Management (`TagManager`)

- [✅ Done] Implement `sync_challenge_personal_tags` (conditional on config).
- [✅ Done] Implement `ensure_poison_status_tags` (conditional on config).
- [✅ Done] Implement `sync_attributes_to_tags` (conditional on config).
- [✅ Done] Implement `find_unused_tags`.
- [✅ Done] Implement `delete_unused_tags_interactive` (uses hypothetical `delete_tag_global` action).
- [✅ Done] Implement `add_or_replace_tag_based_on_other`.
- [✅ Done] Add logging for configured tag features in `__init__`.

#

# Challenge Management (`ChallengeBackupper`, `CliApp`)

- [✅ Done] Implement challenge backup (`ChallengeBackupper`, `CliApp` action).
- [✅ Done] Implement "Leave Challenge" feature (`CliApp._leave_challenge_action`, uses `api.leave_challenge`, updates cache).
- [⏳ To Do] **Implement Challenge Import:** Create `ChallengeImporter` class? Needs logic to parse backup JSON, call `api.create_challenge`, then iterate through `_tasks` in JSON and call `api.create_task` (potentially linking them via challenge parameters if API supports). Add CLI action.
- [⏳ To Do] **List Joined Challenges:** Add CLI action. Fetch using `api.get_challenges(member_only=True)` (can use cache `self.all_challenges_cache`), filter out _owned_ challenges (check `challenge['leader']['_id'] == self.user_id`), display results in a `rich.Table`.

#

# Task Management (`CliApp`, `api.py`)

- [✅ Done] Implement "Handle Broken Tasks" (bulk/individual unlink) (`CliApp._handle_broken_tasks_action`).
- [✅ Done] Implement "Replicate Monthly Setup" (`CliApp._replicate_monthly_setup_action`).
- [⏳ To Do] **Implement Task CRUD via CLI:** (Major Feature)
  - **Display Task Details:** Add action to select task (maybe from filtered list), fetch full task data `api.get_task(task_id)` (needs adding to `api.py` -> `GET /tasks/{taskId}`), display nicely.
  - **Score Task:** Add action, prompt task selection, prompt direction ('up'/'down'), call `api.score_task`.
  - **Edit Task:** Add action, prompt task selection, prompt field(s) to edit (text, notes, priority, due date?), call `api.update_task`.
  - **Create Task:** Add action, prompt for text, type, notes, priority, etc., call `api.create_task`.
  - **Delete Task:** Add action, prompt task selection, confirm, call `api.delete_task`.
- [⏳ To Do] **Manage Checklist Items via CLI:** Add actions within Task viewing/editing:
  - Add item: Prompt text, call `api.add_checklist_item`.
  - Score item (toggle): Prompt item selection, call `api.score_checklist_item`.
  - Edit item text: Prompt item selection, prompt new text, call `api.update_checklist_item`.
  - Delete item: Prompt item selection, call `api.delete_checklist_item`.
- [⏳ To Do] **Implement "Pin/Unpin Task" feature:** Add CLI action. List tasks (e.g., Todos), prompt selection, call `api.move_task_to_position(task_id, 0)` to pin (move to top). Unpin might move to bottom (`-1`) or require more complex position tracking.

#

# User Actions (`CliApp`, `api.py`)

- [✅ Done] Implement "Toggle Sleep Status".
- [⏳ To Do] **Set Custom Day Start:** Add CLI action. Prompt for hour (0-23), call `api.set_custom_day_start`.

#

# Inbox Features (`CliApp`, `api.py`)

- [⏳ To Do] **Display Inbox:** Add CLI action. Call `api.get_inbox_messages` (handle pagination - maybe show first page or prompt for page?), display messages.
- [⏳ To Do] **Send Private Message:** Add CLI action. Prompt recipient username/ID, prompt message text, call `POST /members/send-private-message` (needs adding to `api.py`).

#

# Banking Simulation (Requires Config)

- [⏳ To Do] **Implement Deposit/Withdraw:** Add CLI actions. Requires `DEPOSIT_REWARD_ID` and `WITHDRAW_HABIT_ID` in `.env`. Prompt for amount/times, call `api.score_task` repeatedly for the appropriate ID.

#

# Export Features (`exports.py`, `CliApp`)

- [✅ Done] Implement exports for raw user data, raw tasks, processed tasks, categorized tags.
- [⏳ To Do] **Review/Refine Tasker/KLWP Export:** Evaluate if `tasks_processed.json` is suitable. If not, create a new function in `exports.py` that transforms `self.processed_tasks` into the desired flat list/JSON structure for Tasker/KLWP. Add a corresponding `CliApp` action.

#

# Project & Code Quality

- [✅ Done] Use `Path` objects for file paths.
- [✅ Done] Standardize docstrings and type hinting.
- [✅ Done] Integrate themed Rich components (`display.py`).
- [✅ Done] Centralize JSON saving (`save_json.py`).
- [✅ Done] Improve error handling and user feedback.
- [✅ Done] Add comment anchors (`

# MARK:`, `

# & -`) for navigation.

- [⏳ To Do] **Add Unit/Integration Tests:** Crucial for reliability, especially for API interactions and data processing logic.
- [⏳ To Do] **Refactor Large Methods:** Some methods in `CliApp` (`_replicate_monthly_setup_action`, `_handle_broken_tasks_action`) are quite long. Consider breaking them into smaller helper methods for readability and testing.
- [⏳ To Do] **Implement Debug Mode:** Add a global flag (e.g., environment variable `PIXABIT_DEBUG=true` checked in `config.py`) that enables more verbose logging (e.g., uncommenting `console.log` calls in `api.py`, potentially showing more traceback info).
