from typing import Any, Dict, List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane

from pixabit.helpers._logger import log
from pixabit.models.task import Task
from pixabit.ui.widgets.table_detail_panel import (
    CompleteTask,
    DeleteTask,
    EditTask,
    ScoreTaskDetail,
    TaskDetailPanel,
)
from pixabit.ui.widgets.table_list_panel import (
    ScoreTaskRequest,
    TaskListWidget,
    ViewTaskDetailsRequest,
)


class TaskView(Widget):
    """A container widget that holds a tabbed task list and a detail panel side by side.
    This widget handles the communication between the TaskListWidget and TaskDetailPanel.
    """

    BINDINGS = [
        Binding(key="c", action="complete_task", description="Complete task"),
        Binding(key="e", action="edit_task", description="Edit task"),
        Binding(key="d", action="delete_task", description="Delete task"),
    ]

    def __init__(
        self,
        task_service=None,
        id: str = "task-view",
        **kwargs,
    ):
        super().__init__(id=id, **kwargs)
        self.task_service = task_service
        self.tag_colors = {}
        self._last_selected_task_id = None

    def compose(self) -> ComposeResult:
        """Compose the TaskView with a task list and detail panel."""
        with Horizontal(id="task-view-container"):
            with Container(id="task-list-container"):
                with TabbedContent(id="task-tabs"):
                    with TabPane("Todos", id="todo-tab"):
                        yield TaskListWidget(task_type="todo", id="todo-list")
                    with TabPane("Dailies", id="daily-tab"):
                        yield TaskListWidget(task_type="daily", id="daily-list")
                    with TabPane("Habits", id="habit-tab"):
                        yield TaskListWidget(task_type="habit", id="habit-list")
                    with TabPane("Rewards", id="reward-tab"):
                        yield TaskListWidget(task_type="reward", id="reward-list")
                    with TabPane("All", id="all-tab"):
                        yield TaskListWidget(task_type="all", id="all-list")

            # Task detail panel on the right
            yield TaskDetailPanel(id="task-detail-panel")

    async def on_mount(self) -> None:
        """Initialize after widget is mounted."""
        # Get all task list widgets and detail panel
        task_lists = self.query(TaskListWidget)
        detail_panel = self.query_one(TaskDetailPanel)

        # Initialize tag colors in all widgets
        self.tag_colors = await self._get_tag_colors()
        for task_list in task_lists:
            task_list.tag_colors = self.tag_colors
        detail_panel.tag_colors = self.tag_colors

        # Initialize task lists with data
        for task_list in task_lists:
            await task_list.load_or_refresh_data()

    async def _get_tag_colors(self) -> Dict[str, str]:
        """Get tag colors from the data store."""
        if hasattr(self.app, "datastore") and self.app.datastore:
            try:
                return await self.app.run_in_thread(self.app.datastore.get_tag_colors)
            except Exception as e:
                log.error(f"Error fetching tag colors: {e}")
        return {}

    async def refresh_all_task_lists(self) -> None:
        """Refresh all task list widgets."""
        task_lists = self.query(TaskListWidget)
        for task_list in task_lists:
            await task_list.load_or_refresh_data()

    # Event handlers for communication between widgets

    async def handle_view_task_details(self, event: ViewTaskDetailsRequest) -> None:
        """Handle request to view task details."""
        log.info(f"TaskView: Request to view details for task {event.task_id}")
        detail_panel = self.query_one(TaskDetailPanel)

        try:
            # Store the last selected task ID
            self._last_selected_task_id = event.task_id

            # Get task from data store and update detail panel
            task = await self.app.run_in_thread(self.app.datastore.get_task_by_id, event.task_id)

            if task:
                detail_panel.current_task = task
            else:
                detail_panel.current_task = None
                log.warning(f"Task with ID {event.task_id} not found.")
        except Exception as e:
            log.error(f"Error fetching task details: {e}")
            detail_panel.current_task = None

    async def handle_score_task(self, event: Message) -> None:
        """Handle request to score a task."""
        task_id = event.task_id
        direction = event.direction
        log.info(f"TaskView: Scoring task {task_id} {direction}")

        try:
            # Score the task
            result = await self.app.run_in_thread(self.app.datastore.score_task, task_id, direction)

            if result:
                # Refresh all task lists and update detail panel
                await self.refresh_all_task_lists()

                # Update detail panel if it's showing the scored task
                detail_panel = self.query_one(TaskDetailPanel)
                if detail_panel.current_task and getattr(detail_panel.current_task, "id", None) == task_id:
                    task = await self.app.run_in_thread(self.app.datastore.get_task_by_id, task_id)
                    detail_panel.current_task = task
            else:
                log.warning(f"Failed to score task {task_id}")
        except Exception as e:
            log.error(f"Error scoring task: {e}")

    async def handle_complete_task(self, event: CompleteTask) -> None:
        """Handle request to complete a task."""
        task_id = event.task_id
        log.info(f"TaskView: Completing task {task_id}")

        try:
            # Complete the task
            result = await self.app.run_in_thread(self.app.datastore.complete_task, task_id)

            if result:
                # Refresh all task lists and clear detail panel
                await self.refresh_all_task_lists()

                # Clear detail panel
                detail_panel = self.query_one(TaskDetailPanel)
                detail_panel.current_task = None
            else:
                log.warning(f"Failed to complete task {task_id}")
        except Exception as e:
            log.error(f"Error completing task: {e}")

    async def handle_delete_task(self, event: DeleteTask) -> None:
        """Handle request to delete a task."""
        task_id = event.task_id
        log.info(f"TaskView: Deleting task {task_id}")

        try:
            # Delete the task
            result = await self.app.run_in_thread(self.app.datastore.delete_task, task_id)

            if result:
                # Refresh all task lists and clear detail panel
                await self.refresh_all_task_lists()

                # Clear detail panel
                detail_panel = self.query_one(TaskDetailPanel)
                detail_panel.current_task = None
            else:
                log.warning(f"Failed to delete task {task_id}")
        except Exception as e:
            log.error(f"Error deleting task: {e}")

    async def handle_edit_task(self, event: EditTask) -> None:
        """Handle request to edit a task."""
        task_id = event.task_id
        log.info(f"TaskView: Edit request for task {task_id}")

        # This would be implemented when you have an edit task dialog
        log.info("Edit task feature not yet implemented")

    # Actions for key bindings

    async def action_complete_task(self) -> None:
        """Action to complete the currently selected task."""
        detail_panel = self.query_one(TaskDetailPanel)
        if detail_panel.current_task:
            task_id = getattr(detail_panel.current_task, "id", None)
            if task_id:
                await self.handle_complete_task(CompleteTask(task_id))

    async def action_edit_task(self) -> None:
        """Action to edit the currently selected task."""
        detail_panel = self.query_one(TaskDetailPanel)
        if detail_panel.current_task:
            task_id = getattr(detail_panel.current_task, "id", None)
            if task_id:
                await self.handle_edit_task(EditTask(task_id))

    async def action_delete_task(self) -> None:
        """Action to delete the currently selected task."""
        detail_panel = self.query_one(TaskDetailPanel)
        if detail_panel.current_task:
            task_id = getattr(detail_panel.current_task, "id", None)
            if task_id:
                await self.handle_delete_task(DeleteTask(task_id))
