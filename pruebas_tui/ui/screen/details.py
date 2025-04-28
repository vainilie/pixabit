from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Switch


class TaskDetailScreen(Screen):
    """Pantalla para mostrar y editar detalles de una tarea."""

    def __init__(self, task_data):
        super().__init__()
        self.task_data = task_data

    def compose(self) -> ComposeResult:
        with Container(id="task-detail-container"):
            yield Label(f"Tarea: {self.task_data['name']}", id="task-title")

            with Container(id="task-form"):
                yield Label("Nombre:")
                yield Input(value=self.task_data["name"], id="task-name")

                yield Label("Descripción:")
                yield Input(value=self.task_data.get("description", ""), id="task-description", classes="input-multiline")

                with Horizontal():
                    yield Label("Tipo:")
                    yield Select([(type_val, type_val) for type_val in ["Diario", "Hábito", "ToDo"]], value=self.task_data["type"], id="task-type")

                with Horizontal():
                    yield Label("Dificultad:")
                    yield Select([(diff, diff) for diff in ["Trivial", "Fácil", "Media", "Difícil"]], value=self.task_data["difficulty"], id="task-difficulty")

                with Horizontal():
                    yield Label("Estado:")
                    yield Select([(status, status) for status in ["Pendiente", "En progreso", "Completada"]], value=self.task_data["status"], id="task-status")

                with Horizontal():
                    yield Label("Con fecha:")
                    yield Switch(value=False, id="task-dated")

                with Horizontal(id="date-container", classes="hidden"):
                    yield Label("Fecha límite:")
                    yield Input(placeholder="YYYY-MM-DD", id="task-date")

                yield Label("Etiquetas:")
                with Container(id="task-tags"):
                    with Horizontal(classes="tags-container"):
                        yield Button("Trabajo", classes="tag-button")
                        yield Button("Salud", classes="tag-button")
                        yield Button("Personal", classes="tag-button")
                    with Horizontal(classes="tags-container"):
                        yield Button("Proyectos", classes="tag-button")
                        yield Button("Urgente", classes="tag-button")

                with Horizontal(id="action-buttons"):
                    yield Button("Guardar", variant="primary", id="save-task")
                    yield Button("Completar", variant="success", id="complete-task")
                    yield Button("Eliminar", variant="error", id="delete-task")
                    yield Button("Cancelar", id="cancel-task")

    @on(Switch.Changed, "#task-dated")
    def toggle_date_field(self, event: Switch.Changed) -> None:
        date_container = self.query_one("#date-container")
        if event.value:
            date_container.remove_class("hidden")
        else:
            date_container.add_class("hidden")

    @on(Button.Pressed, "#save-task")
    def save_task(self) -> None:
        # Aquí iría la lógica para guardar los cambios
        self.app.notify("Tarea guardada")
        self.app.pop_screen()

    @on(Button.Pressed, "#complete-task")
    def complete_task(self) -> None:
        # Aquí iría la lógica para marcar como completada
        self.app.notify("¡Tarea completada!")
        self.app.pop_screen()

    @on(Button.Pressed, "#delete-task")
    def delete_task(self) -> None:
        # Aquí iría la lógica para eliminar
        self.app.notify("Tarea eliminada")
        self.app.pop_screen()

    @on(Button.Pressed, "#cancel-task")
    def cancel_edit(self) -> None:
        self.app.pop_screen()

    class Meta:
        css = """
        #task-detail-container {
            width: 100%;
            height: 100%;
            padding: 1 2;
        }

        #task-title {
            text-style: bold;
            background: $boost;
            width: 100%;
            height: 3;
            content-align: center middle;
        }

        #task-form {
            margin: 1 0;
        }

        .input-multiline {
            height: 5;
        }

        #action-buttons {
            margin-top: 2;
        }

        .hidden {
            display: none;
        }

        .tags-container {
            margin: 1 0;
        }

        .tag-button {
            margin-right: 1;
            background: $accent-darken-2;
        }
        """
