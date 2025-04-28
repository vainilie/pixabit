import random

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Digits, Footer, Header, Input, Label, ProgressBar, Select, Static, Switch, TabbedContent, TabPane, Tree


# Pantalla de detalle de tarea
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


# Widget para estadísticas de usuario
class UserStat(Widget):
    """Widget para mostrar una estadística de usuario con nombre y valor."""

    def __init__(self, name, value, max_value=None, id=None):
        super().__init__(id=id)
        self.name = name
        self.value = value
        self.max_value = max_value

    def compose(self) -> ComposeResult:
        with Container(classes="user-stat"):
            yield Label(self.name, classes="stat-name")
            if self.max_value:
                yield Digits(f"{self.value}/{self.max_value}", classes="stat-value")
                yield ProgressBar(value=(int(self.value) / int(self.max_value)) * 100, classes="stat-progress")
            else:
                yield Digits(str(self.value), classes="stat-value")


class UserStatsWidget(Widget):
    """Widget que muestra todas las estadísticas del usuario."""

    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data

    def compose(self) -> ComposeResult:
        with Container(id="user-stats-container"):
            yield Label(f"Usuario: {self.user_data['username']}", id="username")

            with Horizontal(id="basic-stats"):
                yield UserStat("Nivel", self.user_data["level"])
                yield UserStat("Clase", self.user_data["class"])

            with Horizontal(id="health-mana"):
                yield UserStat("Salud", self.user_data["health"], self.user_data["max_health"], id="health-stat")
                yield UserStat("Maná", self.user_data["mana"], self.user_data["max_mana"], id="mana-stat")

            with Horizontal(id="exp-gold"):
                yield UserStat("Experiencia", self.user_data["exp"], self.user_data["next_level"], id="exp-stat")
                yield UserStat("Oro", self.user_data["gold"], id="gold-stat")

            yield Label("Atributos", classes="section-title")
            with Horizontal(id="attributes"):
                yield UserStat("Fuerza", self.user_data["str"])
                yield UserStat("Inteligencia", self.user_data["int"])
                yield UserStat("Constitución", self.user_data["con"])
                yield UserStat("Percepción", self.user_data["per"])

            yield Label("Equipamiento", classes="section-title")
            with Container(id="equipment"):
                for slot, item in self.user_data["equipment"].items():
                    yield Label(f"{slot}: {item}")

            yield Label("Logros y Récords", classes="section-title")
            with Container(id="achievements"):
                for achievement in self.user_data["achievements"]:
                    yield Label(f"🏆 {achievement}")

    class Meta:
        css = """
        #user-stats-container {
            height: 100%;
            overflow: auto;
            padding: 1;
        }

        #username {
            text-style: bold;
            background: $primary;
            color: $text;
            width: 100%;
            height: 3;
            content-align: center middle;
            margin-bottom: 1;
        }

        #basic-stats, #health-mana, #exp-gold, #attributes {
            height: auto;
            margin-bottom: 1;
        }

        .user-stat {
            width: 1fr;
            border: solid $accent;
            padding: 1;
            height: auto;
        }

        .stat-name {
            text-style: bold;
        }

        .stat-value {
            content-align: center middle;
            text-style: bold;
        }

        .stat-progress {
            margin-top: 1;
        }

        #health-stat .stat-progress {
            color: red;
        }

        #mana-stat .stat-progress {
            color: blue;
        }

        #exp-stat .stat-progress {
            color: green;
        }

        .section-title {
            background: $panel-lighten-1;
            text-style: bold;
            content-align: center middle;
            margin-top: 1;
            margin-bottom: 1;
        }

        #equipment, #achievements {
            margin-bottom: 1;
        }
        """


# Pantalla de detalles del usuario
class UserDetailScreen(Screen):
    """Pantalla para mostrar detalles del usuario."""

    def __init__(self):
        super().__init__()
        # Datos dummy para el usuario
        self.user_data = {
            "username": "AventureRPG",
            "level": 42,
            "class": "Mago",
            "health": 35,
            "max_health": 50,
            "mana": 87,
            "max_mana": 100,
            "exp": 6789,
            "next_level": 8000,
            "gold": 2534,
            "str": 15,
            "int": 30,
            "con": 18,
            "per": 22,
            "equipment": {
                "Cabeza": "Sombrero del Archiconocimiento",
                "Torso": "Túnica de Concentración",
                "Arma": "Báculo de Poder Místico",
                "Escudo": "Grimorio Antiguo",
            },
            "achievements": ["Completaste 100 tareas", "Mantuviste un hábito por 30 días", "Completaste 5 retos", "Alcanzaste el nivel 25", "Derrotaste a 10 jefes"],
        }

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Perfil del Usuario", id="user-profile-title")
            yield UserStatsWidget(self.user_data)

            with Horizontal(id="profile-actions"):
                yield Button("Cerrar", id="close-profile")

    @on(Button.Pressed, "#close-profile")
    def close_profile(self):
        self.app.pop_screen()

    class Meta:
        css = """
        #user-profile-title {
            text-style: bold;
            background: $primary;
            color: $text;
            width: 100%;
            height: 3;
            content-align: center middle;
        }

        #profile-actions {
            margin-top: 1;
            content-align: center middle;
        }
        """


# Aplicación principal
class HabiticaApp(App):
    BINDINGS = [
        Binding("q", "quit", "Salir"),
        Binding("d", "toggle_dark", "Cambiar tema"),
        Binding("u", "show_user_profile", "Ver perfil"),
    ]

    CSS = """
    #main-content {
        height: 1fr;
        min-height: 40;
    }

    #detail-section {
        height: 1fr;
        min-height: 15;
        border: solid green;
    }

    #tabbed-content {
        height: 3fr;
    }

    .stat-box {
        width: 1fr;
        height: 5;
        border: solid $accent;
        content-align: center middle;
        text-style: bold;
    }

    .section-title {
        background: $panel-lighten-1;
        text-style: bold;
        content-align: center middle;
        margin-top: 1;
        margin-bottom: 1;
    }

    .hidden {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main-content"):
            with TabbedContent(id="tabbed-content"):
                # Pestaña de Tareas
                with TabPane("Tareas", id="tasks-tab"):
                    yield self.create_tasks_table()

                # Pestaña de Tags
                with TabPane("Tags", id="tags-tab"):
                    tree = Tree("Tags", id="tags-tree")

                    # Datos dummy para tags
                    work = tree.root.add("Trabajo", expand=True)
                    work.add_leaf("Reuniones")
                    work.add_leaf("Proyectos")
                    work.add_leaf("Administrativo")

                    personal = tree.root.add("Personal", expand=True)
                    personal.add_leaf("Salud")
                    personal.add_leaf("Hobbies")
                    personal.add_leaf("Familia")

                    yield tree

                # Pestaña de Configuración
                with TabPane("Configuración", id="config-tab"):
                    with Container():
                        with Vertical():
                            yield Label("Configuración General", classes="section-title")

                            with Horizontal():
                                yield Label("Tema:")
                                yield Button("Claro", id="theme-light")
                                yield Button("Oscuro", id="theme-dark")
                                yield Button("Sistema", id="theme-system")

                            with Horizontal():
                                yield Label("Notificaciones:")
                                yield Input(value="10:00", placeholder="Hora de recordatorio")
                                yield Button("Guardar", variant="primary")

                            yield Label("Preferencias de visualización", classes="section-title")
                            with Horizontal():
                                yield Button("Ocultar tareas completadas", id="hide-completed")
                                yield Button("Mostrar estadísticas", id="show-stats")

                # Pestaña de Retos
                with TabPane("Retos", id="challenges-tab"):
                    yield self.create_challenges_table()

                # Pestaña de Usuario
                with TabPane("Usuario", id="user-tab"):
                    with Container():
                        with Horizontal():
                            with Vertical(classes="stat-box"):
                                yield Label("Nivel")
                                yield Label("42", id="user-level")

                            with Vertical(classes="stat-box"):
                                yield Label("Experiencia")
                                yield Label("6789/8000", id="user-exp")

                            with Vertical(classes="stat-box"):
                                yield Label("Salud")
                                yield Label("45/50", id="user-health")

                            with Vertical(classes="stat-box"):
                                yield Label("Oro")
                                yield Label("2534", id="user-gold")

                        yield Label("Logros recientes:", classes="section-title")
                        with Container():
                            yield Label("🏆 Completaste 100 tareas")
                            yield Label("🏆 Mantuviste un hábito por 30 días")
                            yield Label("🏆 Completaste 5 retos")

                        yield Button("Ver perfil completo", id="view-full-profile")

                # Pestaña de Grupo
                with TabPane("Grupo", id="party-tab"):
                    with Container():
                        yield Label("Grupo: Aventureros del Código", classes="section-title")

                        with Container(id="party-messages"):
                            yield Label("Mensajes del grupo:")
                            yield Static("CodeMaster: ¡Hola a todos! ¿Cómo van con el reto?")
                            yield Static("Bookworm: Voy por el día 15, ¡bastante bien!")
                            yield Static("GymHero: Necesito ayuda con la misión del jefe")
                            yield Static("ZenMaster: Yo puedo ayudarte, tengo pociones extra")

                        with Horizontal():
                            yield Input(placeholder="Escribe un mensaje...", id="party-message-input")
                            yield Button("Enviar", variant="primary", id="send-party-message")

            # Sección de detalles
            with Container(id="detail-section"):
                yield Static("Selecciona un elemento para ver detalles...", id="detail-content")

        yield Footer()

    def create_tasks_table(self) -> DataTable:
        table = DataTable(id="tasks-table")
        table.add_columns("ID", "Nombre", "Tipo", "Dificultad", "Estado")

        # Datos dummy para tareas
        tasks = [
            ["1", "Completar informe", "Diario", "Difícil", "Pendiente"],
            ["2", "Hacer ejercicio", "Hábito", "Media", "Activa"],
            ["3", "Leer 30 minutos", "ToDo", "Fácil", "Pendiente"],
            ["4", "Meditar", "Hábito", "Trivial", "Activa"],
            ["5", "Revisar código", "Diario", "Media", "Completada"],
        ]

        for task in tasks:
            table.add_row(*task)

        return table

    def create_challenges_table(self) -> DataTable:
        table = DataTable(id="challenges-table")
        table.add_columns("ID", "Nombre", "Creador", "Miembros", "Premios")

        # Datos dummy para retos
        challenges = [
            ["101", "Reto de 30 días de código", "CodeMaster", "45", "15 gemas"],
            ["102", "Maratón de lectura", "Bookworm", "23", "10 gemas"],
            ["103", "Desafío fitness", "GymHero", "67", "25 gemas"],
            ["104", "Meditación diaria", "ZenMaster", "12", "5 gemas"],
            ["105", "Reto de escritura", "WordSmith", "34", "20 gemas"],
        ]

        for challenge in challenges:
            table.add_row(*challenge)

        return table

    @on(DataTable.RowSelected)
    def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id
        row = event.row_key.value

        if table_id == "tasks-table":
            task_data = {
                "name": event.data_table.get_cell_at((row, 1)),
                "type": event.data_table.get_cell_at((row, 2)),
                "difficulty": event.data_table.get_cell_at((row, 3)),
                "status": event.data_table.get_cell_at((row, 4)),
                "description": "Descripción de ejemplo para esta tarea.",
            }
            self.show_task_detail(task_data)
        elif table_id == "challenges-table":
            challenge_data = {
                "name": event.data_table.get_cell_at((row, 1)),
                "creator": event.data_table.get_cell_at((row, 2)),
                "members": event.data_table.get_cell_at((row, 3)),
                "prize": event.data_table.get_cell_at((row, 4)),
            }
            self.show_challenge_detail(challenge_data)

    def show_task_detail(self, task_data):
        detail_content = self.query_one("#detail-content", Static)
        detail_text = f"""
        # {task_data['name']}

        **Tipo:** {task_data['type']}
        **Dificultad:** {task_data['difficulty']}
        **Estado:** {task_data['status']}

        Esta es una tarea {task_data['type'].lower()} con dificultad {task_data['difficulty'].lower()}.

        [Editar] [Completar] [Eliminar]
        """
        detail_content.update(detail_text)

        # Agregar botón de edición
        action_buttons = self.query("#detail-section .actions-container")
        if action_buttons:
            # Si ya hay botones, eliminarlos
            for button in action_buttons:
                button.remove()

        # Crear botones nuevos
        actions = Container(classes="actions-container")
        edit_button = Button("Editar", variant="primary", id="edit-task-button")
        complete_button = Button("Completar", variant="success", id="complete-task-button")
        delete_button = Button("Eliminar", variant="error", id="delete-task-button")

        actions.mount(edit_button, complete_button, delete_button)
        self.query_one("#detail-section").mount(actions)

        # Guardar datos de la tarea actual para referencia
        self.current_task_data = task_data

    def show_challenge_detail(self, challenge_data):
        detail_content = self.query_one("#detail-content", Static)
        detail_text = f"""
        # {challenge_data['name']}

        **Creador:** {challenge_data['creator']}
        **Miembros:** {challenge_data['members']}
        **Premio:** {challenge_data['prize']}

        Participa en este reto creado por {challenge_data['creator']} junto con otros {challenge_data['members']} miembros.
        """
        detail_content.update(detail_text)

        # Agregar botones de acción
        action_buttons = self.query("#detail-section .actions-container")
        if action_buttons:
            # Si ya hay botones, eliminarlos
            for button in action_buttons:
                button.remove()

        # Crear botones nuevos
        actions = Container(classes="actions-container")
        join_button = Button("Unirse", variant="primary", id="join-challenge-button")
        view_button = Button("Ver tareas", variant="default", id="view-challenge-tasks-button")
        info_button = Button("Más información", variant="default", id="info-challenge-button")

        actions.mount(join_button, view_button, info_button)
        self.query_one("#detail-section").mount(actions)

    @on(Button.Pressed, "#edit-task-button")
    def edit_task(self):
        """Muestra la pantalla de edición de tarea."""
        self.app.push_screen(TaskDetailScreen(self.current_task_data))

    @on(Button.Pressed, "#complete-task-button")
    def complete_task(self):
        """Marca la tarea como completada."""
        self.app.notify("¡Tarea completada!")

    @on(Button.Pressed, "#delete-task-button")
    def delete_task(self):
        """Elimina la tarea."""
        self.app.notify("Tarea eliminada")

    @on(Button.Pressed, "#view-full-profile")
    def view_full_profile(self):
        """Muestra el perfil completo del usuario."""
        self.app.push_screen(UserDetailScreen())

    def action_show_user_profile(self):
        """Acción para mostrar el perfil de usuario (atajo de teclado U)."""
        self.app.push_screen(UserDetailScreen())

    @on(Button.Pressed, "#send-party-message")
    def send_party_message(self):
        message_input = self.query_one("#party-message-input", Input)
        messages_container = self.query_one("#party-messages", Container)

        if message_input.value:
            new_message = Static(f"Tú: {message_input.value}")
            messages_container.mount(new_message)
            message_input.value = ""

    @on(Tree.NodeSelected)
    def handle_tree_selection(self, event: Tree.NodeSelected):
        if "tags-tree" in str(event.node.tree.id):
            detail_content = self.query_one("#detail-content", Static)
            node_label = event.node.label

            if node_label in ["Trabajo", "Personal"]:
                detail_content.update(f"# Categoría: {node_label}\n\nEsta categoría contiene varias etiquetas relacionadas.")
            else:
                detail_content.update(
                    f"""
                # Etiqueta: {node_label}

                Esta etiqueta está asociada con {random.randint(3, 15)} tareas.

                **Última actividad:** hace {random.randint(1, 24)} horas
                **Color:** #{''.join([random.choice('0123456789ABCDEF') for _ in range(6)])}
                """
                )

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id in ["theme-light", "theme-dark", "theme-system"]:
            self.notify(f"Tema cambiado a {button_id.split('-')[1]}")
        elif button_id == "hide-completed":
            self.notify("Ocultando tareas completadas")
        elif button_id == "show-stats":
            self.notify("Mostrando estadísticas")

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark


if __name__ == "__main__":
    app = HabiticaApp()
    app.run()
