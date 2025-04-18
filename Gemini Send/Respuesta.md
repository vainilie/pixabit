# **Code Review & Refactoring Summary:**

1.  **`main.py`:** Marked as legacy, formatted.
2.  **`Utils/clean_name.py`:** Typing, anchors, docstrings applied. Fixed function name typo (`replace*` -> `replace_`). Logic seems okay.
3.  **`Utils/dates.py`:** Typing, anchors, docstrings applied. Improved UTC/local conversions and error handling. `format_timedelta` logic refined.
4.  **`Utils/display.py`:** Typing, anchors, docstrings applied. Corrected theme path logic. Ensured `print` wrapper works correctly. Added dummy `text2art`. Added `ConsoleRenderable` to exports.
5.  **`Utils/generic_repr.py`:** Typing, anchors, docstrings applied. Added length limit for strings.
6.  **`Utils/save_json.py`:** Typing, anchors, docstrings applied. Added `load_json`. Improved logging messages.
7.  **`models/challenge.py`:** Typing, anchors, docstrings applied. Refined `Challenge.__init__` (leader/group parsing). Verified `ChallengeList._link_tasks`. Added `Optional` to `max_tasks` in filter.
8.  **`models/message.py`:** Typing, anchors, docstrings applied. Refined `Message.__init__` (sender logic, system msg check). Refined `_determine_conversation_id` logic (still complex, endpoint-dependent). Improved sorting/filtering in `MessageList`. Fixed placeholder `convert_timestamp_to_utc`.
9.  **`models/party.py`:** Typing, anchors, docstrings applied. Refined nested classes. Normalized `member_sort_ascending`.
10. **`models/spell.py`:** Typing, anchors, docstrings applied. Improved error handling in `SpellList._process_list`. Refined `get_available_spells` logic.
11. **`models/tag.py`:** Typing, anchors, docstrings applied. Renamed `ListTag` -> `TagList` (in comments, actual rename needed if desired). Refined `_process_single_tag` logic, moved constants. Added more filtering methods. Fixed typo `replace*illegal...` function name usage.
12. **`models/task.py`:** Typing, anchors, docstrings applied. Refined `Task.__init__`, `ChallengeData`, `ChecklistItem`. Added validation. Clarified `is_past_due`. Commented out redundant `update_from_processed`. Streamlined `TaskList.__init__` assuming TaskProcessor creates/processes objects first. Added `_assign_relative_positions`. Added `filter_by_status`.
13. **`models/user.py`:** Typing, anchors, docstrings applied. Significantly reviewed and refined `UserStats` calculations (`_get_gear_stat_bonus`, `_calculate_total_stat`, `max_hp`, `max_mp`) based on common Habitica formulas. Refined other nested classes. Added convenience accessors to `User`.
14. **`cli/api.py`:** Marked as legacy, no changes applied (review focused on `tui/api.py`).
15. **`cli/app.py`:** Marked as legacy, no changes applied (contains original action logic for reference).
16. **`cli/challenge_backupper.py`:** Typing, anchors, docstrings applied. Logic seems okay for synchronous export.
17. **`cli/config_auth.py`:** Typing, anchors, docstrings applied. Logic seems okay.
18. **`cli/config_tags.py`:** Typing, anchors, docstrings applied. Logic seems okay for interactive setup.
19. **`cli/config.py`:** Typing, anchors, docstrings applied. Ensured correct loading and validation. Added `CACHE_FILE_CONTENT`. Clarified maps.
20. **`cli/data_processor.py`:** Marked as legacy, no changes applied.
21. **`cli/exports.py`:** Typing, anchors, docstrings applied. Logic seems okay for synchronous export.
22. **`cli/tag_manager.py`:** Marked as legacy, no changes applied (contains original action logic for reference).

---

**Summary of Changes & Legacy Marking:**

- **Formatted & Typed:** All Python files (`*.py`) have had type hints updated to Python 3.10+ style (using `|`, `list[]`, `dict[]`, etc., while keeping necessary `typing` imports for clarity/compatibility), comment anchors (`# SECTION:`, `# KLASS:`, `# FUNC:`) applied, and docstrings improved.
- **Legacy Files (`cli/`)**:
  - `api.py`, `app.py`, `data_processor.py`, `tag_manager.py`: These contain the core logic of the _old synchronous Rich application_. They are now primarily for **reference** to understand the original action logic that needs migrating to the async `tui/data_store.py`. They have been formatted but are marked as Legacy/Sync.
  - `challenge_backupper.py`, `exports.py`: These perform specific, potentially long-running export/backup tasks. They remain synchronous but could potentially be used by the TUI app if run in a separate thread (`textual.worker.run_in_thread`) to avoid blocking the UI. They have been formatted.
  - `config_auth.py`, `config_tags.py`, `config.py`: These handle configuration loading and setup. They are generally utilities that run at startup or during specific setup actions. They have been formatted and are likely still used by both the old CLI and the new TUI structure (especially `config.py` for loading `.env`).

**Next Steps Reminder:**

1.  **Implement TUI Widgets:** Create the actual Textual widget classes (`StatsPanel`, `MainMenu`, `TaskListWidget`, `ChallengeListWidget`, `TagListWidget`, etc.) in the `tui/widgets/` directory.
2.  **Integrate Widgets into App:** Replace the `PlaceholderWidget` instances in `tui/app.py`'s `compose` method with your new widgets.
3.  **Connect UI Events to DataStore Actions:** Implement `on_...` message handlers or `action_...` methods in `tui/app.py` to catch user interactions from the widgets (button clicks, list selections, key presses) and call `self.run_worker(self.datastore.some_action(...))`.
4.  **Implement DataStore Actions:** Add the remaining `async def` action methods to `tui/data_store.py` based on your TODO list and the logic found in the legacy `cli/app.py` and `cli/tag_manager.py`. Ensure these methods use `await self.api_client...` and trigger `asyncio.create_task(self.refresh_all_data())` on success.
5.  **Implement UI Updates:** Ensure the `notify_data_refreshed` mechanism in `tui/app.py` correctly updates all relevant widgets by calling their specific update methods (which should pull fresh data synchronously from `self.datastore.get_...()` methods).

You have a solid foundation now with the refactored data layer and a clear strategy for the TUI integration.

# **Async Code Review (`tui/` directory):**

## 1. **`tui/api.py`:**

    - **Async/Await:** Correctly uses `async`/`await` for `httpx` calls and internal rate limiting (`_wait_for_rate_limit`).
    - **`httpx` Usage:** Creates a client per request (`async with httpx.AsyncClient(...)`). This is fine for moderate usage, but for high frequency, instantiating the client once in `__init__` and closing it on app exit would be more performant (requires managing client lifecycle).
    - **Rate Limiting:** `_wait_for_rate_limit` logic looks correct using `time.monotonic()` and `asyncio.sleep()`.
    - **Error Handling (`_request`):** Generally robust. Catches `TimeoutException`, `HTTPStatusError`, `RequestError`, `JSONDecodeError`, and `ValueError`. Correctly parses Habitica's `{success: bool, data: ...}` wrapper and raises `HabiticaAPIError` on failure. Also handles successful non-wrapper responses (like `/content`). Returns `None` for 204 No Content. Logging uses the themed console. Looks good.
    - **Convenience Methods:** Correctly `await` the internal `_request` and perform basic type checking on results (e.g., ensuring `/user` returns a dict). Pagination logic in `get_challenges` seems correct.
    - **Typing:** Applied 3.10+ typing.
    - **Anchors/Docstrings:** Applied.
    - **Overall:** This async API client looks well-structured and handles common scenarios correctly.

## 2. **`tui/data_store.py`:**

    - **Initialization:** Correctly initializes API client, content manager, tag manager. Defers `TaskProcessor` initialization to `refresh_all_data`, which is good as it needs fetched data. Uses `asyncio.Lock` for refresh. Callback `app_notify_update` is stored.
    - **`refresh_all_data`:**
      - Uses the `asyncio.Lock` correctly.
      - Uses `asyncio.gather` for concurrent fetching, which is efficient. `return_exceptions=True` is crucial for handling partial failures.
      - **Content Cache Handling:** Correctly fetches fresh content, _saves it_, then invalidates the `GameContent` manager's internal cache to force a reload from the file. This ensures the processor gets the _newest_ content.
      - **Error Handling:** `_handle_fetch_result` correctly checks for exceptions and unexpected types for non-critical data. Critical data failures (user, tasks, content) correctly raise exceptions to stop the refresh.
      - **Processor Init:** Correctly initializes `TaskProcessor` _after_ fetching necessary data and updating the content cache.
      - **Model Instantiation:** Correctly creates model instances (`User`, `Party`, `ListTag`, `TaskList`, `ChallengeList`, `SpellList`) using the fetched/processed data. **Crucially**, it passes the _processed Task objects_ (`processed_task_objects_dict.values()`) to `TaskList`, and then passes that `TaskList` instance to `ChallengeList` for linking. This data flow looks correct.
      - **Stats Calculation:** Correctly calls `get_user_stats` after processing.
      - **UI Notification:** Correctly calls `self.app_notify_update()` in the `finally` block, ensuring the UI is always notified.
      - **Overall `refresh_all_data`:** This orchestration logic looks sound, handling concurrency, errors, caching, processing steps, and UI notification correctly.
    - **Data Accessors:** Simple synchronous getters for the UI layer to pull the current state. Correctly return `Optional` or empty lists if data isn't loaded.
    - **Action Methods (`toggle_sleep`, `score_task`, etc.):**
      - Correctly defined as `async`.
      - Correctly `await` the relevant `self.api_client` method.
      - Correctly handle errors using `try...except HabiticaAPIError`.
      - **Crucially**, on success, they trigger a background refresh using `asyncio.create_task(self.refresh_all_data())`. This is the right approach – don't `await` the refresh, just schedule it.
      - Return `True`/`False` to indicate success/failure to the caller (the Textual worker).
    - **Typing:** Applied 3.10+ typing.
    - **Anchors/Docstrings:** Applied.
    - **Overall:** `PixabitDataStore` seems well-designed as the central orchestrator. Its async refresh logic and action method structure are appropriate for the Textual TUI architecture.

## 3. **`tui/game_content.py` (Reviewed as `DataHandler`)**

    - The code provided seems to be a generic `DataHandler` rather than the specific `GameContent` manager mentioned earlier. Let's assume this is the intended replacement or a new utility.
    - **Lazy Loading:** The `load_or_fetch_data` method implements lazy loading logic: tries extracted cache, then raw cache, then API fetch. This is good.
    - **Caching:** Uses `load_json`/`save_json`. Assumes these are synchronous file I/O, which is usually acceptable in async apps unless files are huge or on slow network drives. For truly non-blocking file I/O, `aiofiles` or `textual.worker.run_in_thread` would be needed for the save/load calls.
    - **Fetching:** Correctly handles using either an async `fetch_func` (preferred) or a direct `api_url` via `httpx`.
    - **Extraction:** `_extract_required_dicts` uses `get_nested_item` (which is robust) to pull out specified sections. Handles errors gracefully.
    - **Typing:** Applied 3.10+ typing.
    - **Anchors/Docstrings:** Applied.
    - **Overall:** As a generic data handler/cacher, this looks reasonable. If this _is_ the `GameContent` manager, it needs to be instantiated correctly in `DataStore` and its methods (`get_gear_data`, etc.) should retrieve data from its `self.extracted_data`. The `DataStore` currently imports and uses a `GameContent` class - ensure the class name and methods match what `DataStore` expects. _Self-correction: I'll assume the `GameContent` class mentioned in the status description is the intended one, and this `DataHandler` code might be a utility or a previous version. The `DataStore` code imports `GameContent`, so I'll proceed assuming that class exists elsewhere or needs to be implemented based on this `DataHandler` logic._ For now, I'll format the provided `DataHandler` code.

## 4. **`tui/task_processor.py`:**

    - **Initialization:** Takes necessary context (`user_data`, `party_data`, `all_tags_list`, `game_content_manager`). Correctly uses the `GameContent` manager instance to get cached data (`get_gear_data`). Calculates context (`_calculate_user_context`) needed for processing.
    - **Context Calculation:** `_calculate_user_context` correctly computes effective CON, stealth, sleep, and quest/boss status based on the provided raw data and content lookups. Error handling seems reasonable.
    - **Task Processing (`process_and_categorize_all`):**
      - Instantiates the correct Task subclasses (`_create_task_object`).
      - Calls `_process_and_calculate_task` for each instance.
      - `_process_and_calculate_task`: This method correctly calculates status, value color, looks up tag names, and calculates potential damage for Dailies based on the formulas and context (CON, sleep, stealth, quest). It _modifies the Task instance directly_, which is efficient.
      - Categorization logic seems correct, grouping tasks by type/status and collecting unique tags/challenge IDs/broken tasks.
    - **`get_user_stats`:** This function correctly aggregates statistics from the user data and the categorized/processed task data. It uses the pre-calculated damage sums.
    - **Typing:** Applied 3.10+ typing.
    - **Anchors/Docstrings:** Applied.
    - **Overall:** The `TaskProcessor` looks solid. It encapsulates the complex logic of transforming raw tasks into processed objects with calculated fields and categories, using the necessary context data.

## 5. **`tui/app.py`:**

    - **Structure:** Basic Textual app with Header, Footer, and placeholder Containers. CSS path is set. Bindings for Quit/Refresh exist.
    - **Initialization:** Instantiates the _synchronous_ `HabiticaAPI`. **This needs to change.** The App should instantiate the `PixabitDataStore`.
    - **`on_mount`:** Calls placeholder refresh. Should call `datastore.refresh_all_data` via `run_worker`.
    - **`compose`:** Defines the basic layout. This will need to be filled with actual widgets.
    - **Actions:** `action_quit_app` is fine. `action_refresh_data_ui` is a placeholder and needs to be replaced with a call to `self.run_worker(self.datastore.refresh_all_data())`.
    - **Typing:** Applied 3.10+ typing.
    - **Anchors/Docstrings:** Applied.
    - **Overall:** This is a good starting shell but needs significant updates to integrate the `PixabitDataStore` and replace placeholders with real widgets and actions.

## 6. **`tui/pixabit.tcss`:** Basic CSS structure matching the `app.py` layout. Looks fine as a starting point.

---

# **Action Logic Integration Strategy:**

Okay, let's outline how to integrate the actions from your TODO list (and old `CliApp`) into the Textual/DataStore architecture, keeping the TUI and data layers separate as requested.

## **Core Principles:**

1.  **DataStore is the Gatekeeper:** All actions that modify Habitica data or require complex state logic go through `PixabitDataStore` async methods.
2.  **TUI Triggers Actions:** Widgets (Buttons, ListViews, Keybindings) capture user intent and trigger actions on the App.
3.  **App Orchestrates Async Actions:** The `PixabitTUIApp` receives UI events and uses `self.run_worker()` to call the appropriate `DataStore` async method in the background.
4.  **DataStore Executes Logic:** The `DataStore` method performs the action:
    - It might need data from its current state (e.g., `self.user_obj`, `self.tasks_list_obj`).
    - It calls the `HabiticaAPI` client (`await self.api_client.some_call(...)`).
    - For complex logic (like tag syncing), it _contains_ that logic, possibly calling helper functions, and makes the necessary API calls itself. **Avoid** calling synchronous methods in helper classes (like the old `TagManager`) that make blocking API calls directly. If you reuse logic from `TagManager`, adapt it into the `DataStore`'s async method or make the `TagManager` methods async if they perform API calls.
    - It handles API errors (`try...except HabiticaAPIError`).
    - On success, it schedules a data refresh: `asyncio.create_task(self.refresh_all_data())`.
    - It can return simple status (e.g., `bool`) to the worker if needed for immediate UI feedback (like a notification).
5.  **DataStore Refreshes State:** The background `refresh_all_data` task completes, fetches new data, processes it, updates the internal state (`self.user_obj`, etc.).
6.  **DataStore Notifies App:** `refresh_all_data` calls the `app_notify_update` callback provided during `DataStore` initialization.
7.  **App Updates UI:** The `app_notify_update` method in `PixabitTUIApp` triggers UI updates. This can be done by:
    - Directly calling `update()` or `refresh()` methods on relevant widgets (e.g., `self.query_one(StatsPanel).update_stats()`).
    - Posting custom Textual messages (e.g., `self.post_message(DataRefreshed())`) that widgets watch for using `on_` handlers. Widgets then pull fresh data _synchronously_ from the `DataStore`'s getter methods (`self.app.datastore.get_user_stats()`, etc.).

## **Implementation Steps & Examples:**

### 1. **Modify `PixabitTUIApp.__init__` and `on_mount`:**

    - Instantiate `PixabitDataStore`, passing `self.notify_data_refreshed` as the callback.
    - Remove the direct `HabiticaAPI` instantiation.
    - In `on_mount`, call `self.run_worker(self.datastore.refresh_all_data())` to perform the initial load.

    ```python
    # pixabit/tui/app.py (Changes)
    from textual.reactive import reactive
    from .data_store import PixabitDataStore # Import DataStore
    # Import widgets as you create them, e.g.:
    # from .widgets.stats_panel import StatsPanel
    # from .widgets.task_list import TaskListWidget

    class PixabitTUIApp(App[None]): # Specify return type for run() if needed
        # ... (CSS_PATH, BINDINGS as before, maybe add more bindings)

        # Add reactive variables to show loading state?
        show_loading: reactive[bool] = reactive(False)

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Instantiate DataStore, passing the notification method
            self.datastore = PixabitDataStore(app_notify_update=self.notify_data_refreshed)
            self._refresh_lock = asyncio.Lock() # Lock for UI refresh trigger

        async def on_mount(self) -> None:
            """Called when the app is mounted."""
            self.title = "Pixabit TUI"
            self.subtitle = "Habitica Assistant"
            # Trigger initial data load
            self.set_loading(True)
            self.run_worker(self.initial_data_load, exclusive=True)

        async def initial_data_load(self) -> None:
            """Worker task for the initial data load."""
            self.console.log("Starting initial data load...")
            await self.datastore.refresh_all_data()
            self.set_loading(False)
            self.console.log("Initial data load complete.")
            # Initial UI population happens in notify_data_refreshed

        def notify_data_refreshed(self) -> None:
            """Callback function passed to DataStore, called after data refresh."""
            # This runs in the DataStore's worker thread or asyncio task context.
            # Use call_from_thread to safely update UI components or post messages.
            # Using a lock to prevent potential race conditions if refresh is very fast.
            async def do_ui_update():
                async with self._refresh_lock:
                    self.console.log("UI: Received data refresh notification.")
                    self.set_loading(False) # Ensure loading indicator is off
                    # Example: Update Stats Panel
                    try:
                        stats_panel = self.query_one("#stats-panel") # Assuming you have a StatsPanel widget
                        stats_panel.update_stats(self.datastore.get_user_stats())
                    except Exception as e:
                        self.console.log(f"Error updating stats panel: {e}")

                    # Example: Update Task List (if currently visible)
                    try:
                        task_list = self.query_one("#task-list-widget") # Assuming TaskListWidget
                        task_list.refresh_tasks() # Widget method pulls data from store
                    except Exception as e:
                        # Handle case where widget might not exist/be mounted
                        pass # Or log self.console.log(f"Task list not found for refresh: {e}")

                    # Add updates for other widgets (Challenges, Tags, etc.)
                    self.console.log("UI: Triggered widget updates.")

            # Schedule the UI update to run on the main event loop thread
            self.call_from_thread(do_ui_update)


        def set_loading(self, loading: bool) -> None:
            """Helper to control a loading indicator (optional)."""
            self.show_loading = loading
            # You might toggle a LoadingIndicator widget visibility here
            # self.query_one(LoadingIndicator).display = loading


        def compose(self) -> ComposeResult:
            yield Header()
            yield Footer()
            # Replace placeholders with actual widgets
            yield Container(
                StatsPanel(id="stats-panel"), # Replace Label with actual StatsPanel widget
                MainMenu(id="menu-panel"),   # Replace Label with actual MainMenu widget
                ContentArea(id="content-panel") # Replace Label with ContentArea container
                # LoadingIndicator(id="loading"), # Optional loading indicator
                # id="main-content-area", # Keep ID for CSS
            )

        # Action to trigger refresh manually
        async def action_refresh_data_ui(self) -> None:
            """Action bound to 'r' - Triggers a data refresh."""
            self.console.log("Action: Manual Refresh Data")
            if not self.datastore.is_refreshing.locked():
                 self.set_loading(True)
                 # Pass exclusive=True to prevent multiple refreshes running?
                 self.run_worker(self.datastore.refresh_all_data, exclusive=True)
            else:
                self.console.log("Refresh already in progress, skipping manual trigger.")


        # Action to quit
        async def action_quit_app(self) -> None:
            """Action bound to 'q' - quits the app."""
            self.console.log("Action: Quit App")
            await self.shutdown() # Ensure async shutdown if needed
            self.exit() # Use self.exit()

        # --- Action Handlers (Examples) ---

        # Example: Handling a request from a widget to score a task
        async def on_task_list_widget_score_task(self, message: TaskListWidget.ScoreTask) -> None:
             """Handles the ScoreTask message from the TaskListWidget."""
             task_id = message.task_id
             direction = message.direction
             self.console.log(f"App: Handling score request for task {task_id} ({direction})")
             # Show loading/progress? Maybe a notification?
             self.set_loading(True) # Simple loading indicator
             # Run the DataStore action in the background
             self.run_worker(self.datastore.score_task(task_id, direction), exclusive=True)
             # Optional: Add optimistic UI update here
             # message.control.optimistic_score(task_id, direction)


        # Example: Handling a request from a button/binding to toggle sleep
        async def action_toggle_sleep(self) -> None:
             """Action to toggle user sleep status."""
             self.console.log("App: Handling toggle sleep request")
             self.set_loading(True)
             self.run_worker(self.datastore.toggle_sleep(), exclusive=True)

        # ... Add more action_ methods for keybindings ...
        # ... Add more on_ message handlers for widget events ...

    ```

### 2. **Create Widgets:**

    - **`StatsPanel`:** (`widgets/stats_panel.py`) A `Static` widget (or custom container). It needs an `update_stats(self, stats_data: Optional[Dict])` method. This method takes the dictionary from `datastore.get_user_stats()` and updates internal Labels or other display elements.
    - **`MainMenu`:** (`widgets/main_menu.py`) Use `ListView` or `OptionList`. Populate it with categories (Tasks, Tags, Challenges, etc.). Handle selection events (`on_list_view_selected` or `on_option_list_option_selected`) to post messages to the App (e.g., `ShowScreen("tasks")`) telling it which content view to display.
    - **`TaskListWidget`:** (`widgets/task_list.py`) Use `DataTable`. Needs a `refresh_tasks()` method that calls `self.app.datastore.get_tasks()`, clears the table, and repopulates it. Handle `on_data_table_row_selected` to show task details. Add filtering controls (e.g., an `Input` widget). When the user types in the filter input, call `refresh_tasks(filter_text=...)` which then calls `datastore.get_tasks(text_filter=...)`. For actions like scoring, handle key presses (`on_key`) or add buttons, then post a custom message (e.g., `self.post_message(self.ScoreTask(task_id, direction))`). Define the `ScoreTask` message class within the widget file.

### 3. **Implement Actions in `PixabitDataStore`:**

    - Add `async` methods for each action in your TODO list (e.g., `leave_challenge`, `delete_tag`, `set_cds`, `unlink_task`).
    - Follow the pattern: `await self.api_client.some_call(...)`, `try...except HabiticaAPIError`, `asyncio.create_task(self.refresh_all_data())`, `return True/False`.

    ```python
    # pixabit/tui/data_store.py (Example action additions)

    # ... (imports and existing methods) ...

    # MARK: - Action Methods (Asynchronous - Modify state via API)

    # FUNC: toggle_sleep (Already implemented)
    async def toggle_sleep(self) -> bool:
        # ... (keep existing implementation) ...

    # FUNC: score_task (Already implemented)
    async def score_task(self, task_id: str, direction: str) -> bool:
        # ... (keep existing implementation) ...

    # FUNC: leave_challenge
    async def leave_challenge(self, challenge_id: str, keep: str = "keep-all") -> bool:
        """Leaves a challenge and triggers a data refresh.

        Args:
            challenge_id: The ID of the challenge to leave.
            keep: How to handle tasks ('keep-all' or 'remove-all').

        Returns:
            True if the API call was successful, False otherwise.
        """
        self.console.log(f"DataStore: Action - Leaving challenge {challenge_id} (keep={keep})...", style="info")
        if keep not in ["keep-all", "remove-all"]:
             self.console.print("Invalid 'keep' parameter for leave_challenge.", style="error")
             return False
        try:
            # The API call itself might return None on success for this endpoint
            await self.api_client.leave_challenge(challenge_id, keep=keep)
            self.console.log(f"DataStore: Left challenge {challenge_id} successfully.", style="success")
            # Trigger refresh in the background
            asyncio.create_task(self.refresh_all_data())
            return True
        except HabiticaAPIError as e:
            self.console.print(f"DataStore: Error leaving challenge {challenge_id}: {e}", style="error")
            return False
        except Exception as e: # Catch unexpected errors
             self.console.print(f"DataStore: Unexpected error leaving challenge {challenge_id}: {e}", style="error")
             return False

    # FUNC: unlink_task
    async def unlink_task(self, task_id: str, keep: str = "keep") -> bool:
        """Unlinks a single task from its challenge.

        Args:
            task_id: The ID of the task to unlink.
            keep: How to handle the task ('keep' or 'remove').

        Returns:
            True if the API call was successful, False otherwise.
        """
        self.console.log(f"DataStore: Action - Unlinking task {task_id} (keep={keep})...", style="info")
        if keep not in ["keep", "remove"]:
             self.console.print("Invalid 'keep' parameter for unlink_task.", style="error")
             return False
        try:
            await self.api_client.unlink_task_from_challenge(task_id, keep=keep)
            self.console.log(f"DataStore: Unlinked task {task_id} successfully.", style="success")
            asyncio.create_task(self.refresh_all_data())
            return True
        except HabiticaAPIError as e:
            self.console.print(f"DataStore: Error unlinking task {task_id}: {e}", style="error")
            return False
        except Exception as e:
             self.console.print(f"DataStore: Unexpected error unlinking task {task_id}: {e}", style="error")
             return False

    # FUNC: delete_tag
    async def delete_tag(self, tag_id: str) -> bool:
         """Deletes a tag globally.

         Args:
             tag_id: The ID of the tag to delete.

         Returns:
             True if the API call was successful, False otherwise.
         """
         self.console.log(f"DataStore: Action - Deleting tag {tag_id} globally...", style="info")
         try:
             await self.api_client.delete_tag(tag_id)
             self.console.log(f"DataStore: Deleted tag {tag_id} successfully.", style="success")
             asyncio.create_task(self.refresh_all_data())
             return True
         except HabiticaAPIError as e:
             self.console.print(f"DataStore: Error deleting tag {tag_id}: {e}", style="error")
             return False
         except Exception as e:
             self.console.print(f"DataStore: Unexpected error deleting tag {tag_id}: {e}", style="error")
             return False

    # --- Example for Tag Syncing Logic (within DataStore) ---
    # FUNC: sync_challenge_personal_tags
    async def sync_challenge_personal_tags(self) -> bool:
        """Ensures tasks have mutually exclusive challenge/personal tags (DataStore version)."""
        description = "Challenge/Personal Tag Sync"
        challenge_tag_id = self.tag_manager.challenge_tag # Get configured IDs
        personal_tag_id = self.tag_manager.personal_tag

        if not challenge_tag_id or not personal_tag_id:
            self.console.print(f"[info]Skipping '{description}': Tags not configured.[/info]")
            return False
        if not self.tasks_list_obj:
            self.console.print(f"[warning]Skipping '{description}': Task list not loaded.[/warning]")
            return False

        actions: list[tuple[str, str, str]] = [] # (action_type, task_id, tag_id)
        tasks_processed = 0
        for task in self.tasks_list_obj.tasks:
            tags = set(task.tags) # Use the list of tag IDs from the Task object
            # Task object has `challenge` which is ChallengeData or None
            is_challenge = task.challenge is not None and task.challenge.id is not None

            if is_challenge:
                if challenge_tag_id not in tags:
                    actions.append(("add_tag", task.id, challenge_tag_id))
                if personal_tag_id in tags:
                    actions.append(("delete_tag", task.id, personal_tag_id))
            else: # Is personal task
                if personal_tag_id not in tags:
                    actions.append(("add_tag", task.id, personal_tag_id))
                if challenge_tag_id in tags:
                    actions.append(("delete_tag", task.id, challenge_tag_id))
            tasks_processed += 1

        self.console.log(f"Analyzed {tasks_processed} tasks for {description}.")

        if not actions:
             self.console.print(f"[success]{description}: All conform. No actions needed.[/success]")
             return False # No API calls needed, no refresh needed

        # Confirm and execute using API calls directly
        fix_count = len(actions)
        if not Confirm.ask(f"Apply {fix_count} tag changes for '{description}'?", default=False):
             self.console.print("[warning]Operation cancelled.[/warning]")
             return False

        error_count = 0
        # Simple execution loop (could use Progress bar like TagManager._confirm...)
        self.console.print(f"Applying {fix_count} changes...")
        for action_type, task_id, tag_id in actions:
            try:
                if action_type == "add_tag":
                    await self.api_client.add_tag_to_task(task_id, tag_id)
                elif action_type == "delete_tag":
                    await self.api_client.delete_tag_from_task(task_id, tag_id)
            except HabiticaAPIError as e:
                 # Log specific errors but continue if possible
                 self.console.print(f"API Error ({action_type} on {task_id}): {e}", style="error")
                 error_count += 1
            except Exception as e:
                 self.console.print(f"Unexpected Error ({action_type} on {task_id}): {e}", style="error")
                 error_count += 1

        # Trigger refresh regardless of errors if changes were attempted
        self.console.log(f"{description} finished. Errors: {error_count}.")
        asyncio.create_task(self.refresh_all_data())
        return True # Indicate that changes were attempted

    # ... Add other actions from TODO list (set_cds, CRUD operations, checklist, etc.)
    # For CRUD, you'll likely need Modal Screens in Textual to get input.
    # The screen would collect data, then call `app.run_worker(datastore.create_task(data))`

    ```

### 4. **Connect Widgets and App:**

    - In `PixabitTUIApp.compose`, replace placeholder `Label`s with your actual widget instances (`StatsPanel()`, `MainMenu()`, `TaskListWidget()`, etc.). Assign IDs if needed for CSS or querying.
    - Implement message handlers (`on_...`) or action methods (`action_...`) in the App to respond to widget events (like menu selection, button presses, row selection, key presses in DataTable).
    - These handlers will call `self.run_worker(self.datastore.some_action(...))`.
    - Implement the `app_notify_update` callback (shown above) to trigger widget refreshes after data changes.

This strategy keeps the `PixabitDataStore` as the single source of truth and action orchestrator, while the TUI layer focuses on display and event handling. The `run_worker` mechanism ensures async operations don't block the UI.

---

This comprehensive plan should guide you through building out the TUI components and integrating the action logic effectively. Remember to build incrementally – get the stats panel working, then the main menu, then the task list display, and then start adding actions one by one. Good luck with Pixabit!

---

# **Summary of Changes & Legacy Marking:**

- **Formatted & Typed:** All Python files (`*.py`) have had type hints updated to Python 3.10+ style (using `|`, `list[]`, `dict[]`, etc., while keeping necessary `typing` imports for clarity/compatibility), comment anchors (`# SECTION:`, `# KLASS:`, `# FUNC:`) applied, and docstrings improved.
- **Legacy Files (`cli/`)**:
  - `api.py`, `app.py`, `data_processor.py`, `tag_manager.py`: These contain the core logic of the _old synchronous Rich application_. They are now primarily for **reference** to understand the original action logic that needs migrating to the async `tui/data_store.py`. They have been formatted but are marked as Legacy/Sync.
  - `challenge_backupper.py`, `exports.py`: These perform specific, potentially long-running export/backup tasks. They remain synchronous but could potentially be used by the TUI app if run in a separate thread (`textual.worker.run_in_thread`) to avoid blocking the UI. They have been formatted.
  - `config_auth.py`, `config_tags.py`, `config.py`: These handle configuration loading and setup. They are generally utilities that run at startup or during specific setup actions. They have been formatted and are likely still used by both the old CLI and the new TUI structure (especially `config.py` for loading `.env`).

# **Next Steps Reminder:**

1.  **Implement TUI Widgets:** Create the actual Textual widget classes (`StatsPanel`, `MainMenu`, `TaskListWidget`, `ChallengeListWidget`, `TagListWidget`, etc.) in the `tui/widgets/` directory.
2.  **Integrate Widgets into App:** Replace the `PlaceholderWidget` instances in `tui/app.py`'s `compose` method with your new widgets.
3.  **Connect UI Events to DataStore Actions:** Implement `on_...` message handlers or `action_...` methods in `tui/app.py` to catch user interactions from the widgets (button clicks, list selections, key presses) and call `self.run_worker(self.datastore.some_action(...))`.
4.  **Implement DataStore Actions:** Add the remaining `async def` action methods to `tui/data_store.py` based on your TODO list and the logic found in the legacy `cli/app.py` and `cli/tag_manager.py`. Ensure these methods use `await self.api_client...` and trigger `asyncio.create_task(self.refresh_all_data())` on success.
5.  **Implement UI Updates:** Ensure the `notify_data_refreshed` mechanism in `tui/app.py` correctly updates all relevant widgets by calling their specific update methods (which should pull fresh data synchronously from `self.datastore.get_...()` methods).

You have a solid foundation now with the refactored data layer and a clear strategy for the TUI integration.
