# Pixabit - Habitica CLI Assistant

A personal command-line interface (CLI) tool written in Python to interact with the Habitica API (v3) for managing tasks, tags, challenges, stats, and performing various account actions. Uses the Rich library for enhanced terminal output.

## Features

- **Data Refresh & Display:** Fetches and displays user stats, tags (all/unused), and broken tasks.
- **Tag Management:**
  - Interactively configure special tags (.env).
  - Sync challenge/personal tags based on task association.
  - Sync attribute tags to task attributes.
  - Ensure poison status tags are present.
  - Interactively add/replace tags on tasks based on other tags.
  - List and optionally delete unused tags.
- **Challenge Management:**
  - Backup challenges (including associated tasks) to individual JSON files.
  - (TODO: Import challenges from backup JSON).
  - (TODO: List joined challenges).
  - (TODO: Leave/Abandon challenges).
- **Task Management:**
  - List tasks associated with broken challenges.
  - Unlink tasks from broken challenges (optionally keeping them).
  - (TODO: Unlink single task from challenge).
  - (TODO: Pin/Unpin tasks by moving to top).
  - (TODO: Full Task CRUD - Create, Read, Update, Delete via CLI).
  - (TODO: Score tasks up/down).
  - (TODO: Manage checklist items - add, score, edit, delete).
  - (TODO: Sort tasks by various criteria).
- **User Actions:**
  - Toggle sleep status.
  - (TODO: Set Custom Day Start).
- **Data Export:**
  - Save raw user data, raw tasks, processed tasks, or all tags to JSON.
- **Banking (Simulation):**
  - (TODO: "Deposit" gold via custom reward).
  - (TODO: "Withdraw" gold via custom habit).
- **(Other Implemented/Planned Features...)**

## Requirements

- Python 3.9+ (Recommended)
- See `requirements.txt` for specific library dependencies (install using pip). Key libraries include:
  - `requests`
  - `rich`
  - `python-dotenv`
  - `python-dateutil`
  - `pytz`
  - `timeago`
  - `art` (Optional, for header)

## Installation & Setup

1.  **Clone:** `git clone <your-repo-url>`
2.  **Navigate:** `cd pixabit`
3.  **Create Virtual Environment:** `python -m venv .venv`
4.  **Activate Environment:**
    - Windows: `.venv\Scripts\activate`
    - Linux/macOS: `source .venv/bin/activate`
5.  **Install Dependencies:** `pip install -r requirements.txt`
6.  **Configure Credentials (.env):**
    - Copy the `.env.example` file (create this!) to `.env`: `cp .env.example .env`
    - Edit the `.env` file with your actual Habitica credentials:
      - `HABITICA_USER_ID="YOUR_USER_ID_HERE"` (Find in Settings -> API)
      - `HABITICA_API_TOKEN="YOUR_API_TOKEN_HERE"` (Find in Settings -> API)
    - **Important:** Add `.env` to your `.gitignore` file to avoid committing secrets!
7.  **Configure Special Tags (.env / Interactive):**
    - You need to tell the app which of your Habitica tags correspond to specific functions (challenges, attributes, etc.).
    - You can either:
      - **Manually edit `.env`:** Add lines like `CHALLENGE_TAG_ID="your-challenge-tag-uuid"`, `PERSONAL_TAG_ID="your-personal-tag-uuid"`, etc. (List all required IDs based on `pixabit/config_utils.py`'s `TAG_CONFIG_KEYS`). Find tag IDs via API or browser dev tools.
      - **Use Interactive Setup:** Run `python main.py configure tags` (assuming you add this command). This will fetch your tags and guide you through selecting the correct one for each required role, saving the IDs to `.env`.

## Usage

1.  Ensure your virtual environment is active.
2.  Run the main application from the project root directory:
    ```bash
    python main.py
    ```
3.  Follow the interactive menu options.

_(Add sections for specific commands if you implement a Typer/Click interface later)_

## `.env` Configuration Variables

_(List the variables expected in `.env` and briefly explain their purpose)_

- `HABITICA_USER_ID`: Your Habitica User ID.
- `HABITICA_API_TOKEN`: Your Habitica API Key.
- `CHALLENGE_TAG_ID`: ID of the tag automatically applied to challenge tasks.
- `PERSONAL_TAG_ID`: ID of the tag applied to non-challenge tasks.
- `PSN_TAG_ID`: ID of the tag indicating "Poisoned" status (optional).
- `NOT_PSN_TAG_ID`: ID of the tag indicating "Not Poisoned" status (optional).
- `NO_ATTR_TAG_ID`: ID of the tag for tasks with conflicting/no attributes.
- `ATTR_TAG_STR_ID`: ID of the tag representing the Strength attribute.
- `ATTR_TAG_INT_ID`: ID of the tag representing the Intelligence attribute.
- `ATTR_TAG_CON_ID`: ID of the tag representing the Constitution attribute.
- `ATTR_TAG_PER_ID`: ID of the tag representing the Perception attribute.
- (Add `DEPOSIT_REWARD_ID`, `WITHDRAW_HABIT_ID` if Bank feature implemented)

## License

_(Optional: e.g., MIT License or "For Personal Use Only")_

---

# Consolidated TODO List for Pixabit (Updated)

## Challenge Management

- [⏳ To Do] **Implement CLI action to unlink tasks by challenge:** Prompt for `challenge_id` and `keep` ('keep-all'/'remove-all'), call `unlink_all_challenge_tasks`. [cite: 1007, 1084]
- [⏳ To Do] **Implement Challenge Import from JSON Backup files:** Read backup JSON, call `create_challenge`, then call API (likely POST `/tasks/challenge/{challengeId}`) to add tasks. [cite: 1029, 1084]
- [⏳ To Do] **Implement CLI action to list joined challenges:** Fetch using `get_challenges` (use cached `self.all_challenges_cache`), display in a table with details (Guild?, Members, Created, Updated, Prize). [cite: 1021, 1084]
- [🚧 Needs Testing] **Implement CLI action to leave/abandon selected challenge:** Display list (use cache, filter out owned), fetch tasks for selected, prompt for action (unlink keep/remove or just leave), call `leave_challenge` API method. _(Code implemented in `_leave_challenge_action`)_. [cite: 1021, 1084]

## Tag Management

- [⏳ To Do] **Implement CLI actions calling existing TagManager methods:** Add menu options in `CliApp` that call:
  - `tag_manager.sync_challenge_personal_tags(self.processed_tasks)` [cite: 1016, 1084]
  - `tag_manager.ensure_poison_status_tags(self.processed_tasks)` [cite: 1017, 1084]
  - `tag_manager.sync_attributes_to_tags(self.processed_tasks)` [cite: 1018, 1084]
  - `tag_manager.delete_unused_tags_interactive(self.all_tags, used_tag_ids)` (List & Delete Unused). [cite: 1016, 1084]
- [⏳ To Do] **Implement other Mass Tag Actions:** Create new `TagManager` methods and corresponding `CliApp` actions for flexible tagging (e.g., "add tag X to tasks with tag Y", "remove tag X based on filter Z"). [cite: 1030, 1084]
- [⏳ To Do] **Modify poison tag logic:** Update `TagManager.ensure_poison_status_tags` to check if `self.psn_tag` and `self.not_psn_tag` are configured before executing (make optional based on config). [cite: 1011, 1017, 1084]

## Task Management & Interaction

- [🚧 Needs Integration] **Implement logic to replicate tags/attributes/position:** (Complex) Add CLI action & `_execute_action` entry; handler (`_replicate_monthly_setup_action`) prompts for Old/New challenges (select Old from broken tasks data, New from active cache), fetches tasks (old from processed, new from API), fuzzy matches, replicates attributes (`set_attribute`) & tags (`add_tag`), optionally replicates position (`move_task_to_position`), optionally cleans up old challenge tasks (`unlink_all_challenge_tasks`). _(Code implemented, needs menu integration)_. [cite: 1009, 1010, 1085]
- [🚧 Needs Integration] **Implement CLI action to handle broken tasks (unlink single task):** Add CLI action & `_execute_action` entry; handler (`_handle_broken_tasks_action`) displays broken tasks grouped by challenge, offers bulk unlink per challenge (`unlink_all_challenge_tasks`) or individual unlink (`unlink_task_from_challenge`), prompts keep/remove. _(Code implemented, needs menu integration)_. [cite: 1011, 1085]
- [⏳ To Do] **Implement Task CRUD features via CLI:** (Major Feature) Requires new `CliApp` actions & UI prompts: [cite: 1012-1014, 1085]
  - Display detailed task info (fetch task by ID, show text, notes, checklist).
  - Score tasks (+/-) using `score_task`.
  - Complete/uncomplete dailies/todos (also uses `score_task`).
  - Edit tasks (text, notes, dates, etc.) using `update_task`.
  - Create tasks using `create_task`.
  - **Sub-feature:** Select Task Difficulty/Priority (`priority` field) during create/edit. [cite: 1070-1074, 1086]
  - Manage checklist items (`add_checklist_item`, `score_checklist_item`, etc.).
  - (Optional) Batch editing capabilities.
- [⏳ To Do] **Implement Task Sorting/Reordering via CLI:** Add CLI action; handler fetches tasks (`self.processed_tasks`), sorts locally (alpha, tags, due date), determines target positions, calls `move_task_to_position` repeatedly (rate limits!). Potentially save/restore original order. [cite: 1015, 1016, 1085]
- [⏳ To Do] **Implement "Pin/Unpin Task" feature:** Add CLI action; handler lists tasks, prompts for selection, calls `move_task_to_position(task_id, 0)`. [cite: 1063-1069, 1086]

## Damage / Stats / User Info

- [⏳ To Do] **Implement Damage Mitigation strategy:** Add CLI action; handler prompts for confirmation, scores down a pre-configured negative Habit task ID (`config.py`, use `score_task(id, 'down')`). Optionally check off item on dummy task/checklist (`score_checklist_item`). [cite: 1022, 1042-1048, 1087]
- [✅ Done] **Add Gems count display:** Fetched balance, calculated Gems (`balance * 4`) in `get_user_stats`, displayed in `_display_stats`. [cite: 1059-1063, 1087]

## User/App Settings

- [⏳ To Do] **Implement CLI action to set Custom Day Start (CDS):** Add CLI action; handler prompts for hour (0-23), calls `set_custom_day_start(hour)`. [cite: 1024, 1025, 1087]

## Inbox Features

- [⏳ To Do] **Implement CLI action to display Inbox messages:** Add CLI action; handler calls `get_inbox_messages` (maybe paginated), displays messages using Rich (e.g., `Panel` or `Table`). [cite: 1018, 1019, 1088]
- [⏳ To Do] **(Optional) Implement CLI action to send messages/reply:** More complex. Would need UI prompts for recipient/message, call `POST /members/send-private-message` (check `api.py` if method exists or use `post`). [cite: 1018, 1019, 1088]

## Banking Simulation

- [⏳ To Do] **Implement "Deposit Gold" CLI action:** Add CLI action; handler prompts for amount/times, calls `score_task(DEPOSIT_REWARD_ID, 'up')` repeatedly. Requires `DEPOSIT_REWARD_ID` in config. [cite: 1052-1057, 1089]
- [⏳ To Do] **Implement "Withdraw Gold" CLI action:** Add CLI action; handler prompts for amount/times, calls `score_task(WITHDRAW_HABIT_ID, 'up')` repeatedly. Requires `WITHDRAW_HABIT_ID` in config. [cite: 1052-1057, 1089]

## Export Features

- [⏳ To Do] **Review/Refine Tasker/KLWP Export:** Check if the current format saved by `save_processed_tasks_into_json` is suitable for Tasker/KLWP, or if a new export function is needed to transform `self.processed_tasks` into a specific structure. [cite: 1031-1033, 1089]

## Project Setup & Documentation

- [🚧 Likely Done] Create/Maintain `README.md`, `requirements.txt`, `.gitignore`, `.env.example`. [cite: 1090, 1091]
