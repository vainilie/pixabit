# Pixabit - Habitica CLI Assistant

A personal command-line interface (CLI) tool written in Python to interact with the Habitica API (v3) for managing tasks, tags, challenges, stats, and performing various account actions. Uses the Rich library for enhanced terminal output.

## Features

* **Data Refresh & Display:** Fetches and displays user stats, tags (all/unused), and broken tasks.
* **Tag Management:**
    * Interactively configure special tags (.env).
    * Sync challenge/personal tags based on task association.
    * Sync attribute tags to task attributes.
    * Ensure poison status tags are present.
    * Interactively add/replace tags on tasks based on other tags.
    * List and optionally delete unused tags.
* **Challenge Management:**
    * Backup challenges (including associated tasks) to individual JSON files.
    * (TODO: Import challenges from backup JSON).
    * (TODO: List joined challenges).
    * (TODO: Leave/Abandon challenges).
* **Task Management:**
    * List tasks associated with broken challenges.
    * Unlink tasks from broken challenges (optionally keeping them).
    * (TODO: Unlink single task from challenge).
    * (TODO: Pin/Unpin tasks by moving to top).
    * (TODO: Full Task CRUD - Create, Read, Update, Delete via CLI).
    * (TODO: Score tasks up/down).
    * (TODO: Manage checklist items - add, score, edit, delete).
    * (TODO: Sort tasks by various criteria).
* **User Actions:**
    * Toggle sleep status.
    * (TODO: Set Custom Day Start).
* **Data Export:**
    * Save raw user data, raw tasks, processed tasks, or all tags to JSON.
* **Banking (Simulation):**
    * (TODO: "Deposit" gold via custom reward).
    * (TODO: "Withdraw" gold via custom habit).
* **(Other Implemented/Planned Features...)**

## Requirements

* Python 3.9+ (Recommended)
* See `requirements.txt` for specific library dependencies (install using pip). Key libraries include:
    * `requests`
    * `rich`
    * `python-dotenv`
    * `python-dateutil`
    * `pytz`
    * `timeago`
    * `art` (Optional, for header)

## Installation & Setup

1.  **Clone:** `git clone <your-repo-url>`
2.  **Navigate:** `cd pixabit`
3.  **Create Virtual Environment:** `python -m venv .venv`
4.  **Activate Environment:**
    * Windows: `.venv\Scripts\activate`
    * Linux/macOS: `source .venv/bin/activate`
5.  **Install Dependencies:** `pip install -r requirements.txt`
6.  **Configure Credentials (.env):**
    * Copy the `.env.example` file (create this!) to `.env`: `cp .env.example .env`
    * Edit the `.env` file with your actual Habitica credentials:
        * `HABITICA_USER_ID="YOUR_USER_ID_HERE"` (Find in Settings -> API)
        * `HABITICA_API_TOKEN="YOUR_API_TOKEN_HERE"` (Find in Settings -> API)
    * **Important:** Add `.env` to your `.gitignore` file to avoid committing secrets!
7.  **Configure Special Tags (.env / Interactive):**
    * You need to tell the app which of your Habitica tags correspond to specific functions (challenges, attributes, etc.).
    * You can either:
        * **Manually edit `.env`:** Add lines like `CHALLENGE_TAG_ID="your-challenge-tag-uuid"`, `PERSONAL_TAG_ID="your-personal-tag-uuid"`, etc. (List all required IDs based on `pixabit/config_utils.py`'s `TAG_CONFIG_KEYS`). Find tag IDs via API or browser dev tools.
        * **Use Interactive Setup:** Run `python main.py configure tags` (assuming you add this command). This will fetch your tags and guide you through selecting the correct one for each required role, saving the IDs to `.env`.

## Usage

1.  Ensure your virtual environment is active.
2.  Run the main application from the project root directory:
    ```bash
    python main.py
    ```
3.  Follow the interactive menu options.

*(Add sections for specific commands if you implement a Typer/Click interface later)*

## `.env` Configuration Variables

*(List the variables expected in `.env` and briefly explain their purpose)*
* `HABITICA_USER_ID`: Your Habitica User ID.
* `HABITICA_API_TOKEN`: Your Habitica API Key.
* `CHALLENGE_TAG_ID`: ID of the tag automatically applied to challenge tasks.
* `PERSONAL_TAG_ID`: ID of the tag applied to non-challenge tasks.
* `PSN_TAG_ID`: ID of the tag indicating "Poisoned" status (optional).
* `NOT_PSN_TAG_ID`: ID of the tag indicating "Not Poisoned" status (optional).
* `NO_ATTR_TAG_ID`: ID of the tag for tasks with conflicting/no attributes.
* `ATTR_TAG_STR_ID`: ID of the tag representing the Strength attribute.
* `ATTR_TAG_INT_ID`: ID of the tag representing the Intelligence attribute.
* `ATTR_TAG_CON_ID`: ID of the tag representing the Constitution attribute.
* `ATTR_TAG_PER_ID`: ID of the tag representing the Perception attribute.
* (Add `DEPOSIT_REWARD_ID`, `WITHDRAW_HABIT_ID` if Bank feature implemented)

## License

*(Optional: e.g., MIT License or "For Personal Use Only")*