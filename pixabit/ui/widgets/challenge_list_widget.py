from pixabit.helpers._logger import log
from pixabit.helpers._textual import (
    Button,
    ComposeResult,
    Container,
    DataTable,
    Horizontal,
    Label,
    Message,
    ScrollableContainer,
    Select,
    Static,
    TabbedContent,
    TabPane,
    Vertical,
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
