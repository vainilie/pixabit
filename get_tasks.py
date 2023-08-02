import habitica_api
import emoji_data_python
import values
import save_file
import convert_date


def process_task_tags(task, tags):
    """
    Process tags associated with a task.

    Args:
        task (dict): The task data obtained from the Habitica API.
        tags (dict): Dictionary containing tag information.

    Returns:
        list: List of tag names associated with the task.
    """
    tag_names = []
    for task_tag in task["tags"]:
        for category in tags:
            for tag in tags[category]:
                if task_tag == tag["id"]:
                    tag_names.append(tag["name"])
    return tag_names


def process_task(task, tags):
    """
    Process a single task obtained from the Habitica API.

    Args:
        task (dict): The task data obtained from the Habitica API.
        tags (dict): Dictionary containing tag information.

    Returns:
        dict: Processed task data with relevant details.
    """

    processed_task = {
        "attribute": task["attribute"],
        "challenge": emoji_data_python.replace_colons(task["challenge"]["shortName"])
        if len(task["challenge"]) > 0
        else "",
        "challenge_id": (task["challenge"]["id"]) if len(task["challenge"]) > 0 else "",
        "id": task["id"],
        "notes": emoji_data_python.replace_colons(task["notes"]),
        "priority": task["priority"],
        "tags_id": task["tags"],
        "tags_names": process_task_tags(task, tags),
        "text": emoji_data_python.replace_colons(task["text"]),
        "type": task["type"],
    }

    if task["type"] == "reward":
        processed_task["value"] = task["value"]

    elif task["type"] == "habit":
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

        processed_task.update(
            {
                "color": values.value_color(task["value"]),
                "counter": count,
                "direction": direction,
                "frequency": task["frequency"],
                "value": task["value"],
            }
        )
    else:
        processed_task.update(
            {
                "checklist": len(task["checklist"]),
                "color": values.value_color(task["value"]),
                "completed": task["completed"],
                "value": task["value"],
            }
        )

        if task["type"] == "daily":
            processed_task.update(
                {
                    "is_due": task["isDue"],
                    "next": task["nextDue"][0],
                    "status": "grey"
                    if not task["isDue"]
                    else "done"
                    if task["completed"]
                    else "due",
                    "streak": task["streak"],
                }
            )
        else:
            if "date" in task:
                deadline = task["date"] if task["date"] is not None else ""
                is_due = bool(task["date"])
            else:
                deadline = ""
                is_due = False
            processed_task.update({"is_due": is_due, "next": deadline})

            if is_due:
                processed_task["status"] = (
                    "red" if convert_date.is_date_passed(task["date"]) else "due"
                )
            else:
                processed_task["status"] = "grey"

    return processed_task


def process_tasks(tags):
    """
    Process all tasks obtained from the Habitica API and count tasks by type and status.

    Args:
        tags (dict): Dictionary containing tag information.

    Returns:
        dict: Dictionary containing processed tasks grouped by types and tags,
        along with task counts.
    """
    all_tasks = habitica_api.get("tasks/user")["data"]
    used_tags = set()
    broken_challenges = list()
    tasks_full = {}
    tasks_dict = {
        "habits": [],
        "todos": {"due": [], "grey": [], "red": []},
        "dailys": {"done": [], "due": [], "grey": []},
        "rewards": [],
        "tags": [],
        "counts": {
            "total": 0,
            "habits": 0,
            "todos": {"due": 0, "grey": 0, "red": 0},
            "dailys": {"done": 0, "due": 0, "grey": 0},
            "rewards": 0,
        },
    }
    number_total = 0
    for idx, task in enumerate(all_tasks):
        number_total += 1
        processed_task = process_task(task, tags)
        tasks_full.update({processed_task["id"]: processed_task})
        used_tags.update(task["tags"])
        if "broken" in task["challenge"]:
            broken_challenges.append(task["id"])

        if task["type"] == "todo" or task["type"] == "daily":
            status = processed_task["status"]
            type_task = task["type"] + "s"
            tasks_dict["counts"][type_task][status] += 1

            tasks_dict[task["type"] + "s"][processed_task["status"]].append(
                processed_task["id"]
            )
        else:
            tasks_dict[task["type"] + "s"].append(processed_task["id"])
            tasks_dict["counts"][task["type"] + "s"] += 1

    tasks_dict["tags"] = list(used_tags)
    tasks_dict["broken"] = list(broken_challenges)
    tasks_dict["counts"]["total"] = number_total
    save_file.save_file(tasks_dict, "all_tasks")
    save_file.save_file(tasks_full, "tasks_data")
    allan_tasks = dict({"data": tasks_full, "stats": tasks_dict})
    return allan_tasks
