"""Ejemplo de uso del widget MarkdownTableWidget en una aplicación Textual."""

# Importamos nuestro widget personalizado
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from pixabit.helpers._md_to_rich import MarkdownRenderer
from pixabit.uix.widgets.markdown_table_widget import MarkdownTableWidget


class HabiticaTasksApp(App):
    """Una aplicación de ejemplo que muestra tareas de Habitica."""

    BINDINGS = [
        Binding("q", "quit", "Salir"),
        Binding("r", "refresh", "Actualizar"),
    ]

    CSS = """
    #main-container {
        height: 100%;
        margin: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        # Datos de ejemplo - en una aplicación real, estos vendrían de la API de Habitica
        self.tasks_data = [
            {
                "id": "task1",
                "title": "**Tarea Urgente**",
                "description": "Descripción *corta*",
                "markdown_content": """
# Tarea Urgente

Esta es una tarea de alta prioridad que debe completarse pronto.

## Detalles
- Fecha límite: **Mañana**
- Prioridad: Alta
- Tiempo estimado: 2 horas

## Notas
Este es un ejemplo de contenido markdown extenso que se mostrará en el panel de detalles cuando se seleccione este elemento.
""",
            },
            {
                "id": "task2",
                "title": "Tarea Normal",
                "description": "Con `código` incluido",
                "markdown_content": """
# Tarea Normal

Esta es una tarea de prioridad normal.

## Código de ejemplo
```python
def hello_world():
    print("¡Hola desde Habitica!")
```

## Estado
- En progreso
- 50% completado
""",
            },
            {
                "id": "task3",
                "title": "*Tarea de baja prioridad*",
                "description": "Puede esperar",
                "markdown_content": """
# Tarea de baja prioridad

Esta tarea no es urgente y puede posponerse si es necesario.

## Lista de verificación
- [ ] Paso 1
- [ ] Paso 2
- [x] Paso 3 (completado)

## Notas adicionales
Cualquier actualización o comentario sobre esta tarea se registrará aquí.
""",
            },
        ]

    def compose(self) -> ComposeResult:
        """Compone la interfaz de usuario."""
        yield Header()

        # Definimos las columnas: tuplas de (id_campo, título_columna)
        columns = [("id", "ID"), ("title", "**Título**"), ("description", "*Descripción*")]

        # Creamos una instancia de nuestro widget personalizado
        yield MarkdownTableWidget(id="main-container", columns=columns, on_select=self.handle_task_selected)

        yield Footer()

    def on_mount(self) -> None:
        """Se ejecuta cuando la aplicación se monta."""
        # Obtenemos referencia a nuestro widget
        table_widget = self.query_one(MarkdownTableWidget)

        # Configuramos los datos
        table_widget.set_data(self.tasks_data)

    def handle_task_selected(self, task):
        """Manejador para cuando se selecciona una tarea."""
        # Aquí podríamos realizar acciones adicionales cuando se selecciona una tarea
        # Por ejemplo, actualizar otros widgets o llamar a una API
        self.log.info(f"Tarea seleccionada: {task['id']}")

    def action_refresh(self):
        """Acción para actualizar los datos desde la API."""
        # En una aplicación real, aquí llamaríamos a la API de Habitica
        # Por ahora, solo simulamos una actualización
        self.log.info("Actualizando datos...")

        # Podríamos modificar los datos o cargar nuevos
        self.tasks_data.append(
            {
                "id": f"task{len(self.tasks_data) + 1}",
                "title": "**Nueva Tarea**",
                "description": "Añadida al *refrescar*",
                "markdown_content": "# Tarea Recién Añadida\n\nEsta tarea fue añadida al refrescar los datos.",
            }
        )

        # Actualizamos el widget con los nuevos datos
        table_widget = self.query_one(MarkdownTableWidget)
        table_widget.set_data(self.tasks_data)


# Ejecutamos la aplicación si este script se ejecuta directamente
if __name__ == "__main__":
    app = HabiticaTasksApp()
    app.run()
