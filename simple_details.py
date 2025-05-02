class TaskDetailPanel(Vertical):
    """Panel for displaying and interacting with task details."""

    # Messages for task interactions
    class ScoreTaskDetail(Message):
        """Message for scoring a task from the detail panel."""

        def __init__(self, task_id: str, direction: str) -> None:
            self.task_id = task_id
            self.direction = direction
            super().__init__()

    class CompleteTask(Message):
        """Message for completing a task."""

        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    class DeleteTask(Message):
        """Message for deleting a task."""

        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    class EditTask(Message):
        """Message for editing a task."""

        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    # Reactive property for current task
    _current_task = reactive(None)

    @property
    def current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current task data."""
        return self._current_task

    @current_task.setter
    def current_task(self, task: Optional[Dict[str, Any]]) -> None:
        """Set the current task and update the display."""
        self._current_task = task
        self._update_display()

    def __init__(self, id: str = None) -> None:
        """Initialize the task detail panel."""
        super().__init__(id=id)
        self.tag_colors = {}
        self._current_task = None

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        # Task details content
        with Container(id="task-details-content"):
            yield Static("No task selected", id="task-detail-text")
            yield Static("", id="task-detail-notes")
            yield Static("", id="task-detail-meta")

        # Task action buttons
        with Vertical(id="task-detail-actions"):
            with Horizontal(id="primary-actions"):
                yield Button("+", id="score-up-btn", classes="score-button", disabled=True)
                yield Button("-", id="score-down-btn", classes="score-button", disabled=True)
                yield Button("Complete", id="complete-btn", disabled=True)

            with Horizontal(id="secondary-actions"):
                yield Button("Edit", id="edit-btn", disabled=True)
                yield Button("Delete", id="delete-btn", disabled=True)

    def _update_display(self) -> None:
        """Update the display with the current task data."""
        detail_text = self.query_one("#task-detail-text", Static)
        detail_notes = self.query_one("#task-detail-notes", Static)
        detail_meta = self.query_one("#task-detail-meta", Static)

        score_up_btn = self.query_one("#score-up-btn", Button)
        score_down_btn = self.query_one("#score-down-btn", Button)
        complete_btn = self.query_one("#complete-btn", Button)
        edit_btn = self.query_one("#edit-btn", Button)
        delete_btn = self.query_one("#delete-btn", Button)

        if self._current_task:
            # Task exists - show details
            task_type = self._current_task.get("type", "unknown")
            task_text = self._current_task.get("text", "No text")
            task_notes = self._current_task.get("notes", "No notes")
            task_priority = self._current_task.get("priority", "medium")
            task_value = self._current_task.get("value", 0)

            # Update text fields
            detail_text.update(f"[b]{task_text}[/b]")
            detail_notes.update(task_notes)

            # Format meta information
            meta_text = f"Type: {task_type.capitalize()}\n"
            meta_text += f"Difficulty: {task_priority.capitalize()}\n"
            meta_text += f"Value: {task_value}\n"

            if "tags" in self._current_task and self._current_task["tags"]:
                meta_text += f"Tags: {', '.join(self._current_task['tags'])}"

            detail_meta.update(meta_text)

            # Enable buttons
            score_up_btn.disabled = False
            score_down_btn.disabled = task_type not in ["habit", "daily", "todo"]
            complete_btn.disabled = task_type not in ["daily", "todo"]
            edit_btn.disabled = False
            delete_btn.disabled = False
        else:
            # No task selected - clear display
            detail_text.update("No task selected")
            detail_notes.update("")
            detail_meta.update("")

            # Disable buttons
            score_up_btn.disabled = True
            score_down_btn.disabled = True
            complete_btn.disabled = True
            edit_btn.disabled = True
            delete_btn.disabled = True

    # Event handlers for button actions

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if not self._current_task:
            return

        task_id = self._current_task.get("id", "")

        # Handle the different buttons
        button_id = event.button.id
        if button_id == "score-up-btn":
            self.post_message(self.ScoreTaskDetail(task_id, "up"))
        elif button_id == "score-down-btn":
            self.post_message(self.ScoreTaskDetail(task_id, "down"))
        elif button_id == "complete-btn":
            self.post_message(self.CompleteTask(task_id))
        elif button_id == "edit-btn":
            self.post_message(self.EditTask(task_id))
        elif button_id == "delete-btn":
            self.post_message(self.DeleteTask(task_id))
