class NewTaskModal(EditTaskModal):
    class Create(Message):
        def __init__(self, sender, values: dict):
            self.values = values
            super().__init__(sender)

    def __init__(self):
        super().__init__(Task(id="", text="", description="", tags=[], priority="1", due_date="", value=0.0, status=False, streak=0, challenge="", attribute="", checklist=[]))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            values = {
                "text": self.query_one("#name", Input).value,
                "notes": self.query_one("#desc", Input).value,
                "tags": [tag.strip() for tag in self.query_one("#tags", Input).value.split(",") if tag.strip()],
                "date": self.query_one("#due", Input).value or None,
                "priority": float(self.query_one("#priority", Select).value),
                "attribute": self.query_one("#attr", Select).value,
                "type": "todo",  # Or habit/daily/reward depending on context
            }
            self.dismiss()
            self.post_message(self.Create(self, values))
        else:
            self.dismiss()

