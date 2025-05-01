"""Generated file by Claude handling the three widgets. TODO review"""

# pixabit/ui/widgets/tasks/task_list_widget.py
from typing import Any, Callable, Dict, List, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Static

from pixabit.helpers._logger import log


class TaskListWidget(DataTable):
    """Widget that displays a list of tasks in a data table."""

    # Reactive properties
    selected_task_id = reactive(None)
    tasks_data = reactive([])
    tag_colors = reactive({})

    class ViewTaskDetailsRequest(Message):
        """Message sent when a task is selected to view details."""

        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    def __init__(self, id: str = None) -> None:
        """Initialize the task list widget."""
        super().__init__(id=id)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.tasks_data = []
        self.tag_colors = {}
        self._selected_idx = 0
        self._loading = False

    async def on_mount(self) -> None:
        """Set up the widget when it's mounted."""
        # Set up columns
        self.add_columns("Type", "Task", "Difficulty", "Tags")

        # Load initial data if any
        await self.load_or_refresh_data()

    async def load_or_refresh_data(self) -> None:
        """Load or refresh task data from the data store."""
        if self._loading:
            return

        self._loading = True
        try:
            # In a real implementation, you'd get this from your data manager
            # For now we'll use dummy data since we don't have access to your actual data
            # This should be replaced with a call to your DataManager
            self.tasks_data = self._get_dummy_tasks()

            # Clear existing rows
            self.clear()

            # Add rows for each task
            for task in self.tasks_data:
                task_type_emoji = self._get_task_type_emoji(task.get("type", "todo"))
                task_text = task.get("text", "")
                difficulty = task.get("priority", "medium")
                tags = self._format_tags(task.get("tags", []))

                self.add_row(task_type_emoji, task_text, difficulty, tags, key=task.get("id", ""))

            # Select the first row if available
            if len(self.tasks_data) > 0 and self.row_count > 0:
                self.cursor_coordinate = (0, 0)
                self._handle_selection()
        except Exception as e:
            log.error(f"Error loading task data: {e}")
        finally:
            self._loading = False

    def _get_dummy_tasks(self) -> List[Dict[str, Any]]:
        """Return dummy task data for development/testing."""
        return [
            {
                "id": "task1",
                "type": "habit",
                "text": "Exercise daily",
                "notes": "30 minutes of cardio or strength training",
                "priority": "high",
                "value": 10.5,
                "tags": ["health", "fitness"],
            },
            {
                "id": "task2",
                "type": "daily",
                "text": "Study Python",
                "notes": "Work on Textual UI projects",
                "priority": "medium",
                "value": 5.0,
                "tags": ["education", "programming"],
            },
            {
                "id": "task3",
                "type": "todo",
                "text": "Buy groceries",
                "notes": "Need vegetables, fruit, and bread",
                "priority": "low",
                "value": 2.0,
                "tags": ["chores", "shopping"],
            },
        ]

    def _get_task_type_emoji(self, task_type: str) -> str:
        """Get an emoji representing the task type."""
        return {"habit": "⚡", "daily": "🔄", "todo": "📝", "reward": "🎁"}.get(task_type.lower(), "❓")

    def _format_tags(self, tags: List[str]) -> str:
        """Format tags into a display string."""
        if not tags:
            return ""
        return ", ".join(tags)

    def on_data_table_row_selected(self) -> None:
        """Handle row selection to update detail view."""
        self._handle_selection()

    def _handle_selection(self) -> None:
        """Handle selection of a task in the list."""
        if self.row_count == 0:
            return

        # Get the selected row key (task id)
        selected_row = self.get_row_at(self.cursor_coordinate[0])
        if selected_row and selected_row.key is not None:
            task_id = selected_row.key

            # Store the selected task id
            self.selected_task_id = task_id

            # Send message to display task details
            self.post_message(self.ViewTaskDetailsRequest(task_id))


# # pixabit/ui/widgets/tasks/task_detail_panel.py
# from typing import Any, Dict, List

# from textual.containers import Horizontal
# from textual.message import Message
# from textual.reactive import reactive
# from textual.widgets import Button


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


# # pixabit/ui/widgets/tasks/task_tab_container.py
# from typing import Any, Dict, Optional

# from textual.app import ComposeResult
# from textual.message import Message

# from pixabit.ui.widgets.tasks.task_detail_panel import TaskDetailPanel
# from pixabit.ui.widgets.tasks.task_list_widget import TaskListWidget


class TaskTabContainer(Container):
    """Container widget that holds both task list and detail panel."""

    class ScoreTaskRequest(Message):
        """Message for scoring a task."""

        def __init__(self, task_id: str, direction: str) -> None:
            self.task_id = task_id
            self.direction = direction
            super().__init__()

    def __init__(self, id: str = None, data_manager=None, api_client=None, on_data_changed: Optional[Callable] = None) -> None:
        """Initialize the task tab container."""
        super().__init__(id=id)
        self.data_manager = data_manager
        self.api_client = api_client
        self.on_data_changed = on_data_changed
        self._task_list = None
        self._task_detail = None

    def compose(self) -> ComposeResult:
        """Compose the layout with task list and detail panel."""
        yield Static("Tasks", classes="tab-header")

        with Horizontal(id="tasks-content-container"):
            yield TaskListWidget(id="task-list-widget")
            yield TaskDetailPanel(id="task-detail-panel")

    async def on_mount(self) -> None:
        """Configure the widget when it's mounted."""
        # Get references to child widgets
        self._task_list = self.query_one(TaskListWidget)
        self._task_detail = self.query_one(TaskDetailPanel)

        # Set tag colors if available from data manager
        if self.data_manager and hasattr(self.data_manager, "get_tag_colors"):
            tag_colors = self.data_manager.get_tag_colors()
            self._task_list.tag_colors = tag_colors
            self._task_detail.tag_colors = tag_colors

        # Initial data load
        await self._task_list.load_or_refresh_data()

    async def refresh_data(self) -> None:
        """Refresh the task data."""
        await self._task_list.load_or_refresh_data()

        # If there's a task selected in the detail panel, refresh it too
        if self._task_detail.current_task:
            task_id = self._task_detail.current_task.get("id")
            if task_id and self.data_manager:
                updated_task = self.data_manager.get_task_by_id(task_id)
                self._task_detail.current_task = updated_task

    # Message handlers

    @on(TaskListWidget.ViewTaskDetailsRequest)
    def handle_view_task_details(self, message: TaskListWidget.ViewTaskDetailsRequest) -> None:
        """Handle request to view task details."""
        if not self.data_manager:
            log.warning("No data manager available to fetch task details")
            return

        try:
            task = self.data_manager.get_task_by_id(message.task_id)
            self._task_detail.current_task = task
        except Exception as e:
            log.error(f"Error fetching task details: {e}")
            self._task_detail.current_task = None

    @on(TaskDetailPanel.ScoreTaskDetail)
    def handle_score_task(self, message: TaskDetailPanel.ScoreTaskDetail) -> None:
        """Handle scoring a task from the detail panel."""
        # Forward the message to the parent
        self.post_message(self.ScoreTaskRequest(message.task_id, message.direction))

    @on(TaskDetailPanel.CompleteTask)
    async def handle_complete_task(self, message: TaskDetailPanel.CompleteTask) -> None:
        """Handle completing a task."""
        if not self.data_manager:
            log.warning("No data manager available to complete task")
            return

        try:
            if self.data_manager.complete_task(message.task_id):
                # Notify that data has changed
                if self.on_data_changed:
                    await self.on_data_changed({"action": "complete", "task_id": message.task_id})

                # Refresh task list
                await self.refresh_data()
        except Exception as e:
            log.error(f"Error completing task: {e}")

    @on(TaskDetailPanel.DeleteTask)
    async def handle_delete_task(self, message: TaskDetailPanel.DeleteTask) -> None:
        """Handle deleting a task."""
        if not self.data_manager:
            log.warning("No data manager available to delete task")
            return

        try:
            if self.data_manager.delete_task(message.task_id):
                # Notify that data has changed
                if self.on_data_changed:
                    await self.on_data_changed({"action": "delete", "task_id": message.task_id})

                # Clear detail panel and refresh list
                self._task_detail.current_task = None
                await self.refresh_data()
        except Exception as e:
            log.error(f"Error deleting task: {e}")

    @on(TaskDetailPanel.EditTask)
    async def handle_edit_task(self, message: TaskDetailPanel.EditTask) -> None:
        """Handle editing a task."""
        if not self.data_manager:
            log.warning("No data manager available to edit task")
            return

        # In a real implementation, you would show a form/modal to edit the task
        log.info(f"Edit task request for task {message.task_id} - not implemented yet")

        # For now, just notify that we would edit the task
        if self.on_data_changed:
            await self.on_data_changed({"action": "edit", "task_id": message.task_id})
