from dataclasses import dataclass
from typing import List

from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
    TextLog,
)


# ---- Models ----
@dataclass
class Task:
    id: str
    text: str
    description: str
    tags: list[str]
    priority: str
    due_date: str
    value: float
    status: str
    streak: int
    challenge: str
    attribute: str
    checklist: list[str]


@dataclass
class Tag:
    id: str
    name: str
    subtags: list[str] = None


@dataclass
class Challenge:
    id: str
    name: str
    summary: str
    description: str
    tasks: list[Task]


@dataclass
class MessageEntry:
    sender: str
    content: str


@dataclass
class Party:
    name: str
    members: list[str]
    chat: list[MessageEntry]


# ---- Messages ----
class TaskSelected(Message):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__()


class TagUpdated(Message):
    def __init__(self, tag_id: str) -> None:
        self.tag_id = tag_id
        super().__init__()


# ---- Widgets ----
class TaskListWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Input(
                placeholder="Filter by name or description", id="task-filter"
            ),
            Select(
                options=[
                    ("Low", "low"),
                    ("Medium", "medium"),
                    ("High", "high"),
                ],
                prompt="Priority",
            ),
            Select(
                options=[
                    ("All", "all"),
                    ("Habits", "habit"),
                    ("Dailies", "daily"),
                    ("To-Dos", "todo"),
                    ("Rewards", "reward"),
                ],
                prompt="Type",
            ),
        )
        yield DataTable(id="task-table")

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns(
            "Name", "Priority", "Due", "Tags", "Streak", "Challenge", "Attr"
        )
        self.tasks = []  # Would be fetched from API
        self.refresh_table()

    def refresh_table(self):
        table = self.query_one("#task-table", DataTable)
        table.clear()
        for task in self.tasks:
            table.add_row(
                task.text,
                task.priority,
                task.due_date,
                ", ".join(task.tags),
                str(task.streak),
                task.challenge,
                task.attribute,
            )


class TagManagerWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Tag Manager")
        yield DataTable(id="tag-table")
        yield Button("Add Tag"), Button("Edit"), Button("Delete")

    def on_mount(self) -> None:
        self.tags = []  # Would be fetched from API or local
        self.refresh_tags()

    def refresh_tags(self):
        table = self.query_one("#tag-table", DataTable)
        table.clear()
        table.add_columns("Tag", "Subtags")
        for tag in self.tags:
            subtags = ", ".join(tag.subtags) if tag.subtags else ""
            table.add_row(tag.name, subtags)


class ChallengeView(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Your Challenges")
        yield DataTable(id="challenge-table")
        yield Button("View"), Button("Clone"), Button("Edit"), Button(
            "Delete"
        ), Button("New Challenge")


class MessagesWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Private Messages")
        yield DataTable(id="messages-table")
        yield Input(placeholder="Send message to..."), Input(
            placeholder="Type message..."
        ), Button("Send")


class PartyWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Party Status")
        yield Static("Members and Spells")
        yield DataTable(id="party-members")
        yield Static("Chat")
        yield TextLog(id="party-chat"), Input(
            placeholder="Send chat..."
        ), Button("Send Chat"), Button("Cast Spell")


class SettingsWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Settings")
        yield Input(placeholder="Start Custom Day Time"), Button("Save")
        yield Input(placeholder="API Token"), Input(
            placeholder="User ID"
        ), Button("Save Credentials")
        yield Button("Force Cron")


# ---- Main App ----
class HabiticaTUI(App):
    CSS_PATH = "style.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(id="main-grid")
        yield Footer()

    def on_mount(self) -> None:
        grid = self.query_one("#main-grid", Grid)
        grid.add_class("main-layout")
        grid.place(
            sidebar=Vertical(Static("Sidebar")),
            main=TabbedContent(
                Tabs(
                    "Tasks",
                    "Tags",
                    "Challenges",
                    "Messages",
                    "Party",
                    "Settings",
                ),
                TabPane(TaskListWidget(), id="tasks"),
                TabPane(TagManagerWidget(), id="tags"),
                TabPane(ChallengeView(), id="challenges"),
                TabPane(MessagesWidget(), id="messages"),
                TabPane(PartyWidget(), id="party"),
                TabPane(SettingsWidget(), id="settings"),
                id="main-tabs",
            ),
        )


if __name__ == "__main__":
    HabiticaTUI().run()
