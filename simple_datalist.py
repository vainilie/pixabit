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

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row highlighting to update detail view."""
        self._handle_selection()

    def on_data_table_row_selected(self, event) -> None:
        """Handle row selection to update detail view."""
        self._handle_selection()

    def _handle_selection(self) -> None:
        """Handle selection of a task in the list."""
        if self.row_count == 0:
            return

        # Get the selected row key (task id)
        try:
            # First try to get directly from cursor_coordinate
            row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
        except (AttributeError, IndexError):
            # Fallback to finding selected task by index
            row_index = self.cursor_coordinate[0] if self.cursor_coordinate else 0
            if 0 <= row_index < len(self.tasks_data):
                row_key = self.tasks_data[row_index].get("id")
            else:
                return

        if row_key:
            # Store the selected task id
            self.selected_task_id = row_key

            # Send message to display task details
            self.post_message(self.ViewTaskDetailsRequest(row_key))
