from core import habitica_api, save_file
import emoji_data_python


def get_rawtasks():
    """
    Get and save raw tasks data from the user's Habitica account.

    This function retrieves the raw tasks data from the user's Habitica account and
    applies the `emoji_data_python.replace_colons` function to the text of each task.
    It then sorts the tasks based on their text in a case-insensitive manner and
    saves the sorted tasks data to a JSON file named "raw_tasks.json" using the
    save_file module.

    Returns:
        list: A list containing dictionaries representing user's raw tasks.

    Example:
        raw_tasks = get_rawtasks()
        print(raw_tasks)
    """
    tasks = habitica_api.get("tasks/user")["data"]

    for task in tasks:
        task["text"] = emoji_data_python.replace_colons(task["text"])

    sorted_tasks = sorted(tasks, key=lambda x: x["text"].lower())
    save_file.save_file(sorted_tasks, "raw_tasks", "_json")
    return sorted_tasks
