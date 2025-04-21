def on_input_changed(self, event: Input.Changed) -> None:
    filter_text = event.value.strip().lower()
    filtered = [
        task for task in self.tasks
        if filter_text in task.text.lower() or filter_text in task.description.lower()
    ]
    self.table.clear()
    for task in filtered:
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

