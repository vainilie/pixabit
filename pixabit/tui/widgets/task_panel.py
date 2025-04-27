# pixabit/tui/widgets/task_list.py

# SECTION: MODULE DOCSTRING
"""Defines the TaskListWidget for displaying and interacting with Habitica tasks."""

# SECTION: IMPORTS
import asyncio  # Might be needed if refresh is async
from typing import Any, Dict, List, Optional, Tuple

from pixabit.models.task import Daily, Reward, Task, TaskList, Todo
from rich.text import Text  # For potential styling within cells
from textual import events, on  # Ensure 'on' decorator is imported

# Textual Imports
from textual.app import ComposeResult
from textual.containers import Vertical  # To hold Table and maybe Input
from textual.coordinate import Coordinate
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (  # Ensure Input is here
    DataTable,
    Input,
    Markdown,
    Select,
    Static,
)
from textual.widgets._data_table import (  # Import keys
    CellKey,
    ColumnKey,
    RowKey,
)

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
    """A widget to display Habitica tasks in a DataTable."""

    DEFAULT_CSS = """
    TaskListWidget { height: 100%; width: 100%; }
    Vertical { height: 100%; }
    Select { width: 50%; margin-bottom: 1; } /* Estilo para Select */
    Input { dock: top; margin-bottom: 1; }
    DataTable { height: 1fr; border: round $accent; }
    /* ... status cell styles ... */
    /* Styling for cells based on status (optional) */
    .status-due { color: $warning; }
    .status-red { color: $error; }
    .status-done { color: $success; }
    .status-success { color: $success; }
    .status-grey { color: $text-muted; }
    .status-habit { color: $secondary; }
    """
    current_sorts: set = set()

    # Reactive variable to trigger refresh when filter changes
    _text_filter = reactive("", layout=True)
    _datatable: DataTable | None = None

    # Store the base task type this instance should display (e.g., "todo", "daily")
    # This is passed during initialization
    _active_task_type = reactive("todo")  # Empieza mostrando TODOs

    # FUNC: __init__
    def __init__(
        self,
        task_type: str | None = None,
        id: str | None = None,
        **kwargs,
    ):
        """Initialize the TaskListWidget.

        Args:
            task_type: The type of tasks this widget should display by default (e.g., 'todo', 'daily').
            id: The widget ID.
            **kwargs: Additional keyword arguments.
        """
        # Store the task type filter BEFORE calling super().__init__
        self._active_task_type = task_type or "todo"
        # Construct the ID based on the task type if not provided
        widget_id = id or f"task-list-{task_type or 'all'}"
        super().__init__(id=widget_id, **kwargs)

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create child widgets: Input for filtering and DataTable."""
        with Vertical():
            # --- Añadir widget de selección ---
            yield Select(
                options=[  # (Label, Value)
                    ("Todos", "todo"),
                    ("Dailies", "daily"),
                    ("Habits", "habit"),
                    ("Rewards", "reward"),
                    ("All", "all"),  # Opción para ver todas
                ],
                value=self._active_task_type,  # Valor inicial
                id="task-type-select",
                allow_blank=False,
            )
            # --- Fin añadir widget ---# Use Vertical to stack Input and DataTable
            yield Input(
                placeholder="Filter tasks by text...", id="task-filter-input"
            )
            self._datatable = DataTable(id="tasks-data-table")
            yield self._datatable

    # FUNC: on_mount
    async def on_mount(self) -> None:
        self.log("Mounting TaskListWidget...")
        # --- Use the stored reference ---
        table = self._datatable
        if not table:
            self.log.error("DataTable instance not found in on_mount!")
            return  # Cannot proceed
        # --- END Use reference ---

        table.cursor_type = "row"
        table.add_column("S", key="status", width=3)
        table.add_column("Task Text", key="text", width=10)
        table.add_column("Value", key="value", width=8)
        table.add_column("Pri", key="priority", width=5)
        table.add_column("Due", key="due", width=12)
        table.add_column("Tags", key="tags")

        self.run_worker(
            self.load_or_refresh_data, exclusive=True
        )  # Carga inicial

    # Observador para el filtro de tipo
    def watch__active_task_type(self, new_type: str) -> None:
        select = self.query_one("#task-type-select", Select)
        select.value = new_type

        self.run_worker(self.load_or_refresh_data, exclusive=True)

    # Observador para el filtro de texto
    def watch__text_filter(self, new_filter: str) -> None:
        self.run_worker(self.load_or_refresh_data, exclusive=True)

    # Manejador para el cambio en el Select
    @on(Select.Changed, "#task-type-select")
    def handle_type_change(self, event: Select.Changed) -> None:
        self.log(f"Task type filter changed to: {event.value}")
        self._active_task_type = str(event.value)  # Actualiza estado reactivo

    # Manejador para el cambio en el Input
    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None:
        self._text_filter = event.value

    async def load_or_refresh_data(self) -> None:
        # await asyncio.sleep(0) # Remove or keep commented out

        # --- Use the stored reference ---
        table = self._datatable
        if not table:
            self.log.error(
                "DataTable instance is None in load_or_refresh_data!"
            )
            return
        # --- END Use reference ---

        self.log("TaskListWidget: Refreshing...")  # Simplified log
        # ... (get current_row_key_value using 'table' reference) ...
        current_row_key_value: str | None = None
        current_cursor_coordinate: Coordinate | None = table.cursor_coordinate

        if current_cursor_coordinate is not None and table.is_valid_coordinate(
            current_cursor_coordinate
        ):
            try:
                # --- Use coordinate_to_cell_key ---
                cell_key: CellKey = table.coordinate_to_cell_key(
                    current_cursor_coordinate
                )
                current_row_key_value = str(cell_key.row_key.value)
                self.log(
                    f"Saved current row key value: {current_row_key_value}"
                )
            except (KeyError, Exception) as e:
                self.log.warning(
                    f"Could not get row key for coordinate {current_cursor_coordinate}: {e}"
                )
                current_row_key_value = None

        table.loading = True
        table.clear()

        # Prepare filters
        data_filters = {"text_filter": self._text_filter}
        if self._active_task_type:
            data_filters["task_type"] = self.task_type_filter

        # --- Obtiene el objeto TaskList del DataStore ---
        try:
            # --- CORREGIDO: El tipo es TaskList ---
            task_list_obj: TaskList = self.app.datastore.get_tasks(
                **data_filters
            )
            # --- FIN CORRECCIÓN ---
            self.log(
                f"Received TaskList with {len(task_list_obj)} tasks from DataStore for {self.id}"
            )
        except Exception as e:
            self.log.error(f"Error getting TaskList from datastore: {e}")
            task_list_obj = TaskList(
                []
            )  # Usa una TaskList vacía en caso de error

        # Prepara filas iterando sobre la TaskList
        rows: list[Tuple] = []
        # --- El bucle FOR funciona porque TaskList es iterable ---
        for task in task_list_obj:
            try:
                # La lógica interna para extraer datos de 'task' (que es un objeto Task)
                # y formatear la fila sigue siendo la misma.
                status = getattr(task, "_status", "unknown")
                text = task.text
                value = getattr(task, "value", 0.0)
                priority = getattr(task, "priority", 1.0)
                tag_str = ", ".join(getattr(task, "tag_names", []))
                due_str = ""
                if isinstance(task, Todo) and task.due_date:
                    due_str = task.due_date.strftime("%Y-%m-%d")
                elif isinstance(task, Daily) and task.next_due:
                    due_str = task.next_due[0].strftime("%Y-%m-%d")

                # Determine status icon/style (Example)
                # status_icon = " ?"
                # status_color = "$text-muted"  # Default color
                # if status == "due":
                #     status_icon = "⏳"
                #     status_color = "$warning"
                # elif status == "red":
                #     status_icon = "❗"
                #     status_color = "$error"
                # elif status == "done" or status == "success":
                #     status_icon = "✅"
                #     status_color = "$success"
                # elif status == "grey":
                #     status_icon = "➖"
                #     status_color = "$text-muted"  # Ensure dim maps correctly
                # elif status == "habit":
                #     status_icon = "🔄"
                #     status_color = "$secondary"  # Example color
                # elif status == "reward":
                #     status_icon = "⭐"
                #     status_color = "$warning"  # Example color

                # Crear objeto Text con estilo dinámico
                # status_cell = Text(status_icon, style=f"bold {status_color}")
                # Asegúrate que el orden y número de elementos coincida con las columnas definidas en on_mount
                content = (
                    str(task._status),
                    str(task.text),
                    str(task.value),
                    str(task.priority),
                    ", ".join(task.tag_names),
                    due_str,
                )
                table.add_row(*content, key=task.id)  # task.id es la key
                # Apply overflow/nowrap here  # Apply overflow/nowrap here  # ID al final para la clave
            except Exception as e:
                self.log.error(
                    f"Error processing task {getattr(task, 'id', 'N/A')} for table: {e}"
                )

        # Añadir filas (key es el último elemento de la tupla 'row')
        table.loading = False
        self.log(f"Table {self.id} updated with {len(rows)} rows.")

        # --- Restore cursor position using the saved KEY VALUE ---
        if current_row_key_value is not None:
            try:
                new_row_index = table.get_row_index(
                    RowKey(current_row_key_value)
                )  # Find new index by value
                table.move_cursor(row=new_row_index, animate=False)
                self.log(
                    f"Restored cursor to row index {new_row_index} for key {current_row_key_value}"
                )
            except KeyError:
                self.log.warning(
                    f"Could not find row key '{current_row_key_value}' after refresh. Resetting cursor."
                )
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
            except Exception as e:
                self.log.error(f"Error restoring cursor: {e}")
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
        elif table.row_count > 0:
            table.move_cursor(
                row=0, animate=False
            )  # Move to top if no previous cursor

    # --- Event Handlers ---

    # FUNC: on_key
    def on_key(self, event: events.Key) -> None:
        # --- Use the stored reference ---
        table = self._datatable
        if not table:
            return
        # --- END Use reference ---

        cursor_coordinate: Coordinate | None = table.cursor_coordinate
        if (
            table.row_count > 0
            and cursor_coordinate is not None
            and table.is_valid_coordinate(cursor_coordinate)
        ):
            try:
                # --- Use coordinate_to_cell_key ---
                cell_key: CellKey = table.coordinate_to_cell_key(
                    cursor_coordinate
                )
                task_id = str(
                    cell_key.row_key.value
                )  # Extract string value from RowKey
                # --- END USE ---

                if task_id:
                    if event.key == "+":
                        self.post_message(ScoreTaskRequest(task_id, "up"))
                        self.log(f"Posted score up request for {task_id}")
                        event.stop()
                    elif event.key == "-":
                        self.post_message(ScoreTaskRequest(task_id, "down"))
                        self.log(f"Posted score down request for {task_id}")
                        event.stop()
                        # ... other key checks ...
            except (KeyError, Exception) as e:  # Catch potential errors
                self.log.error(
                    f"Error getting row key or handling key press: {e}"
                )

    # --- on_data_table_row_selected remains the same ---
    # (event.row_key directly gives the RowKey object)
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # --- CORRECTED WAY TO GET KEY ---
        # event.row_key ALREADY IS the RowKey object
        task_id_key: RowKey | None = event.row_key
        if task_id_key is not None:
            task_id = str(task_id_key.value)  # Extract the task ID string
            self.log(f"Row selected, task ID: {task_id}")
            self.post_message(ViewTaskDetailsRequest(task_id))
