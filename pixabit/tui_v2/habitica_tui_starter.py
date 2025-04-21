from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, Horizontal
from textual.widgets import (
    Header, Footer, Static, Input, Select, DataTable, Tabs, TabPane, TabbedContent, TextLog, Button
)
from textual.message import Message
from textual.widget import Widget
from dataclasses import dataclass
from typing import List

# ---- Models ----
@dataclass
class Task:
    id: str
    text: str
    description: str
    tags: List[str]
    priority: str
    due_date: str
    value: float
    status: str
    streak: int
    challenge: str
    attribute: str
    checklist: List[str]

@dataclass
class Tag:
    id: str
    name: str
    subtags: List[str] = None

@dataclass
class Challenge:
    id: str
    name: str
    summary: str
    description: str
    tasks: List[Task]

@dataclass
class MessageEntry:
    sender: str
    content: str

@dataclass
class Party:
    name: str
    members: List[str]
    chat: List[MessageEntry]

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
            Input(placeholder="Filter by name or description", id="task-filter"),
            Select(options=[("Low", "low"), ("Medium", "medium"), ("High", "high")], prompt="Priority"),
            Select(options=[("All", "all"), ("Habits", "habit"), ("Dailies", "daily"), ("To-Dos", "todo"), ("Rewards", "reward")], prompt="Type")
        )
        yield DataTable(id="task-table")

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns("Name", "Priority", "Due", "Tags", "Streak", "Challenge", "Attr")
        self.tasks = []  # Would be fetched from API
        self.refresh_table()

    def refresh_table(self):
        table = self.query_one("#task-table", DataTable)
        table.clear()
        for task in self.tasks:
            table.add_row(
                task.text, task.priority, task.due_date,
                ", ".join(task.tags), str(task.streak), task.challenge, task.attribute
            )

            from habitica_api import fetch_user_tasks
from textual import work

class TaskListWidget(Widget):
    def on_mount(self) -> None:
        self.tasks: list[Task] = []
        self.table = self.query_one("#task-table", DataTable)
        self.table.add_columns("Name", "Priority", "Due", "Tags", "Streak", "Challenge", "Attr")
        self.load_tasks()

    @work(exclusive=True)
    async def load_tasks(self):
        raw_tasks = await fetch_user_tasks()
        self.tasks = [
            Task(
                id=task["_id"],
                text=task.get("text", ""),
                description=task.get("notes", ""),
                tags=task.get("tags", []),
                priority=str(task.get("priority", "")),
                due_date=task.get("date", "") or "",
                value=task.get("value", 0.0),
                status=task.get("completed", False),
                streak=task.get("streak", 0),
                challenge=task.get("challenge", {}).get("id", ""),
                attribute=task.get("attribute", ""),
                checklist=[item["text"] for item in task.get("checklist", [])],
            )
            for task in raw_tasks
        ]
        self.refresh_table()

    def refresh_table(self):
        self.table.clear()
        for task in self.tasks:
            self.table.add_row(
                task.text,
                task.priority,
                task.due_date,
                ", ".join(task.tags),
                str(task.streak),
                task.challenge,
                task.attribute,
                key=task.id,
            )
    async def toggle_task_done(self, task_id: str, completed: bool):
        response = await client.put(f"/tasks/{task_id}", json={"completed": completed})
        response.raise_for_status()
        updated = response.json()["data"]
        task = self.find_task_by_id(task_id)
        task.status = updated["completed"]
        self.update_task_row(task)
    async def delete_task(self, task_id: str):
        response = await client.delete(f"/tasks/{task_id}")
        response.raise_for_status()
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.table.remove_row(task_id)
    async def edit_task_text(self, task_id: str, new_text: str):
        response = await client.put(f"/tasks/{task_id}", json={"text": new_text})
        response.raise_for_status()
        task = self.find_task_by_id(task_id)
        task.text = new_text
        self.update_task_row(task)


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
        yield Button("View"), Button("Clone"), Button("Edit"), Button("Delete"), Button("New Challenge")

class MessagesWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Private Messages")
        yield DataTable(id="messages-table")
        yield Input(placeholder="Send message to..."), Input(placeholder="Type message..."), Button("Send")

class PartyWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Party Status")
        yield Static("Members and Spells")
        yield DataTable(id="party-members")
        yield Static("Chat")
        yield TextLog(id="party-chat"), Input(placeholder="Send chat..."), Button("Send Chat"), Button("Cast Spell")

class SettingsWidget(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Settings")
        yield Input(placeholder="Start Custom Day Time"), Button("Save")
        yield Input(placeholder="API Token"), Input(placeholder="User ID"), Button("Save Credentials")
        yield Button("Force Cron")

# ---- Main App ----
class HabiticaTUI(App):
    CSS_PATH = "style.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(id="main-grid")
        yield Input(id="task-filter", placeholder="Filter tasks by name or description")
        yield Footer()

    def on_mount(self) -> None:
        grid = self.query_one("#main-grid", Grid)
        grid.add_class("main-layout")
        grid.place(
            sidebar=Vertical(Static("Sidebar")),
            main=TabbedContent(
                Tabs("Tasks", "Tags", "Challenges", "Messages", "Party", "Settings"),
                TabPane(TaskListWidget(), id="tasks"),
                TabPane(TagManagerWidget(), id="tags"),
                TabPane(ChallengeView(), id="challenges"),
                TabPane(MessagesWidget(), id="messages"),
                TabPane(PartyWidget(), id="party"),
                TabPane(SettingsWidget(), id="settings"),
                id="main-tabs"
            )
        )

if __name__ == "__main__":
    HabiticaTUI().run()

