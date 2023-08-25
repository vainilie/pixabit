from core.auth_file import get_key_from_config
from core.habitica_api import post, delete, put
from utils.rich_utils import Confirm, print


def set_attr(all_tasks):
    str = get_key_from_config("tags", "STR", "tags.ini")
    int = get_key_from_config("tags", "INT", "tags.ini")
    con = get_key_from_config("tags", "CON", "tags.ini")
    per = get_key_from_config("tags", "PER", "tags.ini")
    noatr = get_key_from_config("tags", "NOT_ATR", "tags.ini")
    tags_to_fix = 0  # Initialize the count of tags to fix
    actions_to_perform = []  # List to store batched actions

    for task_id, item in all_tasks.items():
        tags = item["tag_id"]
        atr = item["attribute"]
        if str in tags and atr != "str":
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("PUT", task_id, "str"))
        if int in tags and atr != "int":
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("PUT", task_id, "int"))
        if con in tags and atr != "con":
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("PUT", task_id, "con"))
        if per in tags and atr != "per":
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("PUT", task_id, "per"))

        if per not in tags and con not in tags and str not in tags and int not in tags:
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("post", task_id, noatr))

    if tags_to_fix == 0:
        print(f"All your attr are OK :thumbsup:")
    else:
        if tags_to_fix > 30:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the attr (minutes): {round(tags_to_fix/30, 2)}"""
            )
        else:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the attr (seconds)  {round((tags_to_fix*60)/30, 2)}"""
            )

        prompt = f"Continue?"
        if Confirm.ask(prompt, default=False):
            for action, task_id, tag in actions_to_perform:
                if action == "PUT":
                    put(f"tasks/{task_id}?attribute={tag}")
                if action == "post":
                    post(f"tasks/{task_id}/tags/{tag}")
            print("[b]Your tasks' attributes  are now clean  :cherry_blossom:")
        else:
            print("[b]OK, no changes done :cherry_blossom:")
