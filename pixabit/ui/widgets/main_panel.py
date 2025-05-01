"""Generated file to handle table list and table details. TODO review"""


class HabiticaTUIApp(App):
    """Habitica TUI App with Task List and Detail Panel."""

    # --- CSS para el layout y estilo ---
    CSS = """
    /* Variables para configuración global de colores y estilos */
    $panel-border: round $panel;
    $content-padding: 1;
    $margin-between-items: 1;
    $button-spacing: 1;

    /* Define the main layout with two columns */
    #main-layout {
        layout: grid;
        grid-columns: 3fr 2fr; /* Task list gets 60%, details 40% */
        grid-rows: 1fr;
        padding: $content-padding;
        height: 100%;
    }

    /* Styling for both panels */
    .app-panel {
        border: $panel-border;
        padding: $content-padding;
        overflow: auto;
        height: 100%;
    }

    /* Task list panel specific styling */
    TaskListWidget {
        width: 100%;
    }

    /* Basic styling for the detail panel */
    TaskDetailPanel {
        width: 100%;
    }

    /* Styling for detail content items */
    #task-details-content {
        margin-top: $margin-between-items;
    }

    #task-details-content Static {
        margin-bottom: $margin-between-items;
        width: 100%;
        text-wrap: wrap;
    }

    #task-details-content #task-detail-text {
        text-style: bold;
    }

    #task-details-content #task-detail-notes {
        min-height: 3;
        margin-top: $margin-between-items;
        padding: 1;
        background: $surface-darken-1;
        border: thin $primary-background;
    }

    /* Action buttons layout and styling */
    #task-detail-actions {
        margin-top: 2;
    }

    /* Container for main action buttons */
    #primary-actions {
        layout: horizontal;
        width: 100%;
        height: 3;
        align: center middle;
        margin-bottom: $margin-between-items;
    }

    /* Container for secondary action buttons */
    #secondary-actions {
        layout: horizontal;
        width: 100%;
        height: 3;
        align: center middle;
    }

    /* General button styling */
    #task-detail-actions Button {
        margin-right: $button-spacing;
        min-width: 8;
    }

    /* Styling for score buttons */
    .score-button {
        width: 4;
        text-align: center;
    }

    /* Status bar styling */
    #app-status-bar {
        dock: bottom;
        background: $surface;
        color: $text;
        height: 1;
    }

    /* Style for hiding content */
    .hidden {
        display: none;
    }

    /* Hover effect for interactive elements */
    Button:hover {
        background: $accent;
    }
    """

    # --- Keyboard Bindings ---
    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("f1", "toggle_help", "Help"),
        ("r", "refresh_data", "Refresh"),
        # Acciones comunes
        ("c", "complete_task", "Complete"),
        ("e", "edit_task", "Edit"),
        ("d", "delete_task", "Delete"),
        # Navegación
        ("up", "focus_up", "Up"),
        ("down", "focus_down", "Down"),
        ("tab", "next_panel", "Next Panel"),
        ("shift+tab", "prev_panel", "Prev Panel"),
    ]

    # --- Compose App Layout ---
    def compose(self) -> ComposeResult:
        """Compose the main application layout with all components."""
        # Main layout container
        with Container(id="main-layout"):
            yield TaskListWidget(id="task-list", classes="app-panel")
            yield TaskDetailPanel(id="task-detail-panel", classes="app-panel")

        # Status bar in the bottom
        yield Static("Ready", id="app-status-bar")

    # --- App Setup on Mount ---
    async def on_mount(self) -> None:
        """Setup the app on startup."""
        # Initialize datastore and component references
        self.datastore = DummyDataStore()
        self.task_list_widget = self.query_one("#task-list", TaskListWidget)
        self.task_detail_panel = self.query_one("#task-detail-panel", TaskDetailPanel)
        self.status_bar = self.query_one("#app-status-bar", Static)

        # Set focus to the task list initially
        self.set_focus(self.task_list_widget)

        # Configure components with necessary data
        await self._configure_components()

        # Update status bar
        self.status_bar.update("Ready - Press F1 for help")

        log.info("App mounted and initialized successfully.")

    async def _configure_components(self) -> None:
        """Configure all components with necessary data."""
        try:
            # Pass tag colors from the datastore to the widgets
            self.task_list_widget.tag_colors = self.datastore.tag_colors
            self.task_detail_panel.tag_colors = self.datastore.tag_colors

            # Initial load of tasks
            await self.task_list_widget.load_or_refresh_data()

            # Subscribe to any datastore events if applicable
            # self.datastore.subscribe_to_changes(self._on_data_changed)
        except Exception as e:
            log.error(f"Error configuring components: {e}")
            self.update_status(f"Error: {str(e)}", error=True)

    def update_status(self, message: str, error: bool = False) -> None:
        """Update the status bar with a message."""
        style = "red" if error else "green"
        self.status_bar.update(f"[{style}]{message}[/{style}]")

        # Opcional: Programar un temporizador para borrar el mensaje después de unos segundos
        def clear_status():
            self.status_bar.update("Ready - Press F1 for help")

        # Si usas asyncio, podrías implementar un temporizador así:
        # self.set_timer(5, clear_status)
        # O si prefieres evitar temporizadores, simplemente deja el mensaje

    # --- Message Handlers ---

    @on(ViewTaskDetailsRequest)
    async def handle_view_task_details_request(self, message: ViewTaskDetailsRequest) -> None:
        """Handle request to view task details."""
        log.info(f"Viewing details for Task ID: {message.task_id}")

        try:
            # Fetch the task and update detail panel
            task = self.datastore.get_task_by_id(message.task_id)
            if task:
                self.task_detail_panel.current_task = task
                self.update_status(f"Viewing task: {task.text[:30]}...")
            else:
                log.warning(f"Task with ID {message.task_id} not found.")
                self.task_detail_panel.current_task = None
                self.update_status("Task not found", error=True)
        except Exception as e:
            log.error(f"Error fetching task details: {e}")
            self.task_detail_panel.current_task = None
            self.update_status(f"Error: {str(e)}", error=True)

    @on(ScoreTaskRequest, ScoreTaskDetail)
    async def handle_score_task(self, message: Any) -> None:
        """Handle scoring tasks from either panel."""
        task_id = message.task_id
        direction = message.direction
        log.info(f"Scoring task {task_id} {direction}")

        try:
            if self.datastore.score_task(task_id, direction):
                await self._refresh_ui_after_task_change(task_id)
                self.update_status(f"Task scored {direction}")
            else:
                self.update_status("Failed to score task", error=True)
        except Exception as e:
            log.error(f"Error scoring task: {e}")
            self.update_status(f"Error: {str(e)}", error=True)

    @on(CompleteTask)
    async def handle_complete_task(self, message: CompleteTask) -> None:
        """Handle request to complete a task."""
        task_id = message.task_id
        log.info(f"Completing task {task_id}")

        try:
            if self.datastore.complete_task(task_id):
                await self.task_list_widget.load_or_refresh_data()
                self.task_detail_panel.current_task = None
                self.update_status("Task completed")
                self.set_focus(self.task_list_widget)
            else:
                self.update_status("Failed to complete task", error=True)
        except Exception as e:
            log.error(f"Error completing task: {e}")
            self.update_status(f"Error: {str(e)}", error=True)

    @on(DeleteTask)
    async def handle_delete_task(self, message: DeleteTask) -> None:
        """Handle request to delete a task."""
        task_id = message.task_id
        log.info(f"Deleting task {task_id}")

        try:
            if self.datastore.delete_task(task_id):
                await self.task_list_widget.load_or_refresh_data()
                self.task_detail_panel.current_task = None
                self.update_status("Task deleted")
                self.set_focus(self.task_list_widget)
            else:
                self.update_status("Failed to delete task", error=True)
        except Exception as e:
            log.error(f"Error deleting task: {e}")
            self.update_status(f"Error: {str(e)}", error=True)

    @on(EditTask)
    async def handle_edit_task(self, message: EditTask) -> None:
        """Handle request to edit a task."""
        task_id = message.task_id
        log.info(f"Editing task {task_id}")

        # Aquí normalmente abrirías un diálogo modal
        # Por ahora, solo mostramos un mensaje en la barra de estado
        self.update_status("Edit feature not implemented yet")

        # Para implementación futura con un modal:
        # task = self.datastore.get_task_by_id(task_id)
        # if task:
        #     edit_screen = TaskEditModal(task)
        #     result = await self.push_screen(edit_screen)
        #     if result:  # Si el usuario guardó los cambios
        #         await self._refresh_ui_after_task_change(task_id)

    # --- Helper Methods ---

    async def _refresh_ui_after_task_change(self, task_id: str) -> None:
        """Refresh UI components after a task has been modified."""
        # Refresh task list
        await self.task_list_widget.load_or_refresh_data()

        # Refresh detail panel if needed
        if self.task_detail_panel.current_task and getattr(self.task_detail_panel.current_task, "id", None) == task_id:
            updated_task = self.datastore.get_task_by_id(task_id)
            self.task_detail_panel.current_task = updated_task

    # --- App Actions ---

    def action_quit_app(self) -> None:
        """Quit the application."""
        log.info("Quitting application.")
        self.exit()

    def action_toggle_help(self) -> None:
        """Show a help modal dialog."""
        # En una implementación real, esto abriría un modal con ayuda
        self.update_status("Help: Press Q to quit, TAB to switch panels")

    async def action_refresh_data(self) -> None:
        """Refresh all data from the datastore."""
        self.update_status("Refreshing data...")
        try:
            await self.task_list_widget.load_or_refresh_data()
            if self.task_detail_panel.current_task:
                task_id = getattr(self.task_detail_panel.current_task, "id", None)
                if task_id:
                    updated_task = self.datastore.get_task_by_id(task_id)
                    self.task_detail_panel.current_task = updated_task
            self.update_status("Data refreshed")
        except Exception as e:
            log.error(f"Error refreshing data: {e}")
            self.update_status(f"Error refreshing: {str(e)}", error=True)

    def action_next_panel(self) -> None:
        """Switch focus to the next panel."""
        if self.focused == self.task_list_widget:
            self.set_focus(self.task_detail_panel)
        else:
            self.set_focus(self.task_list_widget)

    def action_prev_panel(self) -> None:
        """Switch focus to the previous panel."""
        if self.focused == self.task_detail_panel:
            self.set_focus(self.task_list_widget)
        else:
            self.set_focus(self.task_detail_panel)

    def action_focus_up(self) -> None:
        """Focus handling for up key."""
        # Delegate to appropriate widget if task list is focused
        if self.focused == self.task_list_widget:
            self.task_list_widget.action_cursor_up()

    def action_focus_down(self) -> None:
        """Focus handling for down key."""
        # Delegate to appropriate widget if task list is focused
        if self.focused == self.task_list_widget:
            self.task_list_widget.action_cursor_down()

    # Acciones para implementar teclas rápidas para completar/editar/eliminar
    async def action_complete_task(self) -> None:
        """Complete the currently selected task."""
        if self.task_detail_panel.current_task:
            task_id = str(self.task_detail_panel.current_task.id)
            await self.handle_complete_task(CompleteTask(task_id))

    async def action_edit_task(self) -> None:
        """Edit the currently selected task."""
        if self.task_detail_panel.current_task:
            task_id = str(self.task_detail_panel.current_task.id)
            await self.handle_edit_task(EditTask(task_id))

    async def action_delete_task(self) -> None:
        """Delete the currently selected task."""
        if self.task_detail_panel.current_task:
            task_id = str(self.task_detail_panel.current_task.id)
            await self.handle_delete_task(DeleteTask(task_id))


# --- Main Execution Block ---
if __name__ == "__main__":
    # Configuración de logging
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    log.info("Starting the Habitica TUI App.")
    app = HabiticaTUIApp()
    app.run()
