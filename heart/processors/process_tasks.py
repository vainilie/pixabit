#             _     _            _
#            | |   | |          | |
#   __ _  ___| |_  | |_ __ _ ___| | _____
#  / _` |/ _ \ __| | __/ _` / __| |/ / __|
# | (_| |  __/ |_  | || (_| \__ \   <\__ \
#  \__, |\___|\__|  \__\__,_|___/_|\_\___/
#   __/ |
#  |___/


"""
get_tasks Module
================

Module for processing Habitica tasks data and saving the processed data.

This module interacts with the Habitica API to retrieve tasks data, processes the
data for different types of tasks, counts the number of tasks in each category, and
saves the processed data to files. It contains functions to process habit, todo, daily,
and reward tasks, and to generate dictionaries containing the processed task data.

Functions:
    process_task_tags(task, tags):
        Process tags for a task and return a list of tag names associated with the task.

    all_types(task, tags):
        Process different types of tasks and return a dict with the processed data.

    is_habit(task):
        Process a habit task and return a dictionary with the processed data.

    is_todo(task):
        Process a todo task and return a dictionary with the processed data.

    is_daily(task):
        Process a daily task and return a dictionary with the processed data.

    is_reward(task):
        Process a reward task and return a dictionary with the processed data.

    process_task(task, tags):
        Process a task and return a dictionary with the processed data.

    process_tasks(tags):
        Process all tasks data, count the number of tasks in each category,
        and save it to files.

Note:
    This module depends on the `basis.api_method` module to interact with the
    Habitica API, the `common.convert_date` module to handle date conversions,
    the `common.value_color` module to determine the value color for tasks, and
    the `emoji_data_python` module to replace emoji codes with their Unicode
    representations. The `basis.save_file` module is also used to save the
    processed data to files.
"""


from typing import Dict, List

import emoji_data_python
from basis import api_method
from heart.__common import __convert_date
from heart.__common import __save_file as save_file
from heart.basis import __get_data as get
from processors.process_tags import process_tags
from TUI import color_utils


def process_task_tags(
    task: Dict[str, any], tags: Dict[str, List[Dict[str, str]]]
) -> List[str]:
    """
    Process tags for a task.

    Args:
        task (dict): The task data received from the Habitica API.
        tags (dict): The dictionary containing processed tags data.

    Returns:
        list: A list of tag names associated with the task.
    """
    tag_names = []
    for task_tag in task["tags"]:
        for category in tags:
            for tag in tags[category]:
                if task_tag == tag["id"]:
                    tag_names.append(tag["name"])
    return tag_names


def all_types(
    task: Dict[str, any], tags: Dict[str, List[Dict[str, str]]]
) -> Dict[str, any]:
    """
    Process different types of tasks and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.
        tags (dict): The dictionary containing processed tags data.

    Returns:
        dict: A dictionary containing the processed task data with different types.
    """
    processed_task = {
        "_type": task["type"],
        "attribute": task["attribute"],
        "challenge_id": task["challenge"]["id"] if task["challenge"] else "",
        "challenge": (
            emoji_data_python.replace_colons(task["challenge"]["shortName"])
            if task["challenge"]
            else ""
        ),
        "id": task["id"],
        "note": emoji_data_python.replace_colons(task["notes"]),
        "priority": task["priority"],
        "tag_id": task["tags"],
        "tag_name": process_task_tags(task, tags),
        "text": emoji_data_python.replace_colons(task["text"]),
        "created": task["createdAt"],
    }
    return processed_task


def is_habit(task: Dict[str, any]) -> Dict[str, any]:
    """
    Process a habit task and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.

    Returns:
        dict: A dictionary containing the processed data for a habit task.
    """
    if task["up"] and task["down"]:
        direction = "both"
        count = f'⧾{task["counterUp"]}, -{task["counterDown"]}'
    elif not task["up"] and not task["down"]:
        direction = "none"
        count = f'⧾{task["counterUp"]}, -{task["counterDown"]}'
    elif task["up"] and not task["down"]:
        direction = "up"
        count = f'⧾{task["counterUp"]}'
    else:
        direction = "down"
        count = f'-{task["counterDown"]}'

    return {
        "counter": count,
        "direction": direction,
        "frequency": task["frequency"],
        "value_color": color_utils.value_color(task["value"]),
        "value": task["value"],
    }


def is_todo(task: Dict[str, any]) -> Dict[str, any]:
    """
    Process a todo task and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.

    Returns:
        dict: A dictionary containing the processed data for a todo task.
    """
    if "date" in task and task["date"] is not None:
        is_due = True
        deadline = task["date"]
        status = "red" if __convert_date.is_date_passed(task["date"]) else "due"
    else:
        is_due = False
        status = "grey"
        deadline = ""
    return {
        "_status": status,
        "checklist": task["checklist"],
        "date": deadline,
        "is_due": is_due,
        "value_color": color_utils.value_color(task["value"]),
        "value": task["value"],
    }


def is_daily(task: Dict[str, any]) -> Dict[str, any]:
    """
    Process a daily task and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.

    Returns:
        dict: A dictionary containing the processed data for a daily task.
    """
    if task["isDue"] is False:
        status = "grey"
    else:
        status = "done" if task["completed"] else "due"

    return {
        "_status": status,
        "checklist": task["checklist"],
        "date": task["nextDue"][0] if len(task["nextDue"]) > 0 else "",
        "is_due": task["isDue"],
        "streak": task["streak"],
        "value_color": color_utils.value_color(task["value"]),
        "value": task["value"],
    }


def is_reward(task: Dict[str, any]) -> Dict[str, any]:
    """
    Process a reward task and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.

    Returns:
        dict: A dictionary containing the processed data for a reward task.
    """
    return {"value": task["value"]}


def process_task(
    task: Dict[str, any], tags: Dict[str, List[Dict[str, str]]]
) -> Dict[str, any]:
    """
    Process a task and return a dictionary with the processed data.

    Args:
        task (dict): The task data received from the Habitica API.
        tags (dict): The dictionary containing processed tags data.

    Returns:
        dict: A dictionary containing the processed data for the task.
    """
    p_task = dict(all_types(task, tags))
    if task["type"] == "reward":
        p_task.update(is_reward(task))
    elif task["type"] == "habit":
        p_task.update(is_habit(task))
    elif task["type"] == "daily":
        p_task.update(is_daily(task))
    elif task["type"] == "todo":
        p_task.update(is_todo(task))
    return p_task


def process_tasks(
    tasks_data=None, tags_data: Dict[str, List[Dict[str, str]]] = None
) -> Dict[str, Dict[str, any]]:
    """
    Process all tasks data and save it to files.

    Args:
        tags (dict): The dictionary containing processed tags data.

    Returns:
        dict: A dictionary containing the processed tasks data and categories.
    """

    tags = tags_data if tags_data else process_tags()
    tasks = tasks_data if tasks_data else get.tasks()
    if not tags:
        raise ValueError("No tags data found.")

    used_tags = set()
    broken_challenges = list()
    joined_ch = list()
    cats_dict = {
        "tasks": {
            "habits": [],
            "todos": {"due": [], "grey": [], "red": []},
            "dailys": {"done": [], "due": [], "grey": []},
            "rewards": [],
        },
        "tags": [],
        "broken": [],
        "challenge": [],
    }
    tasks_dict = {
        #     "habits": [],
        #     "todos": {"due": [], "grey": [], "red": []},
        #     "dailys": {"done": [], "due": [], "grey": []},
        #     "rewards": [],
    }
    for idx, task in enumerate(tasks):
        processed_task = process_task(task, tags)
        tasks_dict.update({processed_task["id"]: processed_task})
        used_tags.update(task["tags"])
        if "broken" in task["challenge"]:
            broken_challenges.append(task["id"])
        if len(task["challenge"]) > 0:
            joined_ch.append(task["challenge"].get("id"))

        if task["type"] == "todo" or task["type"] == "daily":
            status = processed_task["_status"]
            type_task = task["type"] + "s"
            cats_dict["tasks"][type_task][status].append(task["id"])
            # tasks_dict[task["type"] + "s"][processed_task["_status"]].append(
            #     processed_task["id"]
            # )
        else:
            # tasks_dict[task["type"] + "s"].append(processed_task["id"])
            cats_dict["tasks"][task["type"] + "s"].append(task["id"])

    cats_dict["tags"] = list(used_tags)
    cats_dict["broken"] = list(broken_challenges)
    cats_dict["challenge"] = list(joined_ch)

    return {"data": tasks_dict, "cats": cats_dict}
