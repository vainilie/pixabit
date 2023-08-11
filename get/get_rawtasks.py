from core import habitica_api, save_file


def get_rawtasks():
    tasks = habitica_api.get("tasks/user")["data"]
    save_file.save_file(tasks, "raw_tasks", "_json")
    return tasks
