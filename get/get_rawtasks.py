from core import habitica_api, save_file
import emoji_data_python


def get_rawtasks():
    tasks = habitica_api.get("tasks/user")["data"]
    for task in tasks:
        emoji_data_python.replace_colons(task["text"])

    sorted_tasks = sorted(tasks, key=lambda x: x["text"].lower())
    save_file.save_file(sorted_tasks, "raw_tasks", "_json")
    return tasks
