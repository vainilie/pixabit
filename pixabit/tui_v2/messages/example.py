# What is the MessagePump?
# In Textual, it’s how widgets communicate without tight coupling.

# Example:

from textual.message import Message
from textual.widget import Widget


class TaskSelected(Message):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__()


class TaskListWidget(Widget):
    def on_task_click(self, task_id: str) -> None:
        self.post_message(TaskSelected(task_id))


# in the widget
def on_task_selected(self, message: TaskSelected) -> None:
    self.query_one(TaskDetailWidget).load_task(message.task_id)
