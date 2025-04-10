from typing import Any, Dict, List

import emoji_data_python
from basis import api_method as habitica_api
from heart.__common import __convert_date
from heart.__common.__save_file import save_file
from processors.process_tags import process_tags
from TUI import color_utils as value_color


def process_task_tags(
    task: Dict[str, Any], tags: Dict[str, List[Dict[str, str]]]
) -> List[str]:
    """
    Process tags for a task.

    Args:
        task (dict): The task data from the Habitica API.
        tags (dict): Processed tags data.

    Returns:
        list: List of tag names associated with the task.
    """
    tag_names = [
        tag["name"]
        for task_tag in task.get("tags", [])
        for category in tags
        for tag in tags[category]
        if task_tag == tag["id"]
    ]
    return tag_names


def process_task_type_specific(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process specific attributes of a task based on its type.

    Args:
        task (dict): The task data from the Habitica API.

    Returns:
        dict: Processed data for the specific task type.
    """
    task_type = task["type"]
    if task_type == "habit":
        return process_habit(task)
    elif task_type == "todo":
        return process_todo(task)
    elif task_type == "daily":
        return process_daily(task)
    elif task_type == "reward":
        return process_reward(task)
    return {}


def process_habit(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process data specific to habit tasks.

    Args:
        task (dict): The habit task data.

    Returns:
        dict: Processed habit task data.
    """
    if task["up"] and task["down"]:
        direction = "both"
        count = f'⧾{task["counterUp"]}, -{task["counterDown"]}'
    elif task["up"]:
        direction = "up"
        count = f'⧾{task["counterUp"]}'
    elif task["down"]:
        direction = "down"
        count = f'-{task["counterDown"]}'
    else:
        direction = "none"
        count = f'⧾{task["counterUp"]}, -{task["counterDown"]}'  # Handles case where up and down are false.

    return {
        "counter": count,
        "direction": direction,
        "frequency": task.get("frequency", ""),
        "value_color": value_color.value_color(task["value"]),
        "value": task["value"],
    }


def process_todo(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process data specific to todo tasks.

    Args:
        task (dict): The todo task data.

    Returns:
        dict: Processed todo task data.
    """
    is_due = "date" in task and task["date"] is not None
    deadline = task["date"] if is_due else ""
    status = (
        "red"
        if is_due and __convert_date.is_date_passed(task["date"])
        else "due" if is_due else "grey"
    )
    return {
        "_status": status,
        "checklist": task.get("checklist", []),
        "date": deadline,
        "is_due": is_due,
        "value_color": value_color.value_color(task["value"]),
        "value": task["value"],
    }


def process_daily(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process data specific to daily tasks.

    Args:
        task (dict): The daily task data.

    Returns:
        dict: Processed daily task data.
    """
    status = (
        "done"
        if task["isDue"] and task["completed"]
        else "due" if task["isDue"] else "grey"
    )

    return {
        "_status": status,
        "checklist": task.get("checklist", []),
        "date": task["nextDue"][0] if task.get("nextDue") else "",
        "is_due": task.get("isDue", False),
        "streak": task.get("streak", 0),
        "value_color": value_color.value_color(task["value"]),
        "value": task["value"],
    }


def process_reward(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process data specific to reward tasks.

    Args:
        task (dict): The reward task data.

    Returns:
        dict: Processed reward task data.
    """
    return {"value": task["value"]}


def process_task(
    task: Dict[str, Any], tags: Dict[str, List[Dict[str, str]]]
) -> Dict[str, Any]:
    """
    Process a task and return a dictionary with its processed data.

    Args:
        task (dict): The task data from the Habitica API.
        tags (dict): Processed tags data.

    Returns:
        dict: Processed task data.
    """
    base_task = {
        "_type": task["type"],
        "attribute": task.get("attribute", ""),
        "challenge_id": task["challenge"]["id"] if task.get("challenge") else "",
        "challenge": (
            emoji_data_python.replace_colons(task["challenge"]["shortName"])
            if task.get("challenge")
            else ""
        ),
        "id": task["id"],
        "note": emoji_data_python.replace_colons(task.get("notes", "")),
        "priority": task.get("priority", 1),
        "tag_id": task.get("tags", []),
        "tag_name": process_task_tags(task, tags),
        "text": emoji_data_python.replace_colons(task.get("text", "")),
        "created": task.get("createdAt", ""),
    }
    specific_data = process_task_type_specific(task)
    base_task.update(specific_data)
    return base_task


def process_tasks(
    tags_data: Dict[str, List[Dict[str, str]]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Process all tasks from the Habitica API and save the processed data.

    Args:
        tags (dict): Processed tags data.

    Returns:
        dict: Processed tasks data organized by categories.
    """
    try:
        # Fetch tags if not provided
        tags = tags_data if tags_data else process_tags()

        if not tags:
            raise ValueError("No tags data found.")

        all_tasks = habitica_api.get("tasks/user")["data"]
        tasks_dict = {}
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

        for task in all_tasks:
            processed_task = process_task(task, tags)
            tasks_dict[processed_task["id"]] = processed_task

            if task.get("challenge", {}).get("broken"):
                cats_dict["broken"].append(task["id"])

            if task["challenge"]:
                cats_dict["challenge"].append(task["challenge"]["id"])

            task_type = task["type"] + "s"
            if task_type in ["todos", "dailys"]:
                status = processed_task["_status"]
                cats_dict["tasks"][task_type][status].append(task["id"])
            else:
                cats_dict["tasks"][task_type].append(task["id"])

        cats_dict["tags"] = list(
            set(tag for task in all_tasks for tag in task.get("tags", []))
        )

        return {"data": tasks_dict, "cats": cats_dict}

    except Exception as e:
        print(f"Error in process_tags: {e}")
        return {"challenge_tags": [], "personal_tags": []}
