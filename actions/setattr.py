from core.auth_file import get_key_from_config
from core.habitica_api import post, delete, put
from utils.rich_utils import Confirm, print
import json


def set_attr(all_tasks):
    """
    Set the attribute of tasks based on the tags

    This function takes all tasks data from the Habitica API and sets the attribute
    of each task based on the tags. The tags and their corresponding attributes are
    set in the 'tags.ini' file.

    Args:
        all_tasks (dict): The all tasks data received from the Habitica API.

    Returns:
        None
    """
    strength = get_key_from_config("tags", "STR", "tags.ini")
    intelligence = get_key_from_config("tags", "INT", "tags.ini")
    constitution = get_key_from_config("tags", "CON", "tags.ini")
    perception = get_key_from_config("tags", "PER", "tags.ini")
    no_attribute = get_key_from_config("tags", "NOT_ATR", "tags.ini")

    tags_to_fix = 0  # Initialize the count of tags to fix
    actions_to_perform = []  # List to store batched actions

    for task_id, item in all_tasks.items():
        tags = item["tag_id"]
        attribute = item["attribute"]

        # Filter attribute-related tags
        attribute_tags = [
            tag
            for tag in tags
            if tag in {strength, intelligence, constitution, perception}
        ]

        if len(attribute_tags) > 1:
            # More than one attribute-related tag: assign no_attribute
            if no_attribute not in tags:
                tags_to_fix += 1
                actions_to_perform.append(("post", task_id, no_attribute))

            for tag in attribute_tags:
                actions_to_perform.append(("delete", task_id, tag))

        elif len(attribute_tags) == 1:
            # Ensure the attribute matches the single tag
            if strength in attribute_tags and attribute != "str":
                tags_to_fix += 1
                actions_to_perform.append(("put", task_id, "str"))
            elif intelligence in attribute_tags and attribute != "int":
                tags_to_fix += 1
                actions_to_perform.append(("put", task_id, "int"))
            elif constitution in attribute_tags and attribute != "con":
                tags_to_fix += 1
                actions_to_perform.append(("put", task_id, "con"))
            elif perception in attribute_tags and attribute != "per":
                tags_to_fix += 1
                actions_to_perform.append(("put", task_id, "per"))

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
                if action == "put":
                    body = {
                        "attribute": tag,
                    }
                    put(f"tasks/{task_id}", data=body)
                if action == "post":
                    post(f"tasks/{task_id}/tags/{tag}")

                if action == "delete":
                    delete(f"tasks/{task_id}/tags/{tag}")
            print("[b]Your tasks' attributes  are now clean  :cherry_blossom:")
        else:
            print("[b]OK, no changes done :cherry_blossom:")
