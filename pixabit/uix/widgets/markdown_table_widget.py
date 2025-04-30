# Importamos markdown-it-py
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import markdown_it
from markdown_it.token import Token
from rich.markdown import Markdown
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Static

from pixabit.helpers._md_to_rich import MarkdownRenderer


class MarkdownTableWidget(Widget):
    """Un widget reutilizable que muestra datos en una tabla con un panel de detalles en formato Markdown."""

    # Reactive para actualizar la tabla cuando cambian los datos
    items_data = reactive([])
    selected_item = reactive(None)

    DEFAULT_CSS = """
    MarkdownTableWidget {
        layout: horizontal;
        height: 100%;
        width: 100%;
    }

    .table-container {
        width: 40%;
        height: 100%;
        border: solid $accent;
    }

    .details-container {
        width: 60%;
        height: 100%;
        border: solid $accent-lighten-2;
        overflow: auto;
    }

    #markdown-content {
        padding: 1 2;
    }

    .details-title {
        background: $panel;
        padding: 1 2;
        text-align: center;
        color: $text;
    }
    """

    def __init__(
        self,
        name: str = None,
        id: str = None,
        classes: str = None,
        columns: List[Tuple[str, str]] = None,  # Lista de tuplas (id, título)
        on_select: Callable[[Dict[str, Any]], None] = None,  # Callback para selección
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.md_renderer = MarkdownRenderer()
        self._columns = columns or []
        self.on_select_callback = on_select

    def compose(self):
        """Compone el widget con sus componentes."""
        with Horizontal():
            with Vertical(classes="table-container"):
                yield Static(
                    "Selecciona un elemento para ver detalles",
                    classes="details-title",
                )
                yield DataTable(id="items-table")
            with Vertical(classes="details-container"):
                yield Static(
                    "Contenido detallado",
                    id="details-title",
                    classes="details-title",
                )
                yield Static(id="markdown-content")

    def on_mount(self) -> None:
        """Configura la tabla cuando el widget se monta."""
        table = self.query_one("#items-table", DataTable)
        table.cursor_type = "row"

        # Configurar columnas
        if self._columns:
            column_headers = []
            for col_id, col_title in self._columns:
                # Si el título tiene formato markdown, lo renderizamos
                if any(marker in col_title for marker in ["*", "**", "`"]):
                    column_headers.append(self.md_renderer.markdown_to_rich_text(col_title))
                else:
                    column_headers.append(col_title)
            table.add_columns(*column_headers)

        # Cargar datos iniciales si existen
        self._refresh_table_data()

    def watch_items_data(self, new_data: List[Dict[str, Any]]):
        """Actualiza la tabla cuando cambian los datos."""
        self._refresh_table_data()

    def watch_selected_item(self, item: Optional[Dict[str, Any]]):
        """Actualiza el panel de detalles cuando cambia la selección."""
        if item:
            # Actualizar el título del panel de detalles
            details_title = self.query_one("#details-title", Static)
            title_text = item.get("title", "Detalles")
            # Quitar marcadores markdown del título si existen
            for marker in ["*", "**", "`"]:
                title_text = title_text.replace(marker, "")
            details_title.update(f"Detalles: {title_text}")

            # Actualizar el contenido Markdown
            markdown_content = self.query_one("#markdown-content", Static)
            content = item.get("markdown_content", "")
            markdown_content.update(Markdown(content))

    def _refresh_table_data(self):
        """Actualiza los datos de la tabla."""
        table = self.query_one("#items-table", DataTable)

        # Limpiar tabla antes de añadir nuevos datos
        table.clear()

        # Volver a añadir columnas si es necesario (si se borraron)
        if not table.columns and self._columns:
            column_headers = []
            for col_id, col_title in self._columns:
                if any(marker in col_title for marker in ["*", "**", "`"]):
                    column_headers.append(self.md_renderer.markdown_to_rich_text(col_title))
                else:
                    column_headers.append(col_title)
            table.add_columns(*column_headers)

        # Añadir filas con los datos
        for item in self.items_data:
            row_data = []
            for col_id, _ in self._columns:
                value = item.get(col_id, "")
                if isinstance(value, str) and any(marker in value for marker in ["*", "**", "`"]):
                    row_data.append(self.md_renderer.markdown_to_rich_text(value))
                else:
                    row_data.append(value)
            table.add_row(*row_data)

    def on_data_table_row_selected(self, event):
        """Maneja el evento de selección de fila."""
        table = event.data_table
        selected_row_index = table.cursor_row

        if selected_row_index is not None and 0 <= selected_row_index < len(self.items_data):
            self.selected_item = self.items_data[selected_row_index]

            # Llamar al callback si existe
            if self.on_select_callback and self.selected_item:
                self.on_select_callback(self.selected_item)

    def set_data(self, data: List[Dict[str, Any]]):
        """Establece los datos del widget."""
        self.items_data = data

    def set_columns(self, columns: List[Tuple[str, str]]):
        """Establece las columnas de la tabla."""
        self._columns = columns
        table = self.query_one("#items-table", DataTable)
        table.clear()
        self._refresh_table_data()
