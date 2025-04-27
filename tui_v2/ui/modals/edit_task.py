from textual.screen import ModalScreen
from textual.widgets import Input, Select, Button, Static
from textual.containers import Vertical, Horizontal
from textual.message import Message

class EditTaskModal(ModalScreen):
    class Submit(Message):
        def __init__(self, sender, task_id: str, values: dict):
            self.task_id = task_id
            self.values = values
            super().__init__(sender)

    def __init__(self, task: Task):
        super().__init__()
        self.task = task

    def compose(self):
        yield Vertical(
            Static(f"Editing: {self.task.text}", id="modal-title"),
            Input(value=self.task.text, placeholder="Task Name", id="name"),
            Input(value=self.task.description, placeholder="Description", id="desc"),
            Input(value=", ".join(self.task.tags), placeholder="Tags (comma-separated)", id="tags"),
            Input(value=self.task.due_date or "", placeholder="Due Date (YYYY-MM-DD)", id="due"),
            Select([("Low", "0.1"), ("Medium", "1"), ("High", "1.5"), ("Critical", "2")],
                   value=str(self.task.priority), id="priority"),
            Select([("None", ""), ("Str", "str"), ("Int", "int"), ("Con", "con"), ("Per", "per")],
                   value=self.task.attribute, id="attr"),
            Horizontal(
                Button("Save", id="save"),
                Button("Cancel", id="cancel"),
                id="modal-actions"
            )
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            values = {
                "text": self.query_one("#name", Input).value,
                "notes": self.query_one("#desc", Input).value,
                "tags": [tag.strip() for tag in self.query_one("#tags", Input).value.split(",") if tag.strip()],
                "date": self.query_one("#due", Input).value or None,
                "priority": float(self.query_one("#priority", Select).value),
                "attribute": self.query_one("#attr", Select).value,
            }
            self.dismiss()
            self.post_message(self.Submit(self, self.task.id, values))
        else:
            self.dismiss()

