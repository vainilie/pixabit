Okay, let's update the documentation and clarify the next steps for building the Textual TUI.

**1. Updated TODO List (`Migration.md`)**

I'll integrate the status and the plan into the existing TODO list format you provided in `Migration.md`.

```markdown
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
```

**2. Updated `Readme.md`**

````markdown
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
````

**3. Ordered & Explained Next Steps**

Here are the next steps ordered logically, with explanations in English and Spanish:

---

**Next Implementation Steps for Pixabit TUI**

1.  **(Foundation) Implement Core TUI Widgets:**

    - **What:** Create the basic building blocks of your UI in the `tui/widgets/` directory. Start with the simplest ones.
      - `StatsPanel`: Display user stats (HP, MP, Level, Gold, etc.). Likely a `Static` widget containing other Textual elements like `Label` or `Pretty`. Needs an `update_display(data)` method.
      - `MainMenu`: Display main navigation options (Tasks, Challenges, Tags, Settings). Use `ListView` or `OptionList`. Needs to emit a message when an item is selected.
      - `TaskListWidget`: Display tasks in a `DataTable`. Needs methods like `refresh_data()` to load tasks from the DataStore and update the table. Needs to handle user input (key presses, row selection) to trigger actions or view details.
      - _(Later)_ `ChallengeListWidget`, `TagListWidget`, `ContentArea` (to hold the list widgets), Detail Widgets, Modal Dialogs (for confirmations/forms).
    - **Why:** You need the visual components before you can connect logic to them. Start simple and build up.
    - **Spanish:** _(Fundación) Implementar Widgets Principales de TUI:_ Crea los bloques visuales básicos (`StatsPanel`, `MainMenu`, `TaskListWidget`, etc.) en `tui/widgets/`. Comienza con los más simples. Necesitan métodos para mostrar datos (ej. `update_display`) y deben emitir mensajes cuando el usuario interactúa (ej. selecciona un item).

2.  **(Integration) Integrate Widgets into the App Layout:**

    - **What:** In `tui/app.py`, modify the `compose()` method. Replace the `PlaceholderWidget` instances with instances of your newly created widgets (e.g., `yield StatsPanel(id="stats")`, `yield MainMenu(id="menu")`, etc.). Arrange them within the `Container` using the grid layout defined in your CSS.
    - **Why:** This puts the visual pieces together on the screen.
    - **Spanish:** _(Integración) Integrar Widgets en el Layout de la App:_ En `tui/app.py`, modifica `compose()` para usar tus nuevos widgets en lugar de los placeholders. Organízalos usando el `Container` y el layout de grid definido en el CSS.

3.  **(Data Flow) Connect Initial Data Load & Refresh Updates:**

    - **What:** Ensure the `PixabitTUIApp.notify_data_refreshed` callback correctly calls the `update_display` or `refresh_data` methods on your _visible_ widgets (`StatsPanel`, `TaskListWidget` if active, etc.) inside the `update_ui_after_refresh` method (which runs via `call_from_thread`). These widget methods will then call `self.app.datastore.get_...()` to pull the latest data _synchronously_ and update their display.
    - **Why:** This makes the UI show the initial data after `on_mount`'s load and automatically update whenever the `DataStore` finishes a background refresh.
    - **Spanish:** _(Flujo de Datos) Conectar Carga Inicial y Actualizaciones:_ Asegúrate de que el callback `notify_data_refreshed` en la App llame a los métodos de actualización de tus widgets (ej. `StatsPanel.update_display`). Estos métodos de widget obtendrán los datos más recientes del DataStore (`self.app.datastore.get_...()`) de forma síncrona para redibujar la UI. Esto muestra los datos iniciales y actualiza la UI automáticamente después de cada refresco.

4.  **(Interaction) Implement DataStore Action Methods:**

    - **What:** Add the `async def` methods to `tui/data_store.py` for all the user actions you want to support (scoring tasks, leaving challenges, deleting tags, creating tasks, etc.), based on the logic in your legacy files (`cli/app.py`, `cli/tag_manager.py`) and your TODO list. Each method should:
      1.  Perform necessary checks/logic.
      2.  Call the corresponding `await self.api_client.some_method(...)`.
      3.  Handle potential `HabiticaAPIError`.
      4.  On success, schedule a background refresh: `asyncio.create_task(self.refresh_all_data())`.
      5.  Return `True` or `False` to indicate success/failure to the caller.
    - **Why:** This centralizes all application logic and API interaction within the `DataStore`, keeping it separate from the UI.
    - **Spanish:** _(Interacción) Implementar Métodos de Acción en DataStore:_ Añade los métodos `async def` a `tui/data_store.py` para cada acción del usuario (puntuar tarea, salir de reto, borrar tag, etc.), basándote en la lógica de tus archivos legacy y tu TODO list. Cada método debe llamar a `await self.api_client...`, manejar errores, y si tiene éxito, planificar un refresco en segundo plano con `asyncio.create_task(self.refresh_all_data())`, devolviendo `True`/`False`. Esto centraliza la lógica.

5.  **(Wiring) Connect UI Events to DataStore Actions via App Workers:**

    - **What:** Make your widgets interactive.
      - For menu/list selections: The widget should `post_message` to the App when an item is selected. The App handles this message (e.g., in `on_main_menu_selected`) to switch the view in the content area.
      - For actions (buttons, key presses): The widget should `post_message` (e.g., `ScoreTask(task_id, direction)`) or the App handles a key binding (`action_...`). The App's handler method then calls `self.run_worker(self.datastore.corresponding_action(...))`.
    - **Why:** This connects the user's input in the UI to the background processing logic in the `DataStore` without blocking the UI thread.
    - **`run_worker` Explanation:** `self.run_worker(coroutine)` tells Textual to execute the provided asynchronous function (`coroutine`, e.g., `self.datastore.score_task(...)`) in a separate thread managed by Textual. This prevents the UI from freezing while waiting for the API call and subsequent refresh to complete. The `DataStore` action itself handles scheduling the refresh, and the notification callback eventually updates the UI.
    - **`asyncio.create_task` Explanation:** Inside the `DataStore` action methods, `asyncio.create_task(self.refresh_all_data())` is used _instead_ of `await self.refresh_all_data()`. This is crucial because the action method itself (like scoring a task) should return quickly after the API call succeeds. We don't want the action worker to wait for the _entire_ refresh process. `create_task` schedules the refresh to run independently in the background, allowing the action worker to finish promptly. The UI update happens later via the separate notification mechanism.
    - **Spanish:** _(Cableado) Conectar Eventos UI a Acciones DataStore vía Workers:_ Haz que los widgets sean interactivos. Cuando el usuario realiza una acción (clic, selección, tecla), el widget envía un mensaje a la App, o la App maneja una combinación de teclas. El manejador en la App llama a `self.run_worker(self.datastore.accion_correspondiente(...))`.
    - **Explicación `run_worker`:** `self.run_worker(coroutine)` le dice a Textual que ejecute la función asíncrona (coroutine) en un hilo separado. Esto evita que la interfaz de usuario (UI) se congele mientras espera la llamada a la API y el refresco. La acción en DataStore planifica el refresco, y el callback de notificación actualiza la UI más tarde.
    - **Explicación `asyncio.create_task`:** Dentro de los métodos de acción de `DataStore`, usamos `asyncio.create_task(self.refresh_all_data())` en lugar de `await`. Esto es clave porque la acción (ej. puntuar tarea) debe terminar rápido después de que la llamada API tenga éxito. No queremos esperar a que termine todo el refresco. `create_task` planifica el refresco para que se ejecute de forma independiente en segundo plano, permitiendo que el worker de la acción termine pronto. La UI se actualiza después a través de la notificación.

6.  **(Refinement) Add Confirmations, Error Handling, Styling:**
    - **What:** Implement modal confirmation dialogs (`ConfirmDialog(ModalScreen)`) where needed. Use `App.notify(...)` to show transient status messages or errors to the user. Flesh out your `pixabit.tcss` file to make the UI look good.
    - **Why:** Improves usability and provides necessary feedback.
    - **Spanish:** _(Refinamiento) Añadir Confirmaciones, Errores, Estilos:_ Implementa diálogos modales para confirmaciones. Usa `App.notify(...)` para mostrar mensajes de estado o errores. Completa tu archivo CSS (`pixabit.tcss`) para mejorar la apariencia.

---

This ordered list should provide a clear path forward. Focus on steps 1-3 first to get the basic structure displaying data, then tackle steps 4 and 5 incrementally for each action you want to implement. Good luck!
