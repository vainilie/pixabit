import habitica_api
import save_file
import emoji_data_python
import convert_date
import ColorValues


def process_task_tags(task, tags):
    tag_names = []
    for tag in task["tags"]:
        for category in tags:
            for tagg in tags[category]:
                if tag == tagg["id"]:
                    tag_names.append(tagg["name"])
    return tag_names


def process_task(task, tags):
    processed_task = {
        "id": task["id"],
        "type": task["type"],
        "text": emoji_data_python.replace_colons(task["text"]),
        "attribute": task["attribute"],
        "tags_id": task["tags"],
        "challenge": emoji_data_python.replace_colons(task["challenge"]["shortName"])
        if len(task["challenge"]) > 0
        else "",
        "notes": emoji_data_python.replace_colons(task["notes"]),
        "tags_names": process_task_tags(task, tags),
        "priority": task["priority"],
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
                "counter": count,
                "direction": direction,
                "frequency": task["frequency"],
                "value": task["value"],
                "color": ColorValues.value_color(task["value"]),
            }
        )
    else:
        processed_task.update(
            {
                "completed": task["completed"],
                "checklist": len(task["checklist"]),
                "value": task["value"],
                "color": ColorValues.value_color(task["value"]),
            }
        )

        if task["type"] == "daily":
            processed_task.update(
                {
                    "streak": task["streak"],
                    "next": task["nextDue"][0],
                    "is_due": task["isDue"],
                    "status": "grey"
                    if not task["isDue"]
                    else "done"
                    if task["completed"]
                    else "due",
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


def getTasks(tags):
    all_tasks = habitica_api.get("tasks/user")["data"]
    used_tags = set()
    tasks_dict = {
        "habits": [],
        "todos": {"done": [], "due": [], "grey": [], "red": []},
        "dailys": {"done": [], "due": [], "grey": []},
        "rewards": [],
        "tags": [],
    }

    for task in all_tasks:
        processed_task = process_task(task, tags)
        used_tags.update(task["tags"])
        if task["type"] == "todo" or task["type"] == "daily":
            tasks_dict[task["type"] + "s"][processed_task["status"]].append(
                processed_task
            )
        else:
            tasks_dict[task["type"] + "s"].append(processed_task)

    tasks_dict.update({"tags": list(used_tags)})

    save_file.save_file(tasks_dict, "AllTasks")
    return tasks_dict


# ─── % GET TASKS ────────────────────────────────────────────────────────────────
