from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

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

try:
    from ...models.task import Daily, Task, TaskList, Todo
except ImportError:
    Task = dict  # type: ignore
    Todo = dict  # type: ignore
    Daily = dict  # type: ignore
    TaskList = list  # type: ignore
    print("Warning: Could not import Task models in task_list.py")


class ScoreTaskRequest(Message):
    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


class ViewTaskDetailsRequest(Message):
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class TaskListWidget(Widget):
    DEFAULT_CSS = """
    TaskListWidget { height: 100%; width: 100%; }
    Vertical { height: 100%; }
    Select { width: 50%; margin-bottom: 1; }
    Input { dock: top; margin-bottom: 1; }
    DataTable { height: 1fr; border: round $accent; }
    .status-due { color: $warning; }
    .status-red { color: $error; }
    .status-done { color: $success; }
    .status-success { color: $success; }
    .status-grey { color: $text-muted; }
    .status-habit { color: $secondary; }
    """

    _text_filter = reactive("", layout=True)
    _active_task_type = reactive("todo")
    _datatable: Optional[DataTable] = None

    sort_key: Optional[str] = reactive(None)
    sort_ascending: bool = reactive(True)

    tag_colors: Dict[str, str] = {}

    def __init__(self, task_type: Optional[str] = None, id: Optional[str] = None, **kwargs):
        self.task_type_filter = task_type
        widget_id = id or f"task-list-{task_type or 'all'}"
        super().__init__(id=widget_id, **kwargs)

    def compose(self) -> ComposeResult:
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
            self._datatable = DataTable(id="tasks-data-table")
            yield self._datatable

    async def on_mount(self) -> None:
        table = self._datatable
        if not table:
            self.log.error("DataTable instance not found in on_mount!")
            return

        table.cursor_type = "row"
        table.add_column("S", key="status", width=3)
        table.add_column("Task Text", key="text", width=40)
        table.add_column("Value", key="value", width=8)
        table.add_column("Pri", key="priority", width=5)
        table.add_column("Due", key="due", width=12)
        table.add_column("Tags", key="tags")

        self.run_worker(self.load_or_refresh_data, exclusive=True)

    def watch__active_task_type(self, new_type: str) -> None:
        self.run_worker(self.load_or_refresh_data, exclusive=True)

    def watch__text_filter(self, new_filter: str) -> None:
        self.run_worker(self.load_or_refresh_data, exclusive=True)

    @on(Select.Changed, "#task-type-select")
    def handle_type_change(self, event: Select.Changed) -> None:
        self._active_task_type = str(event.value)

    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None:
        self._text_filter = event.value

    async def load_or_refresh_data(self) -> None:
        table = self._datatable
        if not table:
            self.log.error("DataTable instance is None in load_or_refresh_data!")
            return

        current_row_key_value: Optional[str] = None
        current_cursor_coordinate: Optional[Coordinate] = table.cursor_coordinate
        if current_cursor_coordinate and table.is_valid_coordinate(current_cursor_coordinate):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(current_cursor_coordinate)
                current_row_key_value = str(cell_key.row_key.value)
            except Exception as e:
                self.log.warning(f"Could not get row key: {e}")

        table.loading = True
        table.clear()

        filters = {"text_filter": self._text_filter}
        if self.task_type_filter:
            filters["task_type"] = self.task_type_filter

        try:
            task_list_obj: TaskList = self.app.datastore.get_tasks(**filters)
        except Exception as e:
            self.log.error(f"Error getting TaskList: {e}")
            task_list_obj = TaskList([])

        tasks = sorted(
            task_list_obj,
            key=lambda t: getattr(t, self.sort_key, 0) if self.sort_key else t.text,
            reverse=not self.sort_ascending,
        )

        for task in tasks:
            try:
                status = getattr(task, "_status", "unknown")
                value = getattr(task, "value", 0.0)
                priority = getattr(task, "priority", 1.0)
                tag_names = getattr(task, "tag_names", [])

                status_cell = Text("●", style=f"bold {self.get_status_style(status)}")
                task_text = Text.from_markup(task.text)
                due_str = ""

                if isinstance(task, Todo) and task.due_date:
                    due_str = task.due_date.strftime("%Y-%m-%d")
                elif isinstance(task, Daily) and task.next_due:
                    due_str = task.next_due[0].strftime("%Y-%m-%d")

                tag_str = Text()
                for tag in tag_names:
                    color = self.tag_colors.get(tag, "$accent")
                    tag_str.append(f"[{color}]{tag}[/{color}] ")

                table.add_row(
                    status_cell, task_text, str(value), str(priority), due_str, tag_str, key=task.id
                )

            except Exception as e:
                self.log.error(f"Error processing task: {e}")

        table.loading = False
        if current_row_key_value:
            try:
                new_row_index = table.get_row_index(RowKey(current_row_key_value))
                table.move_cursor(row=new_row_index, animate=False)
            except Exception as e:
                self.log.warning(f"Could not restore cursor: {e}")
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
        elif table.row_count > 0:
            table.move_cursor(row=0, animate=False)

    def get_status_style(self, status: str) -> str:
        return {
            "due": "$warning",
            "red": "$error",
            "done": "$success",
            "success": "$success",
            "grey": "$text-muted",
            "habit": "$secondary",
            "reward": "$warning",
        }.get(status, "$text-muted")

    def on_key(self, event: events.Key) -> None:
        table = self._datatable
        if not table:
            return

        cursor_coordinate = table.cursor_coordinate
        if table.row_count and cursor_coordinate and table.is_valid_coordinate(cursor_coordinate):
            try:
                cell_key: CellKey = table.coordinate_to_cell_key(cursor_coordinate)
                task_id = str(cell_key.row_key.value)

                if task_id:
                    if event.key == "+":
                        self.post_message(ScoreTaskRequest(task_id, "up"))
                        event.stop()
                    elif event.key == "-":
                        self.post_message(ScoreTaskRequest(task_id, "down"))
                        event.stop()
            except Exception as e:
                self.log.error(f"Key handler error: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        task_id_key: Optional[RowKey] = event.row_key
        if task_id_key:
            task_id = str(task_id_key.value)
            self.post_message(ViewTaskDetailsRequest(task_id))
