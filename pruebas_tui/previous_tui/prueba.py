import random

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane, Tree


# Ventana modal para ediciones
class EditModal(Screen):
    def __init__(self, item_data):
        super().__init__()
        self.item_data = item_data

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(f"Editar: {self.item_data['name']}")
            yield Input(placeholder="Nombre", value=self.item_data["name"])
            yield Input(placeholder="Descripción", value=self.item_data.get("description", ""))
            with Horizontal():
                yield Button("Guardar", id="save-edit", variant="primary")
                yield Button("Cancelar", id="cancel-edit")

    @on(Button.Pressed, "#save-edit")
    def handle_save(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#cancel-edit")
    def handle_cancel(self):
        self.app.pop_screen()


# Aplicación principal
class HabiticaApp(App):
    BINDINGS = [
        Binding("q", "quit", "Salir"),
        Binding("d", "toggle_dark", "Cambiar tema"),
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

    #modal-container {
        background: $surface;
        border: solid $accent;
        min-width: 40;
        min-height: 10;
        max-width: 80;
        max-height: 20;
        padding: 1 2;
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
                    # Ahora creamos el Tree directamente aquí
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

    def show_challenge_detail(self, challenge_data):
        detail_content = self.query_one("#detail-content", Static)
        detail_text = f"""
        # {challenge_data['name']}

        **Creador:** {challenge_data['creator']}
        **Miembros:** {challenge_data['members']}
        **Premio:** {challenge_data['prize']}

        Participa en este reto creado por {challenge_data['creator']} junto con otros {challenge_data['members']} miembros.

        [Unirse] [Ver tareas] [Más información]
        """
        detail_content.update(detail_text)

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

                [Editar] [Eliminar] [Ver tareas]
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
