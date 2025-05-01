import asyncio
import datetime
import logging
from datetime import timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytz
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.reactive import computed, reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Select
from textual.widgets._data_table import CellKey, ColumnKey, RowKey

from pixabit.helpers._logger import log
from pixabit.helpers._md_to_rich import MarkdownRenderer
from pixabit.models.task import Daily, Task, Todo

# Initialize markdown renderer
md_renderer = MarkdownRenderer.markdown_to_rich_text()


# Define message classes for events
class ScoreTaskRequest(Message):
    """Message sent when user wants to score a task up or down."""

    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


class ViewTaskDetailsRequest(Message):
    """Message sent when user wants to view task details."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class TaskListWidget(Widget):
    """Widget that displays a filterable, sortable list of tasks."""

    # Reactive attributes
    _text_filter = reactive("", layout=True)
    _active_task_type = reactive("todo")
    sort_key = reactive(None)
    sort_ascending = reactive(True)
    tag_colors = reactive({})

    # Non-reactive attributes
    _datatable = None
    _tasks = []
    _sort_value_cache = {}

    def __init__(
        self,
        task_type: str | None = None,
        id: str | None = None,
        **kwargs,
    ):
        """Initialize the TaskListWidget.

        Args:
            task_type: Initial task type filter
            id: Widget ID (optional)
        """
        self.task_type_filter = task_type
        widget_id = id or f"task-list-{task_type or 'all'}"
        super().__init__(id=widget_id, **kwargs)

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Vertical():
            yield Select(
                options=[
                    ("Todos", "todo"),
                    ("Dailies", "daily"),
                    ("Habits", "habit"),
                    ("Rewards", "reward"),
                    ("All", "all"),
                ],
                value=self._active_task_type,
                id="task-type-select",
                allow_blank=False,
            )
            yield Input(placeholder="Filter tasks by text...", id="task-filter-input")
            self._datatable = DataTable(id="tasks-data-table", cursor_type="row", zebra_stripes=True)
            self._datatable.add_column("S", key="status", width=3)
            self._datatable.add_column("Task Text", key="text", width=40)
            self._datatable.add_column("Value", key="value", width=8)
            self._datatable.add_column("Pri", key="priority", width=5)
            self._datatable.add_column("Due", key="due", width=12)
            self._datatable.add_column("Tags", key="tags")
            yield self._datatable

    async def on_mount(self) -> None:
        """Handle widget mounting."""
        log.info(f"Mounting TaskListWidget {self.id}...")
        if not self._datatable:
            log.error("DataTable instance not found in on_mount!")
            return

        self.run_worker(
            self.load_or_refresh_data,
            exclusive=True,
            name=f"load_{self.id}",
            group="load_tasks",
        )

    # Reactive watchers
    def watch__active_task_type(self, new_type: str) -> None:
        """React to task type filter changes."""
        log.info(f"Watch: _active_task_type changed to {new_type}")
        self.run_worker(self.load_or_refresh_data, name=f"filter_type_{self.id}", group="load_tasks", exclusive=True)

    def watch__text_filter(self, new_filter: str) -> None:
        """React to text filter changes."""
        log.info(f"Watch: _text_filter changed to '{new_filter}'")
        self.run_worker(
            self.load_or_refresh_data,
            name=f"filter_text_{self.id}",
            group="load_tasks",
            exclusive=True,
        )

    def watch_tag_colors(self, new_colors: dict[str, str]) -> None:
        """React to tag color changes."""
        log.info("Watch: Tag colors changed. Re-sorting/displaying tasks.")
        self._invalidate_sort_cache()
        self.sort_and_display_tasks()

    @computed("_tasks", "sort_key", "sort_ascending")
    def sorted_tasks(self) -> list[Task]:
        """Compute sorted tasks based on current sort settings."""
        if not self._tasks or not self.sort_key:
            return self._tasks
        return self.sort_tasks(self._tasks)

    def watch_sorted_tasks(self) -> None:
        """React to changes in the sorted tasks list."""
        self.update_table_data(self.sorted_tasks)

    # Event handlers
    @on(Select.Changed, "#task-type-select")
    def handle_type_change(self, event: Select.Changed) -> None:
        """Handle task type selection changes."""
        log.info(f"Select.Changed: Task type filter changed to: {event.value}")
        self._active_task_type = str(event.value)

    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None:
        """Handle text filter changes."""
        log.info(f"Input.Changed: Text filter changed to: '{event.value}'")
        self._text_filter = event.value

    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected):
        """Handle column header selection for sorting."""
        table = self._datatable
        if not table:
            return

        column_key = event.column_key
        try:
            column_string_key = str(column_key.value)
            sortable_keys = ["status", "text", "value", "priority", "due", "tags"]

            if column_string_key not in sortable_keys:
                log.warning(f"Column key '{column_string_key}' is not configured for sorting.")
                return

            if column_string_key == self.sort_key:
                self.sort_ascending = not self.sort_ascending
            else:
                self.sort_key = column_string_key
                self.sort_ascending = True

            log.info(f"Sorting state updated: key={self.sort_key}, ascending={self.sort_ascending}")
            self._invalidate_sort_cache()
            self.sort_and_display_tasks()
        except KeyError:
            log.warning(f"Attempted to sort by invalid or non-existent column key: {column_key}")
        except Exception as e:
            log.error(f"Error during header selection sorting: {e}")

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard events for scoring tasks."""
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
                        log.info(f"Key '+': Posting ScoreTaskRequest up for task ID {task_id}")
                        self.post_message(ScoreTaskRequest(task_id, "up"))
                        event.stop()
                    elif event.key == "-":
                        log.info(f"Key '-': Posting ScoreTaskRequest down for task ID {task_id}")
                        self.post_message(ScoreTaskRequest(task_id, "down"))
                        event.stop()
            except (KeyError, Exception) as e:
                log.error(f"Key handler error: {e}")

    @on(DataTable.RowSelected)
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to view task details."""
        task_id_key: RowKey | None = event.row_key
        if task_id_key is not None:
            task_id = str(task_id_key.value)
            log.info(f"DataTable.RowSelected: Row selected, task ID: {task_id}")
            self.post_message(ViewTaskDetailsRequest(task_id))

    # Data manipulation methods
    async def load_or_refresh_data(self) -> None:
        """Load or refresh task data from the datastore."""
        table = self._datatable
        if not table:
            log.error("DataTable instance is None in load_or_refresh_data!")
            return

        log.info(f"TaskListWidget ({self.id}): Refreshing. Type='{self._active_task_type}', Text='{self._text_filter}'")

        # Save current cursor position
        current_row_id = self._get_current_cursor_row_id()

        # Prepare loading state
        table.loading = True
        table.clear()
        self._tasks = []
        self._invalidate_sort_cache()

        # Prepare data filters
        data_filters = {"text_filter": self._text_filter}
        active_type = self._active_task_type
        if active_type and active_type != "all":
            data_filters["task_type"] = active_type

        try:
            # Fetch tasks from datastore
            fetched_tasks = await self.app.run_in_thread(self.app.datastore.get_tasks, **data_filters)
            log.info(f"Received {len(fetched_tasks)} tasks (type: {active_type}, text: '{self._text_filter}') from DataStore.")
            self._tasks = fetched_tasks
        except Exception as e:
            log.error(f"Error getting list[Task] from datastore: {e}")
            self._tasks = []

        # Sort and display tasks
        self.sort_and_display_tasks()

        # Restore loading state and cursor position
        table.loading = False
        self._restore_cursor_position(current_row_id)

    def update_table_data(self, tasks: list[Task]) -> None:
        """Update the table with new task data efficiently."""
        table = self._datatable
        if not table:
            return

        # Save current cursor position
        current_row_id = self._get_current_cursor_row_id()

        # Find rows to add, update, or remove
        current_rows = {str(key.value) for key in table.rows.keys()}
        new_rows = {task.id for task in tasks}
        to_add = new_rows - current_rows
        to_remove = current_rows - new_rows
        to_update = new_rows & current_rows

        # Remove rows no longer needed
        for row_id in to_remove:
            table.remove_row(RowKey(row_id))

        # Update existing rows
        for task in tasks:
            if task.id in to_update:
                self._update_row_data(table, task)

        # Add new rows
        for task in tasks:
            if task.id in to_add:
                self._add_row_for_task(table, task)

        # Restore cursor position
        self._restore_cursor_position(current_row_id)

    def sort_and_display_tasks(self):
        """Sort tasks and update the display."""
        table = self._datatable
        if not table:
            return

        log.info(f"sort_and_display_tasks: Starting. Row count before clear: {table.row_count}. " f"Sorting key: {self.sort_key}, ascending: {self.sort_ascending}")

        table.clear()

        # Sort tasks
        sorted_tasks = self._tasks
        if self.sort_key is not None:
            try:
                sorted_tasks = sorted(self._tasks, key=lambda task: self._get_sort_value(task), reverse=not self.sort_ascending)
                log.info(f"Sorted tasks by '{self.sort_key}', ascending={self.sort_ascending}")
            except Exception as e:
                log.error(f"Error sorting tasks by key '{self.sort_key}': {e}")
                sorted_tasks = self._tasks

        # Add rows to table
        added_row_count = 0
        for task in sorted_tasks:
            try:
                self._add_row_for_task(table, task)
                added_row_count += 1
            except Exception as e:
                task_id_for_log = getattr(task, "id", "N/A")
                task_text_for_log = getattr(task, "text", "N/A")
                log.error(f"Error processing task {task_id_for_log} ('{task_text_for_log}') for row: {e}")

        log.info(f"sort_and_display_tasks: Finished. Final row count: {table.row_count}")

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks based on current sort key and direction."""
        if not self.sort_key:
            return tasks

        try:
            return sorted(tasks, key=lambda task: self._get_sort_value(task), reverse=not self.sort_ascending)
        except Exception as e:
            log.error(f"Error during sorting operation: {e}")
            return tasks

    # Helper methods
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
                log.warning(f"Could not get row key for coordinate {current_cursor_coordinate}: {e}")

        return None

    def _restore_cursor_position(self, row_id: str | None) -> None:
        """Restore cursor to a specific row ID or default to first row."""
        table = self._datatable
        if not table or not table.row_count:
            return

        if row_id is not None:
            try:
                new_row_index = table.get_row_index(RowKey(row_id))
                table.move_cursor(row=new_row_index, animate=False)
                log.info(f"Restored cursor to row index {new_row_index} for key {row_id}")
                return
            except KeyError:
                log.warning(f"Could not find row key '{row_id}' after refresh. Resetting cursor.")
            except Exception as e:
                log.error(f"Error restoring cursor: {e}")

        # Default to first row if specific row not found
        table.move_cursor(row=0, animate=False)

    def _add_row_for_task(self, table: DataTable, task: Task) -> None:
        """Add a row to the table for a task."""
        try:
            # Get task properties
            status = getattr(task, "_status", "unknown")
            value = getattr(task, "value", 0.0)
            priority = getattr(task, "priority", 1.0)
            tag_names = getattr(task, "tag_names", [])
            task_id = getattr(task, "id", f"no-id-{id(task)}")

            # Create cell contents
            status_cell = Text("●", style=f"bold {self._get_status_style(status)}")
            task_text = Text.from_markup(getattr(task, "text", ""))
            due_str = self._format_due_date(task)
            tag_str = self._create_tags_cell(tag_names)

            # Add row to table
            table.add_row(
                status_cell,
                task_text,
                str(value),
                str(priority),
                due_str,
                tag_str,
                key=str(task_id),
            )
        except Exception as e:
            log.error(f"Error adding row for task {getattr(task, 'id', 'N/A')}: {e}")

    def _update_row_data(self, table: DataTable, task: Task) -> None:
        """Update an existing row with new task data."""
        try:
            # Get task properties
            status = getattr(task, "_status", "unknown")
            value = getattr(task, "value", 0.0)
            priority = getattr(task, "priority", 1.0)
            tag_names = getattr(task, "tag_names", [])
            task_id = getattr(task, "id", None)

            if task_id is None:
                return

            # Create cell contents
            status_cell = Text("●", style=f"bold {self._get_status_style(status)}")
            task_text = Text.from_markup(getattr(task, "text", ""))
            due_str = self._format_due_date(task)
            tag_str = self._create_tags_cell(tag_names)

            # Update row in table
            table.update_cell(RowKey(str(task_id)), ColumnKey("status"), status_cell)
            table.update_cell(RowKey(str(task_id)), ColumnKey("text"), task_text)
            table.update_cell(RowKey(str(task_id)), ColumnKey("value"), str(value))
            table.update_cell(RowKey(str(task_id)), ColumnKey("priority"), str(priority))
            table.update_cell(RowKey(str(task_id)), ColumnKey("due"), due_str)
            table.update_cell(RowKey(str(task_id)), ColumnKey("tags"), tag_str)
        except Exception as e:
            log.error(f"Error updating row for task {task_id}: {e}")

    def _format_due_date(self, task: Task) -> str:
        """Format the due date for display in the table."""
        due_str = ""
        try:
            if isinstance(task, Todo) and task.due_date:
                due_str = task.due_date.astimezone(pytz.timezone("UTC")).strftime("%Y-%m-%d")
            elif isinstance(task, Daily) and task.next_due and task.next_due[0]:
                due_str = task.next_due[0].astimezone(pytz.timezone("UTC")).strftime("%Y-%m-%d")
        except Exception as e:
            log.error(f"Error formatting due date for task {getattr(task, 'id', 'N/A')}: {e}")
            due_str = "Invalid Date"

        return due_str

    def _create_tags_cell(self, tag_names: list[str]) -> Text:
        """Create a Text object for displaying tags with colors."""
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
        """Get the color style for a status indicator."""
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
        """Get the sort value for a task, with caching."""
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
                return task.next_due[0] if task.next_due else datetime.datetime.max.replace(tzinfo=timezone.utc)
            return datetime.datetime.max.replace(tzinfo=timezone.utc)

        elif key_str == "tags":
            tag_names = getattr(task, "tag_names", [])
            return tag_names[0].lower() if tag_names else ""

        else:
            log.warning(f"Unknown sort key '{key_str}', sorting by text.")
            return getattr(task, "text", "").lower()

    def _invalidate_sort_cache(self) -> None:
        """Clear the sort value cache."""
        self._sort_value_cache = {}
