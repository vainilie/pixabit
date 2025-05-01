from typing import Any, ClassVar, Dict, List, Optional

from rich.panel import Panel
from rich.text import Text
from textual import log, on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static

# Import the Task model (or dummy Task if models are not available)
try:
    from ...models.task import Daily, Task, Todo
except ImportError:
    # Define dummy types similar to task_list.py if models are not available
    class Task:
        def __init__(self, id="dummy", text="Dummy Task", _status="unknown", value=1.0, priority=1.0, tag_names=None, notes=""):
            self.id = id
            self.text = text
            self._status = _status
            self.value = value
            self.priority = priority
            self.tag_names = tag_names or []
            self.notes = notes
            self.styled = Text(text)  # Para compatibilidad con lógica previa

        def __repr__(self) -> str:
            return f"<DummyTask id={self.id} text='{self.text[:15]}...'>"

    class Todo(Task):
        def __init__(self, id="dummy_todo", text="Dummy Todo", _status="unknown", value=1.0, priority=1.0, tag_names=None, due_date=None, notes=""):
            super().__init__(id, text, _status, value, priority, tag_names, notes)
            self.due_date = due_date  # Should be datetime

    class Daily(Task):
        def __init__(self, id="dummy_daily", text="Dummy Daily", _status="unknown", value=1.0, priority=1.0, tag_names=None, next_due=None, notes=""):
            super().__init__(id, text, _status, value, priority, tag_names, notes)
            self.next_due = next_due  # Debe ser lista de datetimes

    TaskList = list  # Asume que TaskList es una lista de objetos Task

    log.warning("Could not import Task models in task_detail_panel.py. Using dummy types.")


# --- Mensajes para Acciones ---
from textual.message import Message


class CompleteTask(Message):
    """Mensaje publicado cuando se presiona el botón de completar."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class DeleteTask(Message):
    """Mensaje publicado cuando se presiona el botón de eliminar."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class EditTask(Message):
    """Mensaje publicado cuando se presiona el botón de editar."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class ScoreTaskDetail(Message):
    """Mensaje publicado cuando se presionan los botones de puntuación en la vista de detalle."""

    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


class TaskDetailPanel(Widget):
    """Muestra los detalles de una tarea seleccionada y proporciona botones de acción."""

    # Reactivos
    current_task = reactive(None)
    tag_colors = reactive({})

    # Constantes de clase para reutilizar
    DETAIL_FIELDS: ClassVar[List[str]] = ["text", "status", "value", "priority", "due", "tags", "notes"]

    # Estado para seguimiento interno
    _visible = reactive(False)

    def compose(self) -> ComposeResult:
        with Vertical(id="details-container"):
            yield Static("Select a task to view details.", id="task-detail-placeholder")

            with Container(id="task-details-content", classes="hidden"):
                for field in self.DETAIL_FIELDS:
                    yield Static("", id=f"task-detail-{field}")

            with Container(id="task-detail-actions", classes="hidden"):
                with Horizontal():
                    yield Button("Done", id="btn-complete", variant="success")
                    yield Button("+", id="btn-score-up", classes="score-button")
                    yield Button("-", id="btn-score-down", classes="score-button")
                with Horizontal():
                    yield Button("Edit", id="btn-edit", variant="primary")
                    yield Button("Delete", id="btn-delete", variant="error")

    def on_mount(self) -> None:
        """Configura el estado inicial cuando el widget se monta."""
        self._update_visibility()

    def watch_current_task(self, task: Task | None) -> None:
        """Actualiza los detalles mostrados cuando cambia la tarea seleccionada."""
        self._visible = task is not None
        if task:
            self._populate_detail_fields(task)
        self._update_visibility()

    def watch_tag_colors(self, tag_colors: dict[str, str]) -> None:
        """Se llama cuando cambian los colores de las etiquetas."""
        log.debug("Watch: Tag colors changed in detail panel.")
        # Si hay una tarea mostrada actualmente, actualiza su renderizado de etiquetas
        if self.current_task is not None:
            self._update_tags_display(self.current_task)

    def _update_visibility(self) -> None:
        """Actualiza la visibilidad de los contenedores basándose en si hay una tarea seleccionada."""
        placeholder = self.query_one("#task-detail-placeholder", Static)
        content = self.query_one("#task-details-content", Container)
        actions = self.query_one("#task-detail-actions", Container)

        if self._visible:
            placeholder.add_class("hidden")
            content.remove_class("hidden")
            actions.remove_class("hidden")
        else:
            placeholder.remove_class("hidden")
            content.add_class("hidden")
            actions.add_class("hidden")

    def _populate_detail_fields(self, task: Task) -> None:
        """Llena todos los campos de detalle con los datos de la tarea."""
        # Actualiza el campo de texto
        self._get_detail_field("text").update(f"[b]Task:[/b] {Text.from_markup(getattr(task, 'text', ''))}")

        # Actualiza el campo de estado
        self._get_detail_field("status").update(f"[b]Status:[/b] {getattr(task, '_status', 'unknown')}")

        # Actualiza los campos de valor y prioridad con formato
        self._get_detail_field("value").update(f"[b]Value:[/b] {getattr(task, 'value', 0.0):.1f}")
        self._get_detail_field("priority").update(f"[b]Priority:[/b] {getattr(task, 'priority', 1.0):.1f}")

        # Actualiza la fecha de vencimiento con manejo de errores mejorado
        self._update_due_date_display(task)

        # Actualiza las etiquetas
        self._update_tags_display(task)

        # Actualiza las notas
        self._get_detail_field("notes").update(f"[b]Notes:[/b]\n{getattr(task, 'notes', '')}")

    def _update_due_date_display(self, task: Task) -> None:
        """Actualiza la visualización de la fecha de vencimiento con manejo de errores mejorado."""
        due_str = "None"
        try:
            import datetime

            if isinstance(task, Todo) and hasattr(task, "due_date") and task.due_date:
                due_str = task.due_date.strftime("%Y-%m-%d")
            elif isinstance(task, Daily) and hasattr(task, "next_due") and task.next_due:
                if isinstance(task.next_due, list) and task.next_due:
                    due_str = task.next_due[0].strftime("%Y-%m-%d")
                elif hasattr(task.next_due, "strftime"):
                    due_str = task.next_due.strftime("%Y-%m-%d")
        except Exception as e:
            log.error(f"Error formatting due date: {e}")
            due_str = "Invalid Date"

        self._get_detail_field("due").update(f"[b]Due:[/b] {due_str}")

    def _update_tags_display(self, task: Task) -> None:
        """Actualiza la visualización de las etiquetas usando los colores de etiquetas actuales."""
        tag_names = getattr(task, "tag_names", [])
        tag_text = Text()

        if tag_names:
            for i, tag in enumerate(tag_names):
                color = self.tag_colors.get(tag, "$accent")
                tag_text.append(f"[{color}]{tag}[/{color}]")
                if i < len(tag_names) - 1:
                    tag_text.append(", ")
        else:
            tag_text.append("None")

        self._get_detail_field("tags").update(Text.assemble("[b]Tags:[/b] ", tag_text))

    def _get_detail_field(self, field_name: str) -> Static:
        """Obtiene un campo de detalle por nombre con manejo de errores."""
        try:
            return self.query_one(f"#task-detail-{field_name}", Static)
        except NoMatches:
            log.error(f"Detail field '{field_name}' not found")
            # Crear un campo de respaldo para evitar errores
            static = Static(f"Error: Missing '{field_name}' field")
            return static

    # --- Manejadores de Eventos de Botones ---
    @on(Button.Pressed, "#btn-complete")
    def on_complete_button_pressed(self) -> None:
        """Manejador para el botón de completar."""
        if self.current_task:
            log.debug(f"Complete button pressed for task ID: {self.current_task.id}")
            self.post_message(CompleteTask(str(self.current_task.id)))

    @on(Button.Pressed, ".score-button")
    def on_score_button_pressed(self, event: Button.Pressed) -> None:
        """Manejador para los botones de puntuación."""
        if self.current_task:
            direction = "up" if event.button.id == "btn-score-up" else "down"
            log.debug(f"Score button '{direction}' pressed for task ID: {self.current_task.id}")
            self.post_message(ScoreTaskDetail(str(self.current_task.id), direction))

    @on(Button.Pressed, "#btn-edit")
    def on_edit_button_pressed(self) -> None:
        """Manejador para el botón de editar."""
        if self.current_task:
            log.debug(f"Edit button pressed for task ID: {self.current_task.id}")
            self.post_message(EditTask(str(self.current_task.id)))

    @on(Button.Pressed, "#btn-delete")
    def on_delete_button_pressed(self) -> None:
        """Manejador para el botón de eliminar."""
        if self.current_task:
            log.debug(f"Delete button pressed for task ID: {self.current_task.id}")
            self.post_message(DeleteTask(str(self.current_task.id)))
