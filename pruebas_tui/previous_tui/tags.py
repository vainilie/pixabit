# previous_tui_files/tags.py (LEGACY TUI WIDGET ATTEMPTS & EXAMPLES)

# SECTION: MODULE DOCSTRING
"""LEGACY: Contains various previous attempts related to tag display and management.

Includes:
- `TagsWidget`: Basic tag display using DataTable. Fetching logic is deprecated.
- `TagManagerWidget`: Example layout for tag management actions (buttons). Logic is deprecated.
- `SelectApp`: Generic Select widget example.
- Other related App/Section classes for testing/layout.

Focus on reusing DataTable setup from `TagsWidget` and layout ideas from `TagManagerWidget`.
All data fetching and action logic should move to DataStore/App.
"""

# SECTION: IMPORTS
from typing import Any, Dict, List, Optional, Tuple  # Added typing

# Textual Imports
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Header,
    Input,
    Label,
    Select,
    Static,
)

# Local Imports (These are from the OLD structure - likely invalid now)
# from heart.basis.__get_data import get_tags # Old API call
# from heart.processors.process_tags import process_tags # Old processor


# SECTION: TagsWidget (Legacy - Display)
# KLASS: TagsWidget
class TagsWidget(VerticalScroll):
    """LEGACY WIDGET: Displays tags in a scrollable DataTable.

    NOTE: Contains direct fetching/processing logic which is DEPRECATED.
    Should receive tag data via an update method and populate the table.
    DataTable setup might be reusable.
    """

    # Reactive state to store tag data (tuples for DataTable)
    _tags_data: reactive[list[Tuple]] = reactive([])

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        yield DataTable(id="tags_table", cursor_type="row")  # Enable row cursor

    # FUNC: on_mount
    def on_mount(self) -> None:
        """Called when the widget is mounted. Sets up table columns."""
        table = self.query_one(DataTable)
        table.add_columns("Name", "Category", "ID")  # Initialize columns
        # Data loading should be triggered by the App after initial refresh

    # FUNC: update_display (NEW - Required for new architecture)
    def update_display(self, tags: list[dict[str, Any]]) -> None:
        """Updates the table with new tag data.

        Args:
            tags: A list of tag dictionaries (e.g., from DataStore.get_tags()).
                  Each dict should have 'name', 'id', maybe 'category'/'type'.
        """
        self.log.info(f"TagsWidget received {len(tags)} tags to display.")
        # Process tags into tuples suitable for DataTable.add_rows
        # Determine category based on tag object properties (e.g., tag.origin, tag.challenge)
        processed_rows = []
        for tag in tags:
            if isinstance(tag, dict):  # Basic check
                name = tag.get("name", "N/A")
                tag_id = tag.get("id", "N/A")
                # Example categorization (adapt based on your Tag model)
                category = tag.get("origin", "personal")  # Default category
                if tag.get("challenge"):
                    category = "challenge"  # Override if challenge flag is true
                processed_rows.append((name, category, tag_id))

        # Update reactive variable, which triggers watch_tags_data
        self._tags_data = processed_rows

    # Watcher method to update the DataTable when reactive data changes
    def watch__tags_data(self, new_tags_data: list[Tuple]) -> None:
        """Called when the `_tags_data` reactive property changes."""
        try:
            table = self.query_one(DataTable)
            table.clear()  # Clear existing rows before adding new ones
            if new_tags_data:
                table.add_rows(new_tags_data)
            self.log.info(
                f"Tags DataTable updated with {len(new_tags_data)} rows."
            )
        except Exception as e:
            self.log.error(f"Error updating Tags DataTable: {e}")

    # DEPRECATED worker
    # @work
    # async def fetch_tags(self): ...


# previous_tui_files/tags.py (Continued...)


# SECTION: TagManagerWidget (Legacy - UI/Action Example)
# KLASS: TagManagerWidget
class TagManagerWidget(VerticalScroll):
    """LEGACY WIDGET: Example layout for managing tags with various operations.

    NOTE: Action button logic here is DEPRECATED and needs to be reimplemented
    to post messages to the App, which then triggers DataStore actions via workers.
    The layout structure (Buttons, Input, Select) might be reusable.
    """

    # Reactive state (if needed for display, but data comes from DataStore)
    # tags: reactive[list[dict[str, Any]]] = reactive([])
    # selected_tag_details: reactive[dict[str, Any]] | None = reactive(None)

    DEFAULT_CSS = """
    TagManagerWidget {
        border: round $accent;
        padding: 1;
    }
    #title { margin-bottom: 1; text-style: bold; }
    DataTable { height: 10; margin-bottom: 1; border: thin $primary; }
    Horizontal Button { margin: 0 1; }
    Vertical { margin-top: 1; border: thin $primary; padding: 1;}
    Input, Select { margin-bottom: 1; }
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the layout."""
        yield Static("Tag Manager [CONCEPT]", id="title")
        # Table to display tags (similar to TagsWidget)
        yield DataTable(id="tags_table")
        # Row of action buttons
        yield Horizontal(
            Button(
                "Check/Create Special", id="btn_special", variant="default"
            ),  # Renamed
            Button("Delete Selected", id="btn_delete", variant="error"),
            Button("Find Unused", id="btn_unused", variant="default"),
            Button("Replace Tag", id="btn_replace", variant="primary"),
            Button(
                "Add Tag Conditionally", id="btn_add_cond", variant="primary"
            ),  # Renamed
            # Button("Set/Create Tags for Stats", id="set_tags", variant="primary"), # Maybe less common
            Button("Edit Name", id="btn_edit", variant="primary"),
            # Button("Sort Tags", id="sort_tags", variant="primary"), # Ordering done via API?
        )
        # Section for editing/creating a tag (maybe hidden initially)
        yield Vertical(
            Static("Tag Details"),
            Input(placeholder="Tag Name", id="tag_name_input"),
            # Select for category might not be directly editable, depends on logic
            # Select(options=[("Challenge", "challenge"), ("Personal", "personal")], id="tag_category"),
            Button("Save Changes / Create", id="btn_save", variant="success"),
            id="edit-create-section",
        )

    # FUNC: on_mount
    def on_mount(self) -> None:
        """Called when the widget is mounted. Setup table."""
        # Similar to TagsWidget, setup columns
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Category", "ID")
        # Data loading triggered by App

    # FUNC: update_display (NEW)
    def update_display(self, tags: list[dict[str, Any]]) -> None:
        """Updates the DataTable with tag data."""
        try:
            table = self.query_one(DataTable)
            table.clear()
            # Process tags for display (similar to TagsWidget.update_display)
            processed_rows = []
            for tag in tags:
                if isinstance(tag, dict):
                    name = tag.get("name", "N/A")
                    tag_id = tag.get("id", "N/A")
                    category = tag.get("origin", "personal")
                    if tag.get("challenge"):
                        category = "challenge"
                    processed_rows.append((name, category, tag_id))
            if processed_rows:
                table.add_rows(processed_rows)
            self.log.info(
                f"TagManager DataTable updated with {len(processed_rows)} tags."
            )
        except Exception as e:
            self.log.error(f"Error updating TagManager DataTable: {e}")

    # DEPRECATED Action handlers - These should post messages to the App

    # @on(Button.Pressed, "#btn_special")
    # def action_special_tag(self): ...
    # @on(Button.Pressed, "#btn_delete")
    # def action_delete_tag(self): ...
    # @on(Button.Pressed, "#btn_unused")
    # def action_unused_tag(self): ...
    # etc...

    # Example of how an action *would* work now:
    @on(Button.Pressed, "#btn_delete")
    def handle_delete_button(self) -> None:
        """Handles press of the delete button."""
        table = self.query_one(DataTable)
        # Get selected row (assuming single selection) - requires cursor_type='row'
        row_key = table.cursor_row
        if row_key is not None:
            row_data = table.get_row(row_key)  # Get data for the selected row
            tag_id_to_delete = row_data[
                2
            ]  # Assuming ID is the 3rd column (index 2)
            tag_name_to_delete = row_data[0]
            self.log(
                f"Requesting delete for tag: {tag_name_to_delete} ({tag_id_to_delete})"
            )
            # Post message to App - Define this message class
            # class DeleteTagRequest(Message): def __init__(self, tag_id: str): self.tag_id = tag_id
            # self.post_message(self.DeleteTagRequest(tag_id_to_delete))
            # OR directly call an App action if simpler
            # Need confirmation dialog here! App should handle that before worker.
            self.app.confirm_and_delete_tag(
                tag_id_to_delete, tag_name_to_delete
            )
        else:
            self.app.notify("No tag selected to delete.", severity="warning")


# previous_tui_files/tags.py (Continued...)

# SECTION: Other Example/Utility Classes (Likely Not Needed)

# KLASS: TagsApp (Example Runner)
# class TagsApp(App): ... # Not needed for library

# KLASS: TagsSection (Example Layout)
# class TagsSection(VerticalScroll): ... # Example using Collapsible

# KLASS: SelectApp (Generic Example)
# class SelectApp(Vertical): ... # Not needed for library
