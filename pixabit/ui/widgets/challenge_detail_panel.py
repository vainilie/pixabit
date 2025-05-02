from pixabit.helpers._logger import log
from pixabit.helpers._md_to_rich import MarkdownRenderer
from pixabit.helpers._textual import Button, ComposeResult, DataTable, Horizontal, Markdown, Message, ScrollableContainer, Select, Static, Vertical, on, reactive
from pixabit.models.challenge import Challenge


def md_render(str):
    return MarkdownRenderer.markdown_to_rich_text(str)


class ChallengeDetailPanel(ScrollableContainer):
    """Panel that displays challenge details and actions."""

    current_challenge = reactive(None)
    loading_tasks = reactive(False)

    # Define messages
    class ScoreChallengeDetail(Message):
        """Message for viewing challenge tasks."""

        def __init__(self, challenge_id: str, get_all: bool = False) -> None:
            self.challenge_id = challenge_id
            self.get_all = get_all
            super().__init__()

    class JoinChallenge(Message):
        """Message for joining a challenge."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    class LeaveChallenge(Message):
        """Message for leaving a challenge."""

        def __init__(self, challenge_id: str, keep: str) -> None:
            self.challenge_id = challenge_id
            self.keep = keep
            super().__init__()

    class CompleteChallenge(Message):
        """Message for completing a challenge."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    class EditChallenge(Message):
        """Message for editing a challenge."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    class ViewChallengeTasks(Message):
        """Message for viewing challenge tasks."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    def __init__(self, id: str = None, challenge_service=None) -> None:
        """Initialize the challenge detail panel.

        Args:
            id: Widget ID.
            challenge_service: The challenge service for API interactions.
        """
        super().__init__(id=id)
        self.challenge_service = challenge_service
        self._detail_content = None
        self._task_list = None
        self._keep_option = "keep-all"  # Default option for leaving challenges

    def compose(self) -> ComposeResult:
        """Compose the challenge detail panel."""
        yield Static("Select a challenge to view details", id="challenge-detail-header")

        with Vertical(id="challenge-detail-content"):

            yield Markdown("", id="challenge-details")

        with Horizontal(id="challenge-action-buttons", classes="hidden"):
            yield Button("Join", id="join-challenge-btn", variant="success")
            yield Button("Leave ", id="leave-challenge-btn", variant="error")
            yield Select([("Keep", "keep-all"), ("Remove Tasks", "remove-all")], id="leave-option-select", value="keep-all")
            yield Button("Tasks", id="view-tasks-btn", variant="primary")
            # yield Button("Edit", id="edit-challenge-btn", variant="default")

        with Vertical(id="challenge-tasks-container", classes="hidden"):
            yield Static("Challenge Tasks", id="tasks-header")
            yield DataTable(id="challenge-tasks-table")
            yield Button("+", id="load-more-tasks-btn", variant="primary")

    def watch_current_challenge(self, challenge: Challenge) -> None:
        """Watch for changes to the current_challenge property."""
        self._update_detail_view()

    def _update_detail_view(self) -> None:
        """Update the detail view with current challenge data."""
        detail_content = self.query_one("#challenge-details")
        action_buttons = self.query_one("#challenge-action-buttons")
        tasks_container = self.query_one("#challenge-tasks-container")

        if not self.current_challenge:
            detail_content.update("Select a challenge to view details")
            action_buttons.add_class("hidden")
            tasks_container.add_class("hidden")
            return

        # Format challenge details as markdown
        details = f"""# {self.current_challenge.name}
**Description:** {self.current_challenge.description if hasattr(self.current_challenge, 'description') else 'No description'}
**Owner:** {self.current_challenge.leader.name if hasattr(self.current_challenge, 'leader') else 'Unknown'}
**Member Count:** {self.current_challenge.memberCount if hasattr(self.current_challenge, 'memberCount') else 'Unknown'}
**Prize:** {self.current_challenge.prize if hasattr(self.current_challenge, 'prize') else '0'} gems
**Joined:** {"Yes" if self.current_challenge.joined else "No"}
**Created:** {self.current_challenge.createdAt if hasattr(self.current_challenge, 'createdAt') else 'Unknown'}
"""
        detail_content.update(details)

        # Update action buttons based on whether user has joined the challenge
        action_buttons.remove_class("hidden")
        join_btn = self.query_one("#join-challenge-btn")
        leave_btn = self.query_one("#leave-challenge-btn")
        leave_options = self.query_one("#leave-option-select")

        if self.current_challenge.joined is False:
            join_btn(disabled=False)
            leave_btn(disabled=True)
            leave_options(disabled=True)
        else:
            join_btn(disabled=True)
            leave_btn(disabled=False)
            leave_options(disabled=False)

        # Initially hide tasks
        tasks_container.add_class("hidden")

    async def _load_challenge_tasks(self) -> None:
        """Load tasks for the current challenge."""
        if not self.current_challenge or not self.challenge_service:
            return

        self.loading_tasks = True
        tasks_container = self.query_one("#challenge-tasks-container")
        tasks_table = self.query_one("#challenge-tasks-table")

        try:
            # Fetch tasks for the current challenge
            tasks = await self.challenge_service.fetch_challenge_tasks(self.current_challenge.id)

            if tasks:
                # Set up table if not already done
                if not tasks_table.columns:
                    tasks_table.add_columns("Text", "Type", "Difficulty", "Notes")

                # Clear existing rows
                tasks_table.clear()

                # Add task rows
                for task in tasks:
                    text = task.text if hasattr(task, "text") else "Unknown"
                    task_type = task.type if hasattr(task, "type") else "Unknown"
                    difficulty = task.priority if hasattr(task, "priority") else "1"
                    notes = task.notes if hasattr(task, "notes") else ""

                    tasks_table.add_row(text, task_type, difficulty, notes)

                # Show the tasks container
                tasks_container.remove_class("hidden")
            else:
                tasks_table.clear()
                if not tasks_table.columns:
                    tasks_table.add_columns("Text", "Type", "Difficulty", "Notes")
                tasks_table.add_row("No tasks found for this challenge", "", "", "")
                tasks_container.remove_class("hidden")

        except Exception as e:
            log.exception(f"Error loading challenge tasks: {e}")
            tasks_table.clear()
            if not tasks_table.columns:
                tasks_table.add_columns("Error")
            tasks_table.add_row(f"Error loading tasks: {str(e)}")
            tasks_container.remove_class("hidden")
        finally:
            self.loading_tasks = False

    # Event handlers

    @on(Button.Pressed, "#join-challenge-btn")
    async def handle_join_challenge(self) -> None:
        """Handle join challenge button press."""
        if not self.current_challenge:
            return

        self.post_message(self.JoinChallenge(self.current_challenge.id))

    @on(Button.Pressed, "#leave-challenge-btn")
    async def handle_leave_challenge(self) -> None:
        """Handle leave challenge button press."""
        if not self.current_challenge:
            return

        keep_option = self.query_one("#leave-option-select").value
        self.post_message(self.LeaveChallenge(self.current_challenge.id, keep_option))

    @on(Select.Changed, "#leave-option-select")
    def handle_leave_option_change(self, event: Select.Changed) -> None:
        """Handle leave option change."""
        self._keep_option = event.value

    @on(Button.Pressed, "#view-tasks-btn")
    async def handle_view_tasks(self) -> None:
        """Handle view tasks button press."""
        if not self.current_challenge:
            return

        self.post_message(self.ViewChallengeTasks(self.current_challenge.id))
        await self._load_challenge_tasks()

    @on(Button.Pressed, "#edit-challenge-btn")
    def handle_edit_challenge(self) -> None:
        """Handle edit challenge button press."""
        if not self.current_challenge:
            return

        self.post_message(self.EditChallenge(self.current_challenge.id))

    @on(Button.Pressed, "#load-more-tasks-btn")
    async def handle_load_more_tasks(self) -> None:
        """Handle load more tasks button press."""
        # This would implement pagination for tasks if the API supports it
        await self._load_challenge_tasks()


from pixabit.helpers._textual import (
    Button,
    ComposeResult,
    Container,
    Label,
    Message,
    ScrollableContainer,
    Select,
    TabbedContent,
    TabPane,
    on,
    reactive,
)
from pixabit.models.challenge import Challenge, ChallengeList

# Import our custom Pagination widget
from .pagination import Pagination


class ChallengeListWidget(Container):
    """Widget that displays a list of challenges with filtering and pagination."""

    # Define reactive properties
    challenges_data = reactive([])
    current_page = reactive(0)
    total_pages = reactive(50)
    member_only = reactive(False)
    loading = reactive(False)

    # Define constants
    ITEMS_PER_PAGE = 10

    class ViewChallengeDetailsRequest(Message):
        """Message requesting to view challenge details."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    def __init__(self, id: str = None, challenge_service=None) -> None:
        """Initialize the challenge list widget.

        Args:
            id: Widget ID.
            challenge_service: The challenge service for API interactions.
        """
        super().__init__(id=id)
        self.challenge_service = challenge_service
        # Initialize widget references to None; they will be assigned in compose
        self._data_table = None
        self._pagination = None
        self._tabbed_content = None
        self.cursor_type = "row"  # Still applies to the DataTable

    def compose(self) -> ComposeResult:
        """Compose the challenge list widget with tabs, data table, and pagination."""
        with Vertical(id="challenge-list-container"):
            with Horizontal(id="challenge-filter-controls"):
                # Create and yield the TabbedContent with tab titles
                with TabbedContent(id="challenges-tabs") as tabbed_content:
                    self._tabbed_content = tabbed_content
                    yield TabPane("All Challenges", id="tab-all")
                    yield TabPane("Member Challenges", id="tab-member")

            # Yield the DataTable and Pagination widgets

            self._data_table = DataTable(id="challenge-data-table")
            yield self._data_table
            self._pagination = Pagination(
                page_count=50,
                current_page=self.current_page + 1,
                page_size=self.ITEMS_PER_PAGE,
                id="challenge-pagination",
            )
            yield self._pagination

    async def on_mount(self) -> None:
        """Configure the widget when it's mounted."""
        # Set cursor type on the data table
        self._data_table.cursor_type = "row"

        # Set up the data table columns
        self._data_table.add_columns("Name", "Member Count", "Prize", "Joined")

        # Initial data load will happen when the TabbedContent.TabActivated event fires

    async def load_or_refresh_data(self) -> None:
        """Load or refresh challenge data from the service."""
        if not self.challenge_service:
            log.warning("No challenge service available to load challenges")
            return

        if self.loading:
            log.debug("Load already in progress, skipping.")
            return  # Prevent duplicate loads

        # Ensure widgets are initialized
        if self._data_table is None or self._pagination is None:
            log.error("DataTable or Pagination widget is not initialized.")
            return

        self.loading = True
        self._data_table.loading = True  # Show loading indicator

        try:
            log.debug(f"Fetching challenges: member_only={self.member_only}, page={self.current_page}")

            # Fetch challenges using the challenge service
            challenge_list_response = await self.challenge_service.fetch_challenges(member_only=self.member_only, page=self.current_page)

            # Process the response
            self._process_challenge_response(challenge_list_response)

        except Exception as e:
            log.exception(f"Error loading challenges: {e}")
            self._handle_load_error("Error loading challenges.")

        finally:
            self.loading = False
            if self._data_table is not None:
                self._data_table.loading = False  # Hide loading indicator

    def _process_challenge_response(self, challenge_list_response):
        """Process the challenge list response and update the UI."""
        if challenge_list_response and hasattr(challenge_list_response, "challenges"):
            self.challenges_data = challenge_list_response.challenges

            # Update total_pages based on API response
            if hasattr(challenge_list_response, "totalPages"):
                self.total_pages = challenge_list_response.totalPages
            else:
                log.warning("API response missing totalPages. Using default calculation.")
                self.total_pages = max(1, (len(self.challenges_data) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)

            # Update the data table
            self._data_table.clear()

            if not self.challenges_data:
                self._data_table.add_row("No challenges found for this filter.", "", "", "", "")
            else:
                for challenge in self.challenges_data:
                    self._data_table.add_row(
                        getattr(challenge, "name", "N/A"),
                        # getattr(challenge.leader, "name", "Unknown") if hasattr(challenge, "leader") else "Unknown",
                        str(getattr(challenge, "memberCount", "0")),
                        str(getattr(challenge, "prize", "0")),
                        "✓" if getattr(challenge, "joined", False) else "",
                    )

            # Update pagination
            self._pagination.page_count = self.total_pages
            self._pagination.current_page = self.current_page + 1  # Convert 0-indexed to 1-indexed
        else:
            log.warning("Failed to load challenges or empty result/unexpected format")
            self._handle_load_error("Failed to load challenges.")

    def _handle_load_error(self, error_message):
        """Handle loading errors by resetting state and showing an error message."""
        self.challenges_data = []
        self._data_table.clear()
        self.total_pages = 100  # Reset total pages
        self._pagination.page_count = self.total_pages
        self._pagination.current_page = 1  # Reset to first page
        self._data_table.add_row(error_message, "", "", "", "")  # Display error message

    # Event handlers

    @on(DataTable.RowHighlighted)
    def handle_row_selected(self, event: DataTable.RowHighlighted) -> None:
        """Handle row selection in the data table."""
        # Check if the selected row index is within the bounds of the loaded data
        if 0 <= event.cursor_row < len(self.challenges_data):
            challenge = self.challenges_data[event.cursor_row]
            challenge_id = getattr(challenge, "id", None)

            if challenge_id:
                log.debug(f"Selected challenge ID: {challenge_id}")
                self.post_message(self.ViewChallengeDetailsRequest(challenge_id))
            else:
                log.warning(f"Challenge at row {event.cursor_row} is missing 'id' attribute.")
        else:
            log.warning(f"Row index {event.cursor_row} is out of bounds. challenges_data length: {len(self.challenges_data)}")

    @on(TabbedContent.TabActivated)
    async def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab activation change."""
        log.debug(f"Tab activated: {event.tab.id}")

        # Determine the filter based on the activated tab's ID
        self.member_only = event.tab.id == "tab-member"
        log.debug(f"Switched to {'Member' if self.member_only else 'All'} tab.")

        # Reset to the first page when changing tabs
        self.current_page = 0

        # Load data for the newly selected filter
        await self.load_or_refresh_data()

    @on(Pagination.PageChanged)
    async def handle_page_changed(self, event: Pagination.PageChanged) -> None:
        """Handle pagination page change."""
        log.debug(f"Page changed to: {event.page}")

        # Convert from 1-indexed (UI) to 0-indexed (API)
        self.current_page = event.page - 1
        await self.load_or_refresh_data()

    # If you want to add a refresh button:
    # @on(Button.Pressed, "#refresh-challenges-btn")
    # async def handle_refresh_button(self) -> None:
    #     """Handle refresh button press."""
    #     log.debug("Refresh button pressed.")
    #     await self.load_or_refresh_data()
