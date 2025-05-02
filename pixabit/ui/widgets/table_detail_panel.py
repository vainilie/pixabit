from typing import ClassVar, Dict, List, Optional

from rich.text import Text
from textual import log, on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static

from pixabit.models.task import Daily, Task, Todo


class CompleteTask(Message):
    """Message to request task completion."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class DeleteTask(Message):
    """Message to request task deletion."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class EditTask(Message):
    """Message to request task editing."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class ScoreTaskDetail(Message):
    """Message to request task scoring."""

    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction


class TaskDetailPanel(Widget):
    """Panel for displaying and interacting with task details."""

    # Reactive attributes
    current_task = reactive(None)
    tag_colors = reactive({})
    _visible = reactive(False)

    # Fields to display in detail panel
    DETAIL_FIELDS: ClassVar[List[str]] = ["text", "status", "value", "priority", "due", "tags", "notes"]
    BINDINGS = [
        ("d", "complete_task", "Complete Task"),
        ("+", "score_up", "Score Up"),
        ("-", "score_down", "Score Down"),
        ("e", "edit_task", "Edit Task"),
        ("x", "delete_task", "Delete Task"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the detail panel layout."""
        with Vertical(id="details-container"):
            # Placeholder when no task is selected
            yield Static("Select a task to view details.", id="task-detail-placeholder")

            # Container for task details
            with Container(id="task-details-content", classes="hidden"):
                # Create Static widgets for each detail field
                for field in self.DETAIL_FIELDS:
                    yield Static("", id=f"task-detail-{field}")

            # Container for action buttons
            with Container(id="task-detail-actions", classes="hidden"):
                with Horizontal():
                    yield Button("Done", id="btn-complete", variant="success")
                    yield Button("+", id="btn-score-up", classes="score-button")
                    yield Button("-", id="btn-score-down", classes="score-button")
                with Horizontal():
                    yield Button("Edit", id="btn-edit", variant="primary")
                    yield Button("Delete", id="btn-delete", variant="error")

    def on_mount(self) -> None:
        """Handle widget mount."""
        self._update_visibility()

    def watch_current_task(self, task: Task | None) -> None:
        """React to changes in the current task."""
        self._visible = task is not None
        if task:
            self._populate_detail_fields(task)
        self._update_visibility()

    def watch_tag_colors(self, tag_colors: dict[str, str]) -> None:
        """React to changes in tag colors."""
        log.debug("Watch: Tag colors changed in detail panel.")
        if self.current_task is not None:
            self._update_tags_display(self.current_task)

    def _update_visibility(self) -> None:
        """Update visibility of container elements based on whether a task is selected."""
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
    def action_complete_task(self) -> None:
        """Complete the current task."""
        if self.current_task:
            log.debug(f"Binding: Complete task ID {self.current_task.id}")
            self.post_message(CompleteTask(str(self.current_task.id)))

    def action_score_up(self) -> None:
        """Score up the current task."""
        if self.current_task:
            log.debug(f"Binding: Score up task ID {self.current_task.id}")
            self.post_message(ScoreTaskDetail(str(self.current_task.id), "up"))

    def action_score_down(self) -> None:
        """Score down the current task."""
        if self.current_task:
            log.debug(f"Binding: Score down task ID {self.current_task.id}")
            self.post_message(ScoreTaskDetail(str(self.current_task.id), "down"))

    def action_edit_task(self) -> None:
        """Edit the current task."""
        if self.current_task:
            log.debug(f"Binding: Edit task ID {self.current_task.id}")
            self.post_message(EditTask(str(self.current_task.id)))

    def action_delete_task(self) -> None:
        """Delete the current task."""
        if self.current_task:
            log.debug(f"Binding: Delete task ID {self.current_task.id}")
            self.post_message(DeleteTask(str(self.current_task.id)))
