# pixabit/tui/widgets/tasks_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the TaskListWidget for displaying and interacting with Habitica tasks."""

# SECTION: IMPORTS
import asyncio
import datetime
import logging
from datetime import timezone
from operator import attrgetter  # For sorting if needed later
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytz
from rich.logging import RichHandler

# Textual Imports
from rich.text import Text
from textual import events, log, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Select
from textual.widgets._data_table import CellKey, ColumnKey, RowKey

# Local Imports (Adjust path if necessary)
try:
    # Assumes models is two levels up from widgets directory
    from ...models.task import Daily, Task, TaskList, Todo
except ImportError:
    # Fallback definitions
    Task = dict
    Todo = dict
    Daily = dict
    TaskList = list  # type: ignore
    print("Warning: Could not import Task models in task_list.py")

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)  # Keep for rich tracebacks
# SECTION: MESSAGE CLASSES
# Define messages this widget can send to the App


# KLASS: ScoreTaskRequest
class ScoreTaskRequest(Message):
    """Message sent when requesting to score a task."""

    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


# KLASS: ViewTaskDetailsRequest
class ViewTaskDetailsRequest(Message):
    """Message sent when requesting to view task details."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


# SECTION: WIDGET CLASS
# KLASS: TaskListWidget
class TaskListWidget(Widget):
    """A widget to display Habitica tasks in a DataTable with filtering and sorting."""

    DEFAULT_CSS = """
    TaskListWidget {
        height: 100%;
        width: 100%;
        display: block;
    }
    TaskListWidget > Vertical { /* Target the direct Vertical child */
        height: 100%;
    }
    Select {
        width: 50%; /* Adjust as needed */
        margin-bottom: 1;
    }
    Input {
        dock: top; /* Place input above table within the Vertical */
        margin-bottom: 1;
    }
    DataTable {
        height: 1fr; /* Fill remaining space below Input/Select */
        border: round $accent;
    }
    /* Status Cell Styling */
    .status-due { color: $warning; }
    .status-red { color: $error; }
    .status-done { color: $success; }
    .status-success { color: $success; }
    .status-grey { color: $text-muted; }
    .status-habit { color: $secondary; }
    .status-reward{ color: $warning; } /* Added reward color */
    .status-unknown { color: $text-disabled; } /* Color for unknown status */
    """

    # --- State ---
    # Reactive variables trigger watchers when changed
    _text_filter = reactive("", layout=True)
    # Set default directly in reactive()

    _active_task_type = reactive(
        "all"
    )  # Default to 'all' maybe? Or init later?

    # Sorting State
    _sort_column_key: ColumnKey | None = reactive(None)
    _sort_reverse: reactive[bool] = reactive(False)

    # Internal storage for data and table reference
    _datatable: DataTable | None = None
    _tasks: list[Task] = []  # Store the raw Task objects for sorting/filtering

    # FUNC: __init__
    def __init__(
        self,
        task_type: str | None = None,
        id: str | None = None,
        **kwargs,
    ):
        """Initialize the TaskListWidget.

        Args:
            task_type: The type of tasks this widget instance should display by default.
                       If None or 'all', fetches all types.
            id: The widget ID. Auto-generated if None.
            **kwargs: Additional keyword arguments for Widget.
        """
        # 1. Determine the ID first
        widget_id = id or f"task-list-{task_type or 'all'}"

        # 2. Call super().__init__ FIRST, passing the ID
        super().__init__(id=widget_id, **kwargs)

        # 3. Now set instance attributes and initial reactive values if needed
        self.task_type_filter = task_type  # Store the base filter type
        # Set initial value for the reactive var *after* super init
        # Use the stored task_type_filter to set the initial state
        self._active_task_type = (
            self.task_type_filter
            if self.task_type_filter and self.task_type_filter != "all"
            else "all"
        )

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create child widgets: Select, Input, and DataTable within a Vertical layout."""
        with Vertical():  # Use Vertical layout
            yield Select(
                options=[
                    ("All", "all"),  # Add 'All' option
                    ("Todos", "todo"),
                    ("Dailies", "daily"),
                    ("Habits", "habit"),
                    ("Rewards", "reward"),
                ],
                value=self._active_task_type,  # Set initial value
                id="task-type-select",
                allow_blank=False,
            )
            yield Input(
                placeholder="Filter tasks by text...", id="task-filter-input"
            )
            # Create and store the DataTable instance
            self._datatable = DataTable(
                id="tasks-data-table", cursor_type="row", zebra_stripes=True
            )
            # Define columns here - this ensures they exist before on_mount tries to load data
            self._datatable.add_column(
                "S", key="status", width=20
            )  # No sortable=False
            self._datatable.add_column(
                "Task Text", key="text", width=40
            )  # No sortable=True
            self._datatable.add_column(
                "Value", key="value", width=8
            )  # No sortable=True
            self._datatable.add_column(
                "Pri", key="priority", width=5
            )  # No sortable=True
            self._datatable.add_column(
                "Due", key="due", width=12
            )  # No sortable=True
            self._datatable.add_column("Tags", key="tags")  # No sortable=False
            yield self._datatable

    # FUNC: on_mount
    async def on_mount(self) -> None:
        log.info("Mounting TaskListWidget...")
        table = self._datatable
        if not table:
            log.error("DataTable instance not found in on_mount!")
            return
        # Columns are added in compose now
        self.run_worker(
            self.load_or_refresh_data,
            exclusive=True,
            name=f"load_{self.id}",
            group="load_tasks",
        )

    # --- Data Loading / Refreshing ---
    #    @work(exclusive=True, group="load_tasks")
    async def load_or_refresh_data(self) -> None:
        """Worker task to fetch tasks from DataStore, apply filters, and update the table."""
        table = self._datatable
        if not table:
            log.error("DataTable instance is None in load_or_refresh_data!")
            return

        log.info(
            f"TaskListWidget ({self.id}): Refreshing. Type='{self._active_task_type}', Text='{self._text_filter}'"
        )

        # --- Store current cursor key value ---
        current_row_key_value: str | None = None
        current_cursor_coordinate: Coordinate | None = table.cursor_coordinate
        if current_cursor_coordinate and table.is_valid_coordinate(
            current_cursor_coordinate
        ):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(
                    current_cursor_coordinate
                )
                current_row_key_value = str(cell_key.row_key.value)
                log.info(
                    f"Saved current row key value: {current_row_key_value}"
                )
            except Exception as e:
                log.warning(
                    f"Could not get row key for coordinate {current_cursor_coordinate}: {e}"
                )
        # --- End Store Key ---

        table.loading = True
        table.clear()
        self._tasks = []  # Clear internal list

        # Prepare filters for DataStore call
        data_filters = {"text_filter": self._text_filter}

        # --- Use the REACTIVE _active_task_type ---
        active_type = (
            self._active_task_type
        )  # Get current value from Select/reactive
        if active_type and active_type != "all":
            data_filters["task_type"] = active_type
        # --- END Use Reactive ---

        # Get list[Task] from DataStore
        try:
            fetched_tasks: list[Task] = self.app.datastore.get_tasks(
                **data_filters
            )
            log(
                f"Received {len(fetched_tasks)} tasks (type: {active_type}, text: '{self._text_filter}') from DataStore."
            )
            self._tasks = fetched_tasks
        except Exception as e:
            log.error(f"Error getting list[Task] from datastore: {e}")
            self._tasks = []

        # Sort and display the fetched tasks
        self.sort_and_display_tasks()  # Sorts and adds rows

        table.loading = False

        # --- Restore cursor ---
        if current_row_key_value is not None:
            try:
                new_row_index = table.get_row_index(
                    RowKey(current_row_key_value)
                )
                table.move_cursor(row=new_row_index, animate=False)
                log.info(
                    f"Restored cursor to row index {new_row_index} for key {current_row_key_value}"
                )
            except KeyError:
                log.warning(
                    f"Could not find row key '{current_row_key_value}' after refresh. Resetting cursor."
                )
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
            except Exception as e:
                log.error(f"Error restoring cursor: {e}")
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
        elif table.row_count > 0:
            table.move_cursor(row=0, animate=False)  # Default to top

    # --- Sorting and Display ---
    def sort_and_display_tasks(self):
        """Sorts internal _tasks list based on current state and updates table rows."""
        table = self._datatable
        if not table:
            return
        log.info(
            f"sort_and_display_tasks: Starting. Row count before clear: {table.row_count}. Sorting key: {self._sort_column_key}, reverse: {self._sort_reverse}"
        )

        table.clear()
        log.info(
            f"sort_and_display_tasks: Table cleared. Row count: {table.row_count}"
        )

        sorted_tasks = self._tasks

        # Apply sorting if a sort key is set
        if self._sort_column_key is not None:
            try:
                # Define how to get the value for sorting based on column key
                def get_sort_value(task: Task) -> Any:
                    key_str = str(
                        sort_key.value
                    )  # Get the string key ('text', 'value', 'priority', 'due')
                    if key_str == "status":
                        return getattr(
                            task, "_status", ""
                        )  # Sort by status string
                    elif key_str == "text":
                        return getattr(
                            task, "text", ""
                        ).lower()  # Case-insensitive text sort
                    elif key_str == "value":
                        return getattr(task, "value", 0.0)
                    elif key_str == "priority":
                        return getattr(task, "priority", 0.0)
                    elif key_str == "due":  # Sort by date object if available
                        if isinstance(task, Todo) and task.due_date:
                            return task.due_date
                        if isinstance(task, Daily) and task.next_due:
                            return task.next_due[0]
                        return datetime.max.replace(
                            tzinfo=timezone.utc
                        )  # Put tasks without date last
                    else:
                        return None  # Default for unknown keys

                sorted_tasks = sorted(
                    self._tasks, key=get_sort_value, reverse=self._sort_reverse
                )
                log.info(
                    f"Sorted tasks by '{self._sort_column_key.value}', reverse={self._sort_reverse}"
                )
            except Exception as e:
                log.error(
                    f"Error sorting tasks by key '{self._sort_column_key}': {e}"
                )
                sorted_tasks = self._tasks  # Revert

        # Prepare rows from the (potentially sorted) list
        rows_to_add = []
        added_row_count = 0  # Count rows processed in loop
        for task in sorted_tasks:
            try:
                # --- Extract and Format Row Data ---
                status = getattr(task, "_status", "unknown")
                text = getattr(task, "text", "")
                styled_text = getattr(
                    task, "styled", ""
                )  # Convert Markdown to styled Text

                value = getattr(task, "value", 0.0)
                priority = getattr(task, "priority", 1.0)
                tag_names = getattr(task, "tag_names", [])
                tag_str = ", ".join(tag_names)  # Plain string for tags
                due_str = ""
                if isinstance(task, Todo) and task.due_date:
                    due_str = task.due_date.strftime("%Y-%m-%d")
                elif isinstance(task, Daily) and task.next_due:
                    due_str = task.next_due[0].strftime("%Y-%m-%d")

                status_icon = " ?"
                status_color = self.get_status_style(status)
                if status_icon == " ?" and status == "unknown":
                    status_icon = "⁇"  # Different icon for unknown

                status_cell = Text(status_icon, style=f"bold {status_color}")

                # --- Create Row Tuple (Simple Types Preferred) ---
                # Ensure order matches add_column calls
                row_data_cells = (
                    status_cell,  # Keep Text for styled icon
                    styled_text,  # Plain string
                    f"{value:.1f}",
                    f"{priority:.1f}",
                    due_str,  # Plain string
                    tag_str,  # Plain string
                )
                # --- End Create Cells ---

                # --- ADD ROW directly with KEY ---
                table.add_row(*row_data_cells, key=str(task.id))
                added_row_count += 1
                # --- END ADD ROW ---

            except Exception as e:
                log.error(
                    f"Error processing task {getattr(task, 'id', 'N/A')} for row: {e}"
                )

        # --- ADD LOG: Before add_rows ---
        # log.info(f"sort_and_display_tasks: Prepared {len(rows_to_add)} rows to add.")
        # if not rows_to_add and len(sorted_tasks) > 0:
        #     log.warning(
        #         "sort_and_display_tasks: No rows prepared, but tasks exist. Check row processing logic."
        #     )

        # # Add rows using task ID string as key value
        # if rows_to_add:  # Only call add_rows if there's something to add
        #     table.add_rows(rows_to_add)
        log.info(
            f"sort_and_display_tasks: Finished. Final row count: {table.row_count}"
        )

    def get_status_style(self, status: str) -> str:
        """Maps status string to CSS color variable."""
        return {
            "due": "$warning",
            "red": "$error",
            "done": "$success",
            "success": "$success",
            "grey": "$text-muted",
            "habit": "$secondary",
            "reward": "$warning",
            "unknown": "$text-disabled",
        }.get(
            status, "$text-muted"
        )  # Default fallback

    # --- Event Handlers ---
    # Watchers trigger run_worker, which calls the now non-decorated async method
    def watch__active_task_type(self, new_type: str) -> None:
        self.run_worker(
            self.load_or_refresh_data,
            name=f"filter_type_{self.id}",
            group="load_tasks",
        )

    def watch__text_filter(self, new_filter: str) -> None:
        # Using run_worker directly instead of debounce for now to isolate issue
        self.run_worker(
            self.load_or_refresh_data,
            name=f"filter_text_{self.id}",
            group="load_tasks",
            exclusive=True,
        )

    # Handlers remain the same
    @on(Select.Changed, "#task-type-select")
    def handle_type_change(self, event: Select.Changed) -> None:
        """Handle task type selection change."""
        # Update the reactive variable with the new selection
        self._active_task_type = event.value
        log.info(f"Task type filter changed to: {self._active_task_type}")

    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None: ...

    # Header selection handler remains the same, but now relies on the key existing
    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected):
        table = self._datatable
        if not table:
            return
        column_key = event.column_key  # This is a ColumnKey object
        # --- Check if the column key exists before trying to access .sortable ---
        # (Since .sortable was removed, this check might not be strictly needed,
        # but it's good practice if you might add other non-sortable columns later)
        try:
            column = table.get_column(column_key)  # Check if key is valid
            # Proceed only if the column key is valid (implicitly sortable now)
            if column_key == self._sort_column_key:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column_key = column_key
                self._sort_reverse = False
            log.info(
                f"Sorting state updated: key={self._sort_column_key.value}, reverse={self._sort_reverse}"
            )
            self.sort_and_display_tasks()
        except KeyError:
            log.warning(
                f"Attempted to sort by invalid or non-existent column key: {column_key}"
            )
        except Exception as e:
            log.error(f"Error during header selection sorting: {e}")

    # Handle key presses
    def on_key(self, event: events.Key) -> None:
        table = self._datatable
        if not table or not table.row_count:
            return

        cursor_coordinate = table.cursor_coordinate
        if cursor_coordinate and table.is_valid_coordinate(cursor_coordinate):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(
                    cursor_coordinate
                )
                if cell_key.row_key is None:
                    return  # Should have a row key
                task_id = str(cell_key.row_key.value)

                if task_id:
                    if event.key == "+":
                        self.post_message(ScoreTaskRequest(task_id, "up"))
                        event.stop()
                    elif event.key == "-":
                        self.post_message(ScoreTaskRequest(task_id, "down"))
                        event.stop()
                    # Add other key checks if needed
            except (KeyError, Exception) as e:
                log.error(f"Key handler error: {e}")

    # Handle row selection
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        task_id_key: RowKey | None = event.row_key
        if task_id_key is not None:
            task_id = str(task_id_key.value)
            log.info(f"Row selected, task ID: {task_id}")
            self.post_message(ViewTaskDetailsRequest(task_id))
