--- START OF FILE Migration.md ---
**Pixabit Textual TUI TODO List (Updated)**

_(Reflects refactoring of the data layer and plan for TUI implementation)_

**Phase 1: Basic Structure (Mostly Done)**

- [✅] Set up Textual App (`PixabitTUIApp`).
- [✅] Define basic CSS (`pixabit.tcss`).
- [✅] Implement Header/Footer widgets.
- [✅] Create placeholder content areas (`Container` with IDs).
- [✅] Implement basic keybindings (Quit, Refresh).

**Phase 2: Async API & Data Layer (Complete)**

- [✅] Convert `HabiticaAPI` to async using `httpx` (`tui/api.py`).
- [✅] Define Data Models (`models/`).
- [✅] Implement `GameContent` manager (lazy loading cache - `tui/game_content.py`).
- [✅] Refine `TaskProcessor` to use context/models, calculate status/damage (`tui/task_processor.py`).
- [✅] Refine `get_user_stats` function (`tui/task_processor.py`).
- [✅] Implement `PixabitDataStore` facade (`tui/data_store.py`).
- [✅] Implement `DataStore.refresh_all_data` (async fetch, sync process, state update, UI notification callback).

**Phase 3: Core UI Widget Implementation**

- [⏳ **Next**] **Implement `StatsPanel` Widget:** (`tui/widgets/stats_panel.py`) Create a `Static` or custom widget. Add an `update_display(self, stats_data: Optional[Dict])` method. In `PixabitTUIApp.update_ui_after_refresh`, query this widget and call `update_display(self.datastore.get_user_stats())`.
- [⏳ To Do] **Implement `MainMenu` Widget:** (`tui/widgets/main_menu.py`) Use `ListView` or `OptionList`. Populate with main categories (Tasks, Challenges, Tags, etc.). Handle selection events (`on_list_view_selected` or similar) to post a custom message to the App indicating the desired view (e.g., `self.post_message(self.MenuItemSelected("tasks"))`).
- [⏳ To Do] **Implement `TaskList` Widget:** (`tui/widgets/task_list.py`) Use `DataTable`. Add a `refresh_data()` method that calls `self.app.datastore.get_tasks(**filters)`, clears, and repopulates the table. Handle row selection (`on_data_table_row_selected`) potentially for a detail view later. Add filtering controls (e.g., an `Input` widget) connected to `refresh_data`. Handle actions (like scoring) via keybindings (`on_key`) or buttons that post custom messages to the App (e.g., `self.post_message(self.ScoreTask(task_id, direction))`).
- [⏳ To Do] **Implement `ChallengeList` Widget:** (`tui/widgets/challenge_list.py`) Similar structure to `TaskListWidget`, using `DataTable` and `self.app.datastore.get_challenges()`. Handle selection/actions as needed.
- [⏳ To Do] **Implement `TagList` Widget:** (`tui/widgets/tag_list.py`) Similar structure, using `DataTable` or `ListView` and `self.app.datastore.get_tags()`.

**Phase 4: Navigation & Content Switching**

- [⏳ To Do] **Implement Main App Navigation:** In `PixabitTUIApp`, handle messages from `MainMenu` (e.g., `on_main_menu_menu_item_selected`). Based on the message, mount/unmount the appropriate list widget (`TaskListWidget`, `ChallengeListWidget`, etc.) into the main `#content-panel` container. Use methods like `query_one("#content-panel").mount(...)` or `query_one("#content-panel").remove_children()`.
- [⏳ To Do] **Implement Detail Views (Later):** When an item is selected in a list widget (e.g., task selected in `TaskListWidget`), the widget should post a message. The App handles this message, possibly mounting a `TaskDetailWidget` into the `#content-panel` or a separate detail area.

**Phase 5: Action Implementation (Async)**

- [🚧 **In Progress**] **Implement DataStore Actions:** Add `async def` methods to `PixabitDataStore` for _all_ remaining actions from the legacy TODO list (e.g., `leave_challenge`, `delete_tag`, `set_cds`, `create_task`, `update_task`, `delete_task`, checklist actions, etc.). Ensure they use `await self.api_client...`, handle errors, and trigger `asyncio.create_task(self.refresh_all_data())` on success. Reference logic from `cli/app.py` and `cli/tag_manager.py`, adapting it to the async context within `DataStore`.
- [⏳ To Do] **Connect UI to Actions:** Add `Button`s or keybindings (`on_key`) in relevant widgets/screens. Event handlers in the widgets should post custom messages (like `TaskListWidget.ScoreTask`). Handlers in `PixabitTUIApp` (like `on_task_list_widget_score_task`) will call `app.run_worker(self.datastore.action_method(...))`.
- [⏳ To Do] **Implement TUI Confirmations:** Replace Rich `Confirm` with Textual modal screens. Create a reusable `ConfirmDialog(ModalScreen)` that can be pushed via `app.push_screen(ConfirmDialog(...))` within action methods _before_ calling `run_worker` or potentially from within the worker _before_ the API call (though this is slightly more complex).
- [⏳ To Do] **Implement TUI Progress (Later):** For long-running batch actions within `DataStore` (like tag syncing if reimplemented), the `DataStore` method could accept an optional callback function provided by the App worker. This callback could update a Textual `ProgressBar` via `app.call_from_thread`. Alternatively, use simpler loading indicators for now.
- [⏳ To Do] **Implement Specific Actions (Map to DataStore methods):**
  - Toggle Sleep (`datastore.toggle_sleep`) - _Done in example_
  - Score Task (`datastore.score_task`) - _Done in example_
  - Handle Broken Tasks (UI needs list + selection -> call `datastore.unlink_task`)
  - Leave Challenge (UI needs list + selection -> call `datastore.leave_challenge`)
  - Delete Unused Tags (UI needs list + confirm -> loop call `datastore.delete_tag`)
  - Set CDS (UI needs input -> call `datastore.set_custom_day_start` - Requires API method)
  - Task CRUD (major: needs forms/inputs -> calls `datastore.create/update/delete_task` - Requires API methods)
  - Checklist actions (UI in task detail -> calls `datastore.checklist_*` methods - Requires API methods)
  - Pin/Unpin (UI needs list + action -> call `datastore.move_task_to_position` - Requires API method)
  - Banking (Requires config & UI -> calls `datastore.score_task` repeatedly)
  - Inbox (UI needs list/input -> calls `datastore.get/send_inbox` methods - Requires API methods)
  - Exports (UI trigger -> calls `export_*.py` functions via `app.run_in_thread`)

**Phase 6: Styling & Refinement**

- [⏳ To Do] Flesh out `pixabit.tcss` extensively for all widgets.
- [⏳ To Do] Refine layouts for different screen sizes (if needed).
- [⏳ To Do] Add more robust error display in the UI (e.g., via `App.notify` or dedicated status bar).
- [⏳ To Do] Add Unit/Integration Tests.

--- END OF FILE Migration.md ---
