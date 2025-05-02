from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytz
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Select
from textual.widgets._data_table import CellKey, ColumnKey, RowKey

from pixabit.helpers._logger import log
from pixabit.models.task import Daily, Task, Todo


class ScoreTaskRequest(Message):
    """Message to request scoring a task."""

    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


class ViewTaskDetailsRequest(Message):
    """Message to request viewing task details."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class TaskListWidget(Widget):
    """Widget for displaying and interacting with a list of tasks."""

    # Reactive attributes for filtering and sorting
    _text_filter = reactive("", layout=True)
    tag_colors = reactive({})
    sort_key = reactive(None)
    sort_ascending = reactive(True)

    def __init__(
        self,
        task_type: str | None = None,
        id: str | None = None,
        **kwargs,
    ):
        """Initialize the task list widget.

        Args:
            task_type: Type of tasks to display ('todo', 'daily', etc.)
            id: Widget ID
        """
        self.task_type_filter = task_type
        widget_id = id or f"task-list-{task_type or 'all'}"
        super().__init__(id=widget_id, **kwargs)
        self._datatable = None
        self._tasks = []
        self._sort_value_cache = {}

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Vertical():
            yield Input(placeholder="Filter tasks...", id="task-filter-input")
            self._datatable = DataTable(id="tasks-data-table", cursor_type="row", zebra_stripes=True)
            self._datatable.add_column("S", key="status", width=3)
            self._datatable.add_column("Task", key="text", width=40)
            self._datatable.add_column("Value", key="value", width=8)
            self._datatable.add_column("Pri", key="priority", width=5)
            self._datatable.add_column("Due", key="due", width=12)
            self._datatable.add_column("Tags", key="tags")
            yield self._datatable

    async def on_mount(self) -> None:
        """Handle widget mount."""
        log.info(f"Mounting TaskListWidget {self.id}...")
        if not self._datatable:
            log.error("DataTable instance not found in on_mount!")
            return

        # Initial data load
        self.run_worker(
            self.load_or_refresh_data,
            exclusive=True,
            name=f"load_{self.id}",
            group="load_tasks",
        )

    def watch__text_filter(self, new_filter: str) -> None:
        """React to changes in text filter."""
        log.info(f"Watch: _text_filter changed to '{new_filter}'")
        self.run_worker(
            self.load_or_refresh_data,
            name=f"filter_text_{self.id}",
            group="load_tasks",
            exclusive=True,
        )

    def watch_tag_colors(self, new_colors: dict[str, str]) -> None:
        """React to changes in tag colors."""
        log.info("Watch: Tag colors changed. Re-sorting/displaying tasks.")
        self._invalidate_sort_cache()
        self.sort_and_display_tasks()

    def watch_sort_key(self, new_key: str) -> None:
        """React to changes in sort key."""
        if new_key:
            log.info(f"Watch: sort_key changed to {new_key}")
            self._invalidate_sort_cache()
            self.sort_and_display_tasks()

    def watch_sort_ascending(self, ascending: bool) -> None:
        """React to changes in sort direction."""
        log.info(f"Watch: sort_ascending changed to {ascending}")
        self.sort_and_display_tasks()

    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None:
        """Handle changes to the text filter input."""
        self._text_filter = event.value

    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle clicking on table headers for sorting."""
        table = self._datatable
        if not table:
            return

        column_key = event.column_key
        try:
            column_string_key = str(column_key.value)
            sortable_keys = ["status", "text", "value", "priority", "due", "tags"]

            if column_string_key not in sortable_keys:
                return

            # Toggle sort direction if same column, change column otherwise
            if column_string_key == self.sort_key:
                self.sort_ascending = not self.sort_ascending
            else:
                self.sort_key = column_string_key
                self.sort_ascending = True

            log.info(f"Sorting by {self.sort_key}, ascending={self.sort_ascending}")
        except Exception as e:
            log.error(f"Error during header selection: {e}")

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard input for task actions."""
        table = self._datatable
        if not table or not table.row_count:
            return

        cursor_coordinate = table.cursor_coordinate
        if cursor_coordinate and table.is_valid_coordinate(cursor_coordinate):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(cursor_coordinate)
                if cell_key.row_key is None:
                    return

                task_id = str(cell_key.row_key.value)
                if task_id:
                    if event.key == "+":
                        self.post_message(ScoreTaskRequest(task_id, "up"))
                        event.stop()
                    elif event.key == "-":
                        self.post_message(ScoreTaskRequest(task_id, "down"))
                        event.stop()
            except Exception as e:
                log.error(f"Key handler error: {e}")

    @on(DataTable.RowSelected)
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to view task details."""
        task_id_key: RowKey | None = event.row_key
        if task_id_key is not None:
            task_id = str(task_id_key.value)
            log.info(f"Row selected, task ID: {task_id}")
            self.post_message(ViewTaskDetailsRequest(task_id))

    async def load_or_refresh_data(self) -> None:
        """Load or refresh the task list data."""
        table = self._datatable
        if not table:
            log.error("DataTable instance is None in load_or_refresh_data!")
            return

        log.info(f"TaskListWidget ({self.id}): Refreshing. Type='{self.task_type_filter}', Text='{self._text_filter}'")

        # Remember current selection
        current_row_id = self._get_current_cursor_row_id()

        # Clear table and prepare for new data
        table.loading = True
        table.clear()
        self._tasks = []
        self._invalidate_sort_cache()

        # Set up filters
        data_filters = {"text_filter": self._text_filter}
        if self.task_type_filter and self.task_type_filter != "all":
            data_filters["task_type"] = self.task_type_filter

        try:
            # Fetch tasks from data store
            fetched_tasks = await self.app.run_in_thread(self.app.datastore.get_tasks, **data_filters)
            log.info(f"Received {len(fetched_tasks)} tasks from DataStore.")
            self._tasks = fetched_tasks
        except Exception as e:
            log.error(f"Error getting tasks from datastore: {e}")
            self._tasks = []

        # Sort and display tasks
        self.sort_and_display_tasks()
        table.loading = False

        # Restore cursor position if possible
        self._restore_cursor_position(current_row_id)

    def sort_and_display_tasks(self) -> None:
        """Sort and display tasks based on current sort settings."""
        table = self._datatable
        if not table:
            return

        table.clear()
        sorted_tasks = self._tasks

        # Sort if a sort key is set
        if self.sort_key is not None:
            try:
                sorted_tasks = sorted(self._tasks, key=lambda task: self._get_sort_value(task), reverse=not self.sort_ascending)
            except Exception as e:
                log.error(f"Error sorting tasks: {e}")

        # Add rows for all tasks
        for task in sorted_tasks:
            try:
                self._add_row_for_task(table, task)
            except Exception as e:
                task_id = getattr(task, "id", "N/A")
                log.error(f"Error adding row for task {task_id}: {e}")

    def _add_row_for_task(self, table: DataTable, task: Task) -> None:
        """Add a row to the table for a task."""
        try:
            # Get task attributes
            status = getattr(task, "_status", "unknown")
            value = getattr(task, "value", 0.0)
            priority = getattr(task, "priority", 1.0)
            tag_names = getattr(task, "tag_names", [])
            task_id = getattr(task, "id", f"no-id-{id(task)}")

            # Create cell content
            status_cell = Text("●", style=f"bold {self._get_status_style(status)}")
            task_text = Text.from_markup(getattr(task, "text", ""))
            due_str = self._format_due_date(task)
            tag_str = self._create_tags_cell(tag_names)

            # Add the row
            table.add_row(
                status_cell,
                task_text,
                f"{value:.1f}",
                f"{priority:.1f}",
                due_str,
                tag_str,
                key=str(task_id),
            )
        except Exception as e:
            log.error(f"Error adding row for task: {e}")

    def _format_due_date(self, task: Task) -> str:
        """Format the due date for a task."""
        due_str = ""
        try:
            if isinstance(task, Todo) and task.due_date:
                due_str = task.due_date.strftime("%Y-%m-%d")
            elif isinstance(task, Daily) and task.next_due and task.next_due[0]:
                due_str = task.next_due[0].strftime("%Y-%m-%d")
        except Exception as e:
            log.error(f"Error formatting due date: {e}")
            due_str = "Invalid"
        return due_str

    def _create_tags_cell(self, tag_names: list[str]) -> Text:
        """Create a formatted text object for tags."""
        tag_text = Text()
        if not tag_names:
            return tag_text

        for i, tag in enumerate(tag_names):
            color = self.tag_colors.get(tag, "$accent")
            tag_text.append(tag, style=color)
            if i < len(tag_names) - 1:
                tag_text.append(", ")

        return tag_text

    def _get_status_style(self, status: str) -> str:
        """Get the style color for a task status."""
        return {
            "due": "$warning",
            "red": "$error",
            "done": "$success",
            "success": "$success",
            "grey": "$text-muted",
            "habit": "$secondary",
            "reward": "$warning",
            "unknown": "$text-disabled",
        }.get(status, "$text-muted")

    def _get_sort_value(self, task: Task) -> Any:
        """Get the sort value for a task, using cache if available."""
        cache_key = (task.id, self.sort_key)
        if cache_key in self._sort_value_cache:
            return self._sort_value_cache[cache_key]

        value = self._calculate_sort_value(task)
        self._sort_value_cache[cache_key] = value
        return value

    def _calculate_sort_value(self, task: Task) -> Any:
        """Calculate the sort value for a task based on the current sort key."""
        key_str = self.sort_key

        if key_str == "status":
            status_order = {"red": 0, "due": 1, "habit": 2, "unknown": 3, "grey": 4, "done": 5, "success": 5}
            status = getattr(task, "_status", "unknown")
            return (status_order.get(status, 99), status)

        elif key_str == "text":
            return getattr(task, "text", "").lower()

        elif key_str == "value":
            return getattr(task, "value", 0.0)

        elif key_str == "priority":
            return getattr(task, "priority", 1.0)

        elif key_str == "due":
            if isinstance(task, Todo) and task.due_date:
                return task.due_date
            if isinstance(task, Daily) and task.next_due:
                return task.next_due[0] if task.next_due else datetime.max.replace(tzinfo=timezone.utc)
            return datetime.max.replace(tzinfo=timezone.utc)

        elif key_str == "tags":
            tag_names = getattr(task, "tag_names", [])
            return tag_names[0].lower() if tag_names else ""

        else:
            return getattr(task, "text", "").lower()

    def _get_current_cursor_row_id(self) -> str | None:
        """Get the ID of the currently selected row."""
        table = self._datatable
        if not table:
            return None

        current_cursor_coordinate = table.cursor_coordinate
        if current_cursor_coordinate and table.is_valid_coordinate(current_cursor_coordinate):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(current_cursor_coordinate)
                return str(cell_key.row_key.value)
            except Exception as e:
                log.warning(f"Could not get row key: {e}")

        return None

    def _restore_cursor_position(self, row_id: str | None) -> None:
        """Restore cursor to previously selected row if possible."""
        table = self._datatable
        if not table or not table.row_count:
            return

        if row_id is not None:
            try:
                new_row_index = table.get_row_index(RowKey(row_id))
                table.move_cursor(row=new_row_index, animate=False)
                return
            except Exception:
                pass

        # Default to first row if can't restore
        table.move_cursor(row=0, animate=False)

    def _invalidate_sort_cache(self) -> None:
        """Clear the sort value cache."""
        self._sort_value_cache = {}
