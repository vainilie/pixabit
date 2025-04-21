def update_task_row(self, updated_task: Task):
    if self.table.has_row(updated_task.id):
        self.table.update_row(
            updated_task.id,
            updated_task.text,
            updated_task.priority,
            updated_task.due_date,
            ", ".join(updated_task.tags),
            str(updated_task.streak),
            updated_task.challenge,
            updated_task.attribute,
        )

