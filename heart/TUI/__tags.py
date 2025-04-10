from heart.basis.__get_data import get_tags
from heart.processors.process_tags import process_tags
from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Collapsible, DataTable, Label


class TagsWidget(VerticalScroll):
    """A widget to display tags in a scrollable table."""

    tags = reactive([])  # Reactive state to store tag data

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        yield DataTable(id="tags_table")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        table = self.query_one(DataTable)
        table.add_columns("Tag", "Category", "ID")  # Initialize columns
        self.fetch_tags()  # Fetch tags on startup (no await here)

    @work
    async def fetch_tags(self):
        """Fetch tags data asynchronously and update the table."""
        try:
            raw_tags = await get_tags()
            data = await process_tags(raw_tags)

            # Prepare rows
            fetched_tags = [
                (tag["name"], "challenge", tag["id"]) for tag in data["challenge_tags"]
            ] + [(tag["name"], "personal", tag["id"]) for tag in data["personal_tags"]]
            self.tags = fetched_tags  # Update reactive state

        except Exception as e:
            self.app.notify(
                f"Error fetching tags: {str(e)}", title="Error", severity="error"
            )

    def watch_tags(self, tags: list):
        """Called when the `tags` reactive property changes."""
        table = self.query_one(DataTable)
        table.clear()  # Clear existing rows
        table.add_rows(tags)  # Add new rows


class TagsApp(App):
    """The main application to display the TagsWidget."""

    def compose(self) -> ComposeResult:
        yield TagsWidget()


class TagsSection(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Collapsible(TagsWidget(), title="Tags", collapsed=True)

    def action_collapse_or_expand(self, collapse: bool) -> None:
        for child in self.walk_children(Collapsible):
            child.collapsed = collapse


if __name__ == "__main__":
    app = TagsApp()
    app.run()


from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, Select, Static


class TagManagerWidget(VerticalScroll):
    """Widget to manage tags with various operations."""

    tags = reactive([])  # Store all tags as reactive data
    tasks = reactive([])  # Store tasks and their associated tags

    def compose(self) -> ComposeResult:
        """Compose the layout."""
        yield Static("Tag Manager", id="title", classes="header")
        yield DataTable(id="tags_table")
        yield Horizontal(
            Button("Check/Create Special Tag", id="special_tag", variant="primary"),
            Button("Delete Selected Tags", id="delete_tag", variant="error"),
            Button("Find Unused Tags", id="unused_tag", variant="default"),
            Button("Replace Tag", id="replace_tag", variant="primary"),
            Button("Add Second Tag", id="add_second_tag", variant="primary"),
            Button("Set/Create Tags for Stats", id="set_tags", variant="primary"),
            Button("Edit Tag", id="edit_tag", variant="primary"),
            Button("Sort Tags", id="sort_tags", variant="primary"),
        )
        yield Vertical(
            Static("Tag Details"),
            Input(placeholder="Tag Name", id="tag_name"),
            Select(
                options=[
                    ("Challenge", "challenge"),
                    ("Personal", "personal"),
                    ("Stat-Based", "stats"),
                ],
                id="tag_category",
            ),
            Button("Save Changes", id="save_changes", variant="success"),
        )

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.load_tags()

    @work
    async def load_tags(self):
        """Load tags into the DataTable."""
        # Fetch data asynchronously (mocked here)
        await self.mock_fetch_tags()
        table = self.query_one(DataTable)
        table.clear()
        table.add_columns("Name", "Category", "ID")
        table.add_rows([(tag["name"], tag["category"], tag["id"]) for tag in self.tags])

    async def mock_fetch_tags(self):
        """Mock method to simulate fetching tags."""
        # Replace this with your actual fetching logic
        self.tags = [
            {"name": "Health", "category": "challenge", "id": "1"},
            {"name": "Work", "category": "personal", "id": "2"},
            {"name": "Strength", "category": "stats", "id": "3"},
        ]

    def action_special_tag(self):
        """Handle 'Check/Create Special Tag' action."""
        # Implement logic to check or create special tags
        pass

    def action_delete_tag(self):
        """Handle 'Delete Selected Tags' action."""
        # Implement logic to delete selected tags
        pass

    def action_unused_tag(self):
        """Handle 'Find Unused Tags' action."""
        # Implement logic to find and delete unused tags
        pass

    def action_replace_tag(self):
        """Handle 'Replace Tag' action."""
        # Implement logic to replace one tag with another
        pass

    def action_add_second_tag(self):
        """Handle 'Add Second Tag' action."""
        # Implement logic to add a second tag to tasks with a specific tag
        pass

    def action_set_tags(self):
        """Handle 'Set/Create Tags for Stats' action."""
        # Implement logic to set or create tags for stats
        pass

    def action_edit_tag(self):
        """Handle 'Edit Tag Text' action."""
        # Implement logic to edit the text of a tag
        pass

    def action_sort_tags(self):
        """Handle 'Sort Tags Order' action."""
        self.tags.sort(key=lambda x: x["name"].lower())
        self.load_tags()


class TagManagerApp(App):
    """Main application to display the TagManagerWidget."""

    def compose(self) -> ComposeResult:
        yield TagManagerWidget()


if __name__ == "__main__":
    app = TagManagerApp()
    app.run()


from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Select

LINES = """I must not fear.
Fear is the mind-killer.
Fear is the little-death that brings total obliteration.
I will face my fear.
I will permit it to pass over me and through me.""".splitlines()


class SelectApp(Vertical):
    DEFAULT_CSS = """
    Screen {
    align: center top;
}

Select {
    width: 60;
    margin: 2;
}
"""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Select((line, line) for line in LINES)

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        self.title = str(event.value)


if __name__ == "__main__":
    app = SelectApp()
    app.run()
