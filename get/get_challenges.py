from core import save_file
import emoji_data_python
from get import get_ch, get_rawtasks


def get_challenges():
    tasks = get_rawtasks.get_rawtasks()
    # Access and manipulate the JSON challenges
    challenges = get_ch.get_my_challenges()
    sorted_challenges = sorted(challenges, key=lambda x: x["name"])

    for challenge in sorted_challenges:
        backup = {}

        backup = challenge
        bk_tasks = []
        for task in tasks:
            if (len(task["challenge"])) > 0:
                if task["challenge"]["id"] == backup["id"]:
                    bk_tasks.append(task)
        backup["_tasks"] = bk_tasks
        backup["_name"] = backup.pop("name")
        backup["_name"] = str.replace(backup["_name"], "/", "|")
        backup["_description"] = backup.pop("description")

        keys_del = [
            "history",
            "byHabitica",
            "completed",
            "createdAt",
            "group",
            "isDue",
            "nextDue",
            "updatedAt",
            "userId",
            "yesterDaily",
        ]
        for task in backup["_tasks"]:
            for key in keys_del:
                task.pop(key, None)

        for key, value in backup.items():
            if type(value) is str:
                new_value = emoji_data_python.replace_colons(
                    value
                )  # Replace this with your desired new value
                backup[key] = new_value

        save_file.save_file(backup, backup["_name"], "_challenges")
