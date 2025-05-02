from rich.text import Text

from pixabit.helpers._logger import log
from pixabit.helpers._md_to_rich import MarkdownRenderer
from pixabit.helpers._rich import Text
from pixabit.helpers._textual import (
    Button,
    ComposeResult,
    Container,
    DataTable,
    Horizontal,
    Label,
    Markdown,
    Message,
    Screen,
    ScrollableContainer,
    Select,
    Static,
    TabbedContent,
    TabPane,
    Tree,
    Vertical,
    on,
    reactive,
)
from pixabit.models.challenge import Challenge, ChallengeList

MarkdownRenderer = MarkdownRenderer()


# Tree navigation implementation
class ChallengeTree(Tree):
    """Tree widget for navigating challenges with pagination support."""

    def __init__(self, label="Challenges", *children, id=None):
        super().__init__(label, *children, id=id)
        # Track the current filter and pagination state
        self.member_only = False
        self.current_page = 0
        self.total_pages = 10
        self._challenge_map = {}  # Maps node IDs to challenge objects

    def populate(self, challenges, member_only=False, current_page=0, total_pages=1):
        """Populate the tree with challenge nodes."""
        self.clear()
        self._challenge_map = {}

        # Add filter nodes
        filter_node = self.root.add("Filters", expand=True)

        # Create filter nodes with visual indication of current selection
        all_prefix = "► " if not member_only else "  "
        member_prefix = "► " if member_only else "  "

        all_node = filter_node.add(f"{all_prefix}All Challenges", data={"filter": "all"})
        member_node = filter_node.add(f"{member_prefix}My Challenges", data={"filter": "member"})

        # Add pagination info if there are multiple pages
        if total_pages > 1:
            page_info = f"Page {current_page + 1} of {total_pages}"
            pagination_node = self.root.add(page_info, expand=True)

            # Add navigation options if needed
            if current_page > 0:
                pagination_node.add("◀ Previous Page", data={"action": "prev_page"})

            if current_page < total_pages - 1:
                pagination_node.add("▶ Next Page", data={"action": "next_page"})

        # Add challenges
        challenges_node = self.root.add(f"Challenges ({len(challenges)})", expand=True)

        for challenge in challenges:
            # Format the node label with joined status indicator
            joined_indicator = "✓ " if getattr(challenge, "joined", False) else "  "
            challenge_name = getattr(challenge, "name", "Unknown Challenge")
            member_count = getattr(challenge, "memberCount", 0)
            prize = getattr(challenge, "prize", 0)

            # Create a formatted node label
            label = f"{joined_indicator}{challenge_name} ({member_count} members, {prize} gems)"

            # Add node and store the challenge object mapping
            node = challenges_node.add(label)
            node_id = id(node)
            self._challenge_map[node_id] = challenge

        # Expand the root to show filters and challenges
        self.root.expand()

    def get_challenge_from_node(self, node):
        """Get the challenge object associated with a node."""
        return self._challenge_map.get(id(node))


class ChallengeTasksPanel(Vertical):
    """Panel that displays challenge tasks as a markdown list with filtering options."""

    def __init__(self, id=None, challenge_service=None):
        super().__init__(id=id)
        self.challenge_service = challenge_service
        self.challenge_id = None
        self.loading = False
        self.task_type_filter = "all"
        self.sort_by = "priority"

    def compose(self) -> ComposeResult:
        """Compose the tasks panel."""
        with Horizontal(id="tasks-header"):
            yield Static("Challenge Tasks", id="tasks-title")

        # Using Markdown widget instead of DataTable
        yield ScrollableContainer(Markdown("*Select a challenge to view its tasks*", id="tasks-markdown"), id="tasks-container")

    async def load_tasks(self, challenge_id):
        """Load tasks for a challenge and display as markdown."""
        if not challenge_id or not self.challenge_service:
            return

        self.challenge_id = challenge_id
        self.loading = True
        tasks_markdown = self.query_one("#tasks-markdown")

        try:
            # Indicate loading
            tasks_markdown.update("*Loading tasks...*")

            # Fetch tasks from service
            tasks = await self.challenge_service.fetch_challenge_tasks(challenge_id)

            if tasks and len(tasks) > 0:
                # Filter tasks if needed
                if self.task_type_filter != "all":
                    tasks = [t for t in tasks if hasattr(t, "type") and t.type.lower() == self.task_type_filter.lower()]

                # Sort tasks
                if self.sort_by == "priority":
                    tasks = sorted(tasks, key=lambda t: getattr(t, "priority", 999), reverse=False)
                elif self.sort_by == "created":
                    tasks = sorted(tasks, key=lambda t: getattr(t, "createdAt", ""), reverse=True)

                # Generate markdown content
                md_content = "# Task List\n\n"

                for i, task in enumerate(tasks):
                    text = task.text if hasattr(task, "text") else "Unknown Task"
                    task_type = task.type if hasattr(task, "type") else "Unknown"
                    priority = task.priority if hasattr(task, "priority") else "1"
                    notes = task.notes if hasattr(task, "notes") else ""

                    # Format each task as a markdown list item
                    md_content += f"- **[{task_type}]** {text}"

                    # Add priority indicator with stars
                    if priority and str(priority).isdigit():
                        stars = "⭐" * int(priority)
                        md_content += f" {stars}"

                    # Add notes if they exist
                    if notes:
                        md_content += f"\n  - *{notes}*"

                    md_content += "\n"

                tasks_markdown.update(md_content)
            else:
                tasks_markdown.update("*No tasks found for this challenge*")

        except Exception as e:
            log.exception(f"Error loading challenge tasks: {e}")
            tasks_markdown.update(f"**Error loading tasks:** {str(e)}")

        finally:
            self.loading = False

    @on(Button.Pressed, "#refresh-tasks-btn")
    async def refresh_tasks(self):
        """Refresh the tasks list."""
        if self.challenge_id:
            await self.load_tasks(self.challenge_id)

    @on(Select.Changed, "#task-type-filter")
    def handle_type_filter_change(self, event: Select.Changed):
        """Handle task type filter change."""
        self.task_type_filter = event.value
        if self.challenge_id:
            self.refresh_tasks_async()

    @on(Select.Changed, "#task-sort")
    def handle_sort_change(self, event: Select.Changed):
        """Handle sort order change."""
        self.sort_by = event.value
        if self.challenge_id:
            self.refresh_tasks_async()

    def refresh_tasks_async(self):
        """Helper to refresh tasks asynchronously."""

        async def _refresh():
            await self.load_tasks(self.challenge_id)

        self.app.call_later(_refresh)


class ChallengeDetailPanel(ScrollableContainer):
    """Panel that displays challenge details with actions."""

    current_challenge = reactive(None)

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

    class LoadChallengeTasks(Message):
        """Message for loading challenge tasks."""

        def __init__(self, challenge_id: str) -> None:
            self.challenge_id = challenge_id
            super().__init__()

    def __init__(self, id=None, challenge_service=None):
        super().__init__(id=id)
        self.challenge_service = challenge_service

    def compose(self) -> ComposeResult:
        """Compose the challenge detail panel."""
        with Horizontal(id="challenge-detail-content"):
            yield ScrollableContainer(Markdown("", id="challenge-details"))

        with Horizontal(id="challenge-action-buttons", classes="action-row"):

            yield Button("Tasks", id="view-tasks-btn", variant="primary")
            yield Button("Join", id="join-challenge-btn", variant="success")

            with Horizontal(id="leave-challenge-container"):
                yield Button("Leave", id="leave-challenge-btn", variant="error")
                yield Select([("Keep", "keep-all"), ("Remove", "remove-all")], id="leave-option-select", value="keep-all")

    def watch_current_challenge(self, challenge: Challenge) -> None:
        """Watch for changes to the current_challenge property."""
        self._update_detail_view()

    def _update_detail_view(self) -> None:
        """Update the detail view with the current challenge data."""
        detail_content = self.query_one("#challenge-details")
        action_buttons = self.query_one("#challenge-action-buttons")

        if not self.current_challenge:
            detail_content.update("Select a challenge from the sidebar")
            action_buttons.add_class("hidden")
            return
        md_content = f"# {self.current_challenge.name}\n\n"
        # Format the challenge details with rich styling
        md_content += f"## Description\n\n {self.current_challenge.description}\n\n"
        md_content += f"**Owner:** {self.current_challenge.leader.name}\n"
        md_content += f" **Prize:** {self.current_challenge.prize}\n"
        md_content += f" **Members:** {self.current_challenge.member_count}"

        # Convert markdown to rich text
        detail_content.update(md_content)

        # Update action buttons based on joined status
        action_buttons.remove_class("hidden")
        join_btn = self.query_one("#join-challenge-btn")
        leave_container = self.query_one("#leave-challenge-container")

        if self.current_challenge.joined is False:
            join_btn.disabled = False
            leave_container.add_class("hidden")
        else:
            join_btn.disabled = True
            leave_container.remove_class("hidden")

    @on(Button.Pressed, "#join-challenge-btn")
    def handle_join_challenge(self):
        """Handle join challenge button press."""
        if self.current_challenge:
            self.post_message(self.JoinChallenge(self.current_challenge.id))

    @on(Button.Pressed, "#leave-challenge-btn")
    def handle_leave_challenge(self):
        """Handle leave challenge button press."""
        if self.current_challenge:
            keep_option = self.query_one("#leave-option-select").value
            self.post_message(self.LeaveChallenge(self.current_challenge.id, keep_option))

    @on(Button.Pressed, "#view-tasks-btn")
    def handle_view_tasks(self):
        """Handle view tasks button press."""
        if self.current_challenge:
            self.post_message(self.LoadChallengeTasks(self.current_challenge.id))


class ChallengeView(Container):
    """Main container that combines sidebar navigation and content panels."""

    current_challenge_id = reactive(None)
    loading = reactive(False)

    def __init__(self, id=None, challenge_service=None):
        super().__init__(id=id)
        self.challenge_service = challenge_service
        self.member_only = False
        self.current_page = 0
        self.total_pages = 1

    def compose(self) -> ComposeResult:
        """Compose the main challenge view."""
        with Horizontal(id="challenge-layout"):
            # Sidebar with tree navigation
            with Vertical(id="sidebar-container"):
                with Horizontal(id="sidebar-header"):
                    yield Static("Challenge Explorer", id="sidebar-title")
                #                    yield Button("↻", id="refresh-challenges-btn", variant="primary")

                yield ChallengeTree(id="challenge-tree")

            # Content panels
            with Vertical(id="content-container"):
                # Challenge details panel
                yield ChallengeDetailPanel(id="challenge-detail-panel", challenge_service=self.challenge_service)

                # Tasks panel (initially hidden)
                with Vertical(id="tasks-panel", classes="hidden"):
                    yield ChallengeTasksPanel(id="challenge-tasks-panel", challenge_service=self.challenge_service)

    async def on_mount(self) -> None:
        """Initialize the view on mount."""
        await self.load_challenges()

    async def load_challenges(self):
        """Load challenges from the service."""
        if not self.challenge_service:
            log.warning("No challenge service available")
            return

        if self.loading:
            return  # Prevent duplicate loads

        self.loading = True
        tree = self.query_one("#challenge-tree")

        try:
            # Fetch challenges using the service
            challenge_list = await self.challenge_service.fetch_challenges(member_only=self.member_only, page=self.current_page)

            # Extract and store pagination info
            self.total_pages = 50

            # Update the tree with challenges
            challenges = getattr(challenge_list, "challenges", [])
            tree.populate(challenges=challenges, member_only=self.member_only, current_page=self.current_page, total_pages=self.total_pages)

        except Exception as e:
            log.exception(f"Error loading challenges: {e}")
            # Show error in the tree
            tree.clear()
            tree.root.add("Error loading challenges")

        finally:
            self.loading = False

    @on(Tree.NodeSelected)
    async def handle_tree_node_selected(self, event: Tree.NodeSelected):
        """Handle tree node selection."""
        # Check for filter selection
        if event.node.data and "filter" in event.node.data:
            filter_type = event.node.data["filter"]

            # Switch the filter and reload
            if filter_type == "all" and self.member_only:
                self.member_only = False
                self.current_page = 0
                await self.load_challenges()
            elif filter_type == "member" and not self.member_only:
                self.member_only = True
                self.current_page = 0
                await self.load_challenges()

        # Check for pagination actions
        elif event.node.data and "action" in event.node.data:
            action = event.node.data["action"]

            if action == "prev_page" and self.current_page > 0:
                self.current_page -= 1
                await self.load_challenges()
            elif action == "next_page" and self.current_page < self.total_pages - 1:
                self.current_page += 1
                await self.load_challenges()

        # Check for challenge selection
        else:
            # Get the challenge from the tree
            tree = self.query_one("#challenge-tree")
            challenge = tree.get_challenge_from_node(event.node)

            if challenge:
                # Update the detail panel
                detail_panel = self.query_one("#challenge-detail-panel")
                detail_panel.current_challenge = challenge

                # Hide the tasks panel
                tasks_panel = self.query_one("#tasks-panel")
                tasks_panel.add_class("hidden")

    @on(Button.Pressed, "#refresh-challenges-btn")
    async def handle_refresh(self):
        """Handle refresh button press."""
        await self.load_challenges()

    @on(ChallengeDetailPanel.JoinChallenge)
    async def handle_join_challenge(self, event: ChallengeDetailPanel.JoinChallenge):
        """Handle join challenge message."""
        if not self.challenge_service:
            return

        try:
            # Call the service to join the challenge
            result = await self.challenge_service.join_challenge(event.challenge_id)

            if result:
                # Refresh the challenges to update the UI
                await self.load_challenges()

                # Update the detail panel - need to get the updated challenge
                challenge = await self.challenge_service.fetch_challenge(event.challenge_id)
                if challenge:
                    detail_panel = self.query_one("#challenge-detail-panel")
                    detail_panel.current_challenge = challenge

        except Exception as e:
            log.exception(f"Error joining challenge: {e}")

    @on(ChallengeDetailPanel.LeaveChallenge)
    async def handle_leave_challenge(self, event: ChallengeDetailPanel.LeaveChallenge):
        """Handle leave challenge message."""
        if not self.challenge_service:
            return

        try:
            # Call the service to leave the challenge
            result = await self.challenge_service.leave_challenge(event.challenge_id, keep=event.keep == "keep-all")

            if result:
                # Refresh the challenges to update the UI
                await self.load_challenges()

                # Update the detail panel
                challenge = await self.challenge_service.fetch_challenge(event.challenge_id)
                if challenge:
                    detail_panel = self.query_one("#challenge-detail-panel")
                    detail_panel.current_challenge = challenge

        except Exception as e:
            log.exception(f"Error leaving challenge: {e}")

    @on(ChallengeDetailPanel.LoadChallengeTasks)
    async def handle_load_tasks(self, event: ChallengeDetailPanel.LoadChallengeTasks):
        """Handle load tasks message."""
        tasks_panel = self.query_one("#tasks-panel")
        tasks_panel.remove_class("hidden")

        tasks_panel_widget = self.query_one("#challenge-tasks-panel")
        await tasks_panel_widget.load_tasks(event.challenge_id)


# Custom CSS for the widgets


# Example usage in a screen
class ChallengeScreen(Screen):
    """Example screen using the ChallengeView widget."""

    def __init__(self, challenge_service=None):
        super().__init__()
        self.challenge_service = challenge_service

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield ChallengeView(challenge_service=self.challenge_service)
