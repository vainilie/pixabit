from core import habitica_api
from get import get_rawtasks
from rich.progress import track
from pixabit.utils.display import Confirm, print

import time
import six


def sortFunction_alpha(value):
    return value[
        "title"
    ].lower()  # Use 'title' because we create that key in each task item.


def sortFunction(value):
    return value["title"].lower()


def sort_alpha(dictionary):
    tasks = []

    # Iterate over the dictionary and extract required data
    for key, value in dictionary.items():
        item = {
            "id": key,  # Use 'value' to access task properties
            "title": value["text"],
            "ch": value["challenge"],
        }
        tasks.append(item)

    # Sort tasks alphabetically by title
    sortedtasks = sorted(tasks, key=sortFunction_alpha)

    print(
        f"""Total tasks to be sorted: {len(sortedtasks)}.
        
        Estimated time to fix the tags (seconds): {round(len(sortedtasks)/ 30, 2)}"""
    )
    # Confirm before proceeding with API calls
    if Confirm.ask("Continue?", default=False):
        for task in track(sortedtasks, description="Sorting tasks..."):
            habitica_api.post(f"tasks/{task['id']}/move/to/-1")
        print("[b]Your tasks are now alphabetically sorted :cherry_blossom:")
    else:
        print("[b]OK, no changes done :cherry_blossom:")


def sort_todo_duedates(dictionary):
    tasks = []

    # Iterate over the dictionary and extract required data
    for key, value in dictionary.items():
        if value["_type"] == "todo":
            item = {
                "id": key,  # Use 'value' to access task properties
                "title": value["text"],
                "ch": value["challenge"],
                "date": value["date"],
                "createdAt": value["created"],
            }
            tasks.append(item)

    # Sort tasks alphabetically by title
    sortedtasks = tasks.sort(
        key=lambda k: (k["date"][:10], k["createdAt"]), reverse=True
    )

    print(
        f"""Total tasks to be sorted: {len(sortedtasks)}.
        
        Estimated time to fix the tags (seconds): {round(len(sortedtasks)/ 30, 2)}"""
    )
    # Confirm before proceeding with API calls
    if Confirm.ask("Continue?", default=False):
        for task in track(sortedtasks, description="Sorting tasks..."):
            habitica_api.post(f"tasks/{task['id']}/move/to/0")
        print("[b]Your tasks are now sorted by duedate :cherry_blossom:")
    else:
        print("[b]OK, no changes done :cherry_blossom:")
    # Push todos_with_duedates to the top
