**Assessment of Reusability:**

- **High Potential (Layout/CSS/Concepts):**
  - `stats.py` / `stats_widget.py`: CSS, `compose` layout for stats display. Reactive variables pattern (if adapted).
  - `sleep.py`: `Switch` widget usage, horizontal layout concept.
  - `tags.py` (`TagsWidget`): `DataTable` setup, column definitions.
  - `tags.py` (`TagManagerWidget`): Button layout ideas.
  - `home.py`: `TabbedContent` idea for organizing main views.
- **Medium Potential (Specific Logic Snippets - Needs Adaptation):**
  - The core _logic_ within the legacy action functions (`main_functions.py`, `cli/app.py`, `cli/tag_manager.py`) needs to be extracted, adapted to use the new data models (`User`, `Task`, etc.), made `async`, integrated into `DataStore` methods, and use the async `HabiticaAPI`.
- **Low/No Potential (Direct Reuse):**
  - Any code making direct synchronous API calls or using the old sync API client (`heart.basis.__get_data`, direct `httpx` calls within widgets).
  - Any code relying on the old processors (`heart.processors.*`).
  - Menu display logic (`main_menu.py`).
  - `.ini` based config (`auth_file.py`).
  - Generic examples (`backup.py`, `layout.py`, `demo_app.py`, `page.py`).
  - Duplicate utilities (`replace_filename.py`).

Essentially, treat the old TUI files as visual mockups and the old `cli` files as logic references. The new structure (`tui/data_store.py` + `tui/api.py` + `models/`) is the source of truth for data and actions now.
