def on_data_table_row_selected(self, event: DataTable.RowSelected):
    task_id = event.row_key
    task = self.find_task_by_id(task_id)
    self.app.push_screen(EditTaskModal(task))

async def on_edit_task_modal_submit(self, event: EditTaskModal.Submit):
    task_id = event.task_id
    values = event.values
    response = await client.put(f"/tasks/{task_id}", json=values)
    response.raise_for_status()
    updated = response.json()["data"]
    task = self.find_task_by_id(task_id)

    # Update local task
    task.text = updated["text"]
    task.description = updated["notes"]
    task.tags = updated.get("tags", [])
    task.due_date = updated.get("date", "")
    task.priority = str(updated["priority"])
    task.attribute = updated.get("attribute", "")
    self.update_task_row(task)

