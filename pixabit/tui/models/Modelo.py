from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListView,
    Rule,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)


class NavigationTree(Widget):
    """Árbol de navegación para la interfaz."""

    def compose(self) -> ComposeResult:
        """Crear el árbol de navegación."""
        tree = Tree("Habitica")
        tree.root.expand()

        # Tareas
        tasks_node = tree.root.add("Tareas", expand=True)
        tasks_node.add_leaf("Todos")
        tasks_node.add_leaf("Hábitos")
        tasks_node.add_leaf("Diarios")
        tasks_node.add_leaf("Recompensas")

        # Social
        social_node = tree.root.add("Social")
        social_node.add_leaf("Equipo")
        social_node.add_leaf("Desafíos")
        social_node.add_leaf("Mensajes")

        # Configuración
        config_node = tree.root.add("Configuración")
        config_node.add_leaf("Perfil")
        config_node.add_leaf("Etiquetas")
        config_node.add_leaf("Ajustes")

        yield tree


class HabiticaTUI(App):
    """Interfaz de usuario basada en texto para Habitica, optimizada para móviles."""

    BINDINGS = [
        Binding(key="q", action="quit", description="Salir"),
        Binding(key="escape", action="toggle_menu", description="Menú"),
        Binding(key="/", action="search", description="Buscar"),
        Binding(key="f1", action="view_help", description="Ayuda"),
        Binding(key="f2", action="toggle_navigation", description="Navegación"),
        # Atajos para moverse entre secciones
        Binding(key="1", action="section('todos')", description="Todos"),
        Binding(key="2", action="section('habits')", description="Hábitos"),
        Binding(key="3", action="section('dailies')", description="Diarios"),
        Binding(
            key="4", action="section('rewards')", description="Recompensas"
        ),
        Binding(key="5", action="section('party')", description="Equipo"),
        Binding(key="6", action="section('messages')", description="Mensajes"),
        # Atajos para acciones comunes
        Binding(key="n", action="new_item", description="Nuevo"),
        Binding(key="e", action="edit_item", description="Editar"),
        Binding(key="d", action="delete_item", description="Eliminar"),
        Binding(key="c", action="complete_item", description="Completar"),
        # Navegación por elementos
        Binding(key="j", action="next_item", description="Siguiente"),
        Binding(key="k", action="previous_item", description="Anterior"),
    ]

    CSS = """
    /* Variables de colores */
    $habitica-purple-dark: #4f2a93;
    $habitica-purple-light: #925cf3;
    $habitica-red: #ff6165;
    $habitica-blue: #50b5e9;
    $habitica-yellow: #ffbe5d;
    $habitica-green: #24cc8f;

    /* Estilo general */
    Screen {
        background: $background;
    }

    Header {
        background: $habitica-purple-dark;
        color: $text;
    }

    Footer {
        background: $habitica-purple-dark;
        color: $text;
    }

    /* Layout principal */
    #nav-panel {
        width: 30%;
        max-width: 25;
        min-width: 15;
        background: $panel;
        display: block;
    }

    #content-panel {
        width: 1fr;
        background: $background;
        overflow: auto;
    }

    /* Barra de estado */
    #status-bar {
        height: 3;
        width: 100%;
        background: $panel-lighten-1;
    }

    #stats-container {
        height: 100%;
        layout: horizontal;
        align: center middle;
    }

    .stat {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        text-style: bold;
    }

    .hp { color: $habitica-red; border-right: solid $background; }
    .mp { color: $habitica-blue; border-right: solid $background; }
    .exp { color: $habitica-yellow; border-right: solid $background; }
    .gold { color: $habitica-yellow; }

    /* Navegación en árbol */
    NavigationTree {
        width: 100%;
        height: auto;
        overflow-y: auto;
        padding: 1;
    }

    /* Botones de acción rápida */
    #action-buttons {
        width: 100%;
        height: auto;
        padding: 1;
    }

    Button {
        width: 100%;
        margin-bottom: 1;
    }

    /* Botones de acción por tipo */
    .todo-btn { border: tall $habitica-blue; }
    .habit-btn { border: tall $habitica-red; }
    .daily-btn { border: tall $habitica-yellow; }
    .reward-btn { border: tall $habitica-green; }

    /* Tablas de datos */
    DataTable {
        height: 100%;
        overflow: auto;
    }

    /* Búsqueda */
    #search-container {
        height: auto;
        dock: top;
        background: $panel-lighten-1;
        padding: 1;
        display: none;
    }

    #search-container.visible {
        display: block;
    }

    /* Vista específica de elementos */
    #item-view {
        padding: 1;
    }

    /* Etiquetas */
    .tag {
        background: $panel-lighten-2;
        color: $text;
        padding: 0 1 0 1;
        margin-right: 1;
        border: round red;
    }

    /* Adaptación a móviles */

    """

    show_search = reactive(False)
    show_navigation = reactive(True)
    current_section = reactive("todos")

    def compose(self) -> ComposeResult:
        """Crear el layout principal."""
        yield Header(show_clock=True)

        # Barra de búsqueda (oculta por defecto)
        with Container(id="search-container"):
            yield Input(placeholder="Buscar...", id="global-search")

        # Layout principal
        with Horizontal(id="main-layout"):
            # Panel de navegación
            with Container(id="nav-panel"):
                yield NavigationTree()
                yield Rule()

                # Botones de acción rápida
                with Container(id="action-buttons"):
                    yield Label("Crear Nueva:", classes="heading")
                    yield Button("Todo", id="new-todo", classes="todo-btn")
                    yield Button("Hábito", id="new-habit", classes="habit-btn")
                    yield Button("Diario", id="new-daily", classes="daily-btn")
                    yield Button(
                        "Recompensa", id="new-reward", classes="reward-btn"
                    )

            # Panel de contenido
            with Container(id="content-panel"):
                # TabbedContent para secciones principales
                with TabbedContent(id="main-tabs"):
                    # === Sección de Tareas ===
                    with TabPane("Todos", id="todos"):
                        with Vertical():
                            with Horizontal(id="todos-actions"):
                                yield Button(
                                    "Nuevo", variant="success", id="add-todo"
                                )
                                yield Button(
                                    "Editar", variant="primary", id="edit-todo"
                                )
                                yield Button(
                                    "Eliminar",
                                    variant="error",
                                    id="delete-todo",
                                )
                                yield Button(
                                    "Completar",
                                    variant="success",
                                    id="complete-todo",
                                )
                            yield DataTable(id="todos-table")

                    with TabPane("Hábitos", id="habits"):
                        with Vertical():
                            with Horizontal(id="habits-actions"):
                                yield Button(
                                    "Nuevo", variant="success", id="add-habit"
                                )
                                yield Button(
                                    "Editar", variant="primary", id="edit-habit"
                                )
                                yield Button(
                                    "Eliminar",
                                    variant="error",
                                    id="delete-habit",
                                )
                                yield Button(
                                    "+", variant="success", id="up-habit"
                                )
                                yield Button(
                                    "-", variant="error", id="down-habit"
                                )
                            yield DataTable(id="habits-table")

                    with TabPane("Diarios", id="dailies"):
                        with Vertical():
                            with Horizontal(id="dailies-actions"):
                                yield Button(
                                    "Nuevo", variant="success", id="add-daily"
                                )
                                yield Button(
                                    "Editar", variant="primary", id="edit-daily"
                                )
                                yield Button(
                                    "Eliminar",
                                    variant="error",
                                    id="delete-daily",
                                )
                                yield Button(
                                    "Completar",
                                    variant="success",
                                    id="complete-daily",
                                )
                            yield DataTable(id="dailies-table")

                    with TabPane("Recompensas", id="rewards"):
                        with Vertical():
                            with Horizontal(id="rewards-actions"):
                                yield Button(
                                    "Nueva", variant="success", id="add-reward"
                                )
                                yield Button(
                                    "Editar",
                                    variant="primary",
                                    id="edit-reward",
                                )
                                yield Button(
                                    "Eliminar",
                                    variant="error",
                                    id="delete-reward",
                                )
                                yield Button(
                                    "Comprar",
                                    variant="warning",
                                    id="buy-reward",
                                )
                            yield DataTable(id="rewards-table")

                    # === Sección Social ===
                    with TabPane("Equipo", id="party"):
                        with Vertical():
                            with Horizontal():
                                yield Button(
                                    "Refrescar",
                                    variant="primary",
                                    id="refresh-party",
                                )
                            with Grid(id="party-grid"):
                                # Grid 2x2 para información del equipo
                                with Container(id="party-info"):
                                    yield Label(
                                        "Información del Equipo",
                                        classes="heading",
                                    )
                                    yield Static(id="party-details")

                                with Container(id="quest-info"):
                                    yield Label(
                                        "Quest Actual", classes="heading"
                                    )
                                    yield Static(id="quest-details")

                                with Container(
                                    id="chat-info", classes="span-2"
                                ):
                                    yield Label(
                                        "Chat del Equipo", classes="heading"
                                    )
                                    yield DataTable(id="party-chat")
                                    with Horizontal():
                                        yield Input(
                                            placeholder="Mensaje...",
                                            id="party-message",
                                        )
                                        yield Button(
                                            "Enviar", id="send-party-message"
                                        )

                    with TabPane("Desafíos", id="challenges"):
                        with Vertical():
                            yield DataTable(id="challenges-table")

                    with TabPane("Mensajes", id="messages"):
                        with Vertical():
                            yield DataTable(id="messages-table")
                            with Horizontal():
                                yield Input(
                                    placeholder="Responder...",
                                    id="message-reply",
                                )
                                yield Button("Enviar", id="send-message")

                    # === Sección de Configuración ===
                    with TabPane("Perfil", id="profile"):
                        with Vertical():
                            yield Static(id="profile-info")

                    with TabPane("Etiquetas", id="tags"):
                        with Vertical():
                            with Horizontal():
                                yield Button(
                                    "Nueva", variant="success", id="add-tag"
                                )
                                yield Button(
                                    "Editar", variant="primary", id="edit-tag"
                                )
                                yield Button(
                                    "Eliminar", variant="error", id="delete-tag"
                                )
                            yield DataTable(id="tags-table")

                    with TabPane("Ajustes", id="settings"):
                        with Vertical():
                            yield Label(
                                "Configuración de la Aplicación",
                                classes="heading",
                            )
                            # Aquí irían opciones de configuración

        # Barra de estado con estadísticas
        with Container(id="status-bar"):
            with Horizontal(id="stats-container"):
                yield Label("❤️ [b]50[/b]/50", classes="stat hp", id="hp-stat")
                yield Label("⚡ [b]30[/b]/30", classes="stat mp", id="mp-stat")
                yield Label(
                    "⭐ [b]80[/b]/150", classes="stat exp", id="exp-stat"
                )
                yield Label(
                    "🔰 [b]10[/b]", classes="stat level", id="level-stat"
                )
                yield Label(
                    "💰 [b]500[/b]", classes="stat gold", id="gold-stat"
                )

        yield Footer()

    def action_toggle_menu(self) -> None:
        """Mostrar/ocultar el menú principal."""
        self.show_navigation = not self.show_navigation
        try:
            nav_panel = self.query_one("#nav-panel")
            if self.show_navigation:
                nav_panel.add_class("visible")
            else:
                nav_panel.remove_class("visible")
        except NoMatches:
            pass

    def action_search(self) -> None:
        """Mostrar/ocultar la barra de búsqueda."""
        self.show_search = not self.show_search
        try:
            search_container = self.query_one("#search-container")
            if self.show_search:
                search_container.add_class("visible")
                self.query_one("#global-search").focus()
            else:
                search_container.remove_class("visible")
        except NoMatches:
            pass

    def action_toggle_navigation(self) -> None:
        """Alternar la visibilidad del panel de navegación."""
        self.action_toggle_menu()

    def action_section(self, section: str) -> None:
        """Cambiar a una sección específica."""
        self.current_section = section
        try:
            tabs = self.query_one("#main-tabs", TabbedContent)
            tabs.active = section
        except NoMatches:
            pass

    def action_new_item(self) -> None:
        """Crear un nuevo elemento según la sección actual."""
        # Esta función puede ser implementada más adelante
        pass

    def action_edit_item(self) -> None:
        """Editar el elemento seleccionado."""
        # Esta función puede ser implementada más adelante
        pass

    def action_delete_item(self) -> None:
        """Eliminar el elemento seleccionado."""
        # Esta función puede ser implementada más adelante
        pass

    def action_complete_item(self) -> None:
        """Completar el elemento seleccionado."""
        # Esta función puede ser implementada más adelante
        pass

    def action_next_item(self) -> None:
        """Seleccionar el siguiente elemento en la lista."""
        # Esta función puede ser implementada más adelante
        pass

    def action_previous_item(self) -> None:
        """Seleccionar el elemento anterior en la lista."""
        # Esta función puede ser implementada más adelante
        pass

    def action_view_help(self) -> None:
        """Mostrar la pantalla de ayuda."""
        # Esta función puede ser implementada más adelante
        pass


if __name__ == "__main__":
    app = HabiticaTUI()
    app.run()
