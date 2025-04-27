# Importamos markdown-it-py
import markdown_it
from markdown_it.token import Token
from rich.markdown import Markdown
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static


class MarkdownTableApp(App):
    """Una aplicación que muestra datos en una tabla con títulos y contenido formateado usando markdown-it."""

    CSS = """
    .table-container {
        width: 40%;
        height: 100%;
        border: solid green;
    }

    .details-container {
        width: 60%;
        height: 100%;
        border: solid blue;
        overflow: auto;
    }

    #markdown-content {
        padding: 1 2;
    }

    .details-title {
        background: $boost;
        padding: 1 2;
        text-align: center;
        color: $text;
    }
    """

    BINDINGS = [
        Binding(key="q", action="quit", description="Salir"),
        Binding(key="escape", action="quit", description="Salir"),
    ]

    def __init__(self):
        super().__init__()
        # Inicializar el parser de markdown-it
        self.md_parser = markdown_it.MarkdownIt()

        # Almacenar datos con su contenido Markdown
        self.items_data = [
            {
                "id": "1",
                "title": "**Introducción** a Python",
                "description": "Lenguaje de *programación* `versátil`",
                "markdown_content": """
# Introducción a Python

Python es un lenguaje de programación **interpretado** de alto nivel y propósito general.

## Características principales

* Sintaxis clara y legible
* Tipado dinámico
* Orientado a objetos
* Gran biblioteca estándar

```python
def hello_world():
    print("¡Hola, mundo!")
```

Para más información, visita [python.org](https://www.python.org/).
                """,
            },
            {
                "id": "2",
                "title": "Aprendiendo `Textual` para **TUI**",
                "description": "*Framework* **TUI** para Python",
                "markdown_content": """
# Framework Textual

Textual es un *framework* de **TUI** (Text User Interface) para Python.

## Componentes principales

1. Widgets
2. Contenedores
3. Eventos
4. CSS para TUI

### Ejemplo de código

```python
from textual.app import App

class MiApp(App):
    def compose(self):
        yield Header()
        yield Footer()
```

Visita [textual.textualize.io](https://textual.textualize.io/) para documentación.
                """,
            },
            {
                "id": "3",
                "title": "Markdown en *Rich* con `código`",
                "description": "~~Básico~~ -> **Avanzado** y *completo*",
                "markdown_content": """
# Markdown en Rich

Rich permite renderizar Markdown en la terminal con estilos.

## Ejemplo de uso

```python
from rich.markdown import Markdown
from rich.console import Console

console = Console()
md = Markdown("# Título\n\nContenido **importante**.")
console.print(md)
```

## Elementos soportados

| Elemento | Sintaxis |
|----------|----------|
| Negrita | `**texto**` |
| Cursiva | `*texto*` |
| Código | `` `código` `` |
| Enlaces | `[texto](url)` |

> Rich hace que el texto en terminal sea más expresivo y agradable.
                """,
            },
        ]

    def markdown_to_rich_text(self, markdown_str: str) -> Text:
        """Convierte Markdown a Rich Text usando markdown-it-py para un parsing más completo."""
        # Parsear el markdown
        tokens = self.md_parser.parse(markdown_str)

        # Crear un objeto Text para el resultado
        result = Text()

        # Procesar los tokens recursivamente
        self._process_tokens(tokens, result)

        return result

    def _process_tokens(self, tokens, text_obj):
        """Procesa los tokens de markdown-it y aplica los estilos correspondientes."""
        current_styles = {}

        for token in tokens:
            # Manejar tokens inline
            if token.type == "inline" and token.children:
                self._process_tokens(token.children, text_obj)
                continue

            # Procesar formato de texto
            if token.type == "text":
                text_obj.append(token.content, Style(**current_styles))

            elif token.type == "strong_open":
                current_styles["bold"] = True

            elif token.type == "strong_close":
                current_styles.pop("bold", None)

            elif token.type == "em_open":
                current_styles["italic"] = True

            elif token.type == "em_close":
                current_styles.pop("italic", None)

            elif token.type == "code_inline":
                # Para código inline, añadimos directamente con estilo
                text_obj.append(token.content, Style(reverse=True))

            elif token.type == "s_open":
                current_styles["strike"] = True

            elif token.type == "s_close":
                current_styles.pop("strike", None)

            elif token.type == "link_open":
                current_styles["underline"] = True

            elif token.type == "link_close":
                current_styles.pop("underline", None)

    def compose(self) -> ComposeResult:
        yield Header()
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
        yield Footer()

    def on_mount(self) -> None:
        # Configurar la tabla
        table = self.query_one("#items-table", DataTable)
        table.cursor_type = "row"

        # Añadir columnas con títulos formateados
        table.add_columns(
            "ID",
            self.markdown_to_rich_text("**Título**"),
            self.markdown_to_rich_text("*Descripción*"),
        )

        # Añadir filas con contenido formateado
        for item in self.items_data:
            table.add_row(
                item["id"],
                self.markdown_to_rich_text(item["title"]),
                self.markdown_to_rich_text(item["description"]),
            )

    def on_data_table_row_selected(self, event) -> None:
        """Manejar el evento de selección de fila."""
        table = event.data_table
        selected_row_index = table.cursor_row

        if selected_row_index is not None:
            # Obtener el ID de la fila seleccionada
            selected_id = table.get_row_at(selected_row_index)[0]

            # Buscar el elemento correspondiente
            selected_item = next(
                (item for item in self.items_data if item["id"] == selected_id),
                None,
            )

            if selected_item:
                # Actualizar el título del panel de detalles
                details_title = self.query_one("#details-title", Static)
                details_title.update(
                    f"Detalles: {selected_item['title'].replace('*', '').replace('`', '').replace('**', '')}"
                )

                # Actualizar el contenido Markdown
                markdown_content = self.query_one("#markdown-content", Static)
                markdown_content.update(
                    Markdown(selected_item["markdown_content"])
                )


if __name__ == "__main__":
    app = MarkdownTableApp()
    app.run()
