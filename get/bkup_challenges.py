from core import save_file
import emoji_data_python
from get import get_challenges, get_rawtasks
from utils import replace_filename

def join_challenges_and_tasks():
    """
    Get challenges data and associated tasks, manipulate and save them.

    This function retrieves raw tasks and challenges data, manipulates them
    by filtering tasks associated with each challenge, updating challenge names,
    descriptions, and other properties, and finally saves each challenge
    to a separate JSON file in the "_challenges" folder.

    Returns:
        None

    Example:
        get_challengesallenges()
    """
    tasks = get_rawtasks.get_rawtasks()
    challenges = get_challenges.get_my_challenges()
    sorted_challenges = sorted(challenges, key=lambda x: x["name"])

    for challenge in sorted_challenges:
        backup = {}
        backup = challenge

        bk_tasks = []
        for task in tasks:
            if len(task["challenge"]) > 0 and task["challenge"]["id"] == backup["id"]:
                bk_tasks.append(task)

        backup["_tasks"] = bk_tasks
        backup["_name"] = backup.pop("name")
        title = replace_filename.replace_illegal_filename_characters_leading_underscores(backup["_name"])
        backup["_description"] = backup.pop("description")
        backup["_summary"] = (backup.pop("summary") if "summary" in backup else "")
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
            if isinstance(value, str):
                new_value = emoji_data_python.replace_colons(value)
                backup[key] = new_value

        save_file.save_file(backup, title, "___Challenges")
