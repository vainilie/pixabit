from basis.auth_file import get_key_from_config
from basis.api_method import post, delete, put
from TUI.rich_utils import Confirm, print


def set_attr(tasks_data):
    """
    Set the attribute of tasks based on their tags.

    This function processes all tasks and adjusts their attributes
    (e.g., STR, INT, CON, PER) based on associated tags defined in a 'tags.ini' file.
    It ensures tasks have correct attributes and fixes inconsistencies.

    Args:
        all_tasks (dict): Dictionary of tasks data fetched from the Habitica API.

    Returns:
        None
    """
    all_tasks = tasks_data["data"]
    # Load tag-to-attribute mappings from config
    tag_to_attr = {
        get_key_from_config("attributes_tags", "STR", "auth.ini"): "str",
        get_key_from_config("attributes_tags", "INT", "auth.ini"): "int",
        get_key_from_config("attributes_tags", "CON", "auth.ini"): "con",
        get_key_from_config("attributes_tags", "PER", "auth.ini"): "per",
    }
    no_attribute = get_key_from_config("attributes_tags", "NOT_ATR", "auth.ini")
    
    tags_to_fix = 0  # Count of tags needing fixes
    actions_to_perform = []  # Store batched actions

    for task_id, task in all_tasks.items():
        tags = task["tag_id"]
        attribute = task["attribute"]

        # Identify tags related to attributes
        attribute_tags = [tag for tag in tags if tag in tag_to_attr]

        if len(attribute_tags) > 1:
            # More than one attribute-related tag: assign no_attribute
            if no_attribute not in tags:
                tags_to_fix += 1
                actions_to_perform.append(("post", task_id, no_attribute))
            for tag in attribute_tags:
                actions_to_perform.append(("delete", task_id, tag))

        elif len(attribute_tags) == 1:
            # Ensure the task attribute matches the tag's attribute
            correct_attr = tag_to_attr[attribute_tags[0]]
            if attribute != correct_attr:
                tags_to_fix += 1
                actions_to_perform.append(("put", task_id, correct_attr))

    # Provide feedback to the user
    if tags_to_fix == 0:
        print(f"All your attributes are OK :thumbsup:")
    else:
        estimated_time = (
            f"{round(tags_to_fix/30, 2)} minutes"
            if tags_to_fix > 30
            else f"{round((tags_to_fix * 60) / 30, 2)} seconds"
        )
        print(
            f"Total tags to fix: {tags_to_fix}. "
            f"Estimated time to fix attributes: {estimated_time}"
        )

        # Ask for confirmation before performing actions
        if Confirm.ask("Continue?", default=False):
            for action, task_id, tag_or_attr in actions_to_perform:
                try:
                    if action == "put":
                        body = {"attribute": tag_or_attr}
                        put(f"tasks/{task_id}", data=body)
                    elif action == "post":
                        post(f"tasks/{task_id}/tags/{tag_or_attr}")
                    elif action == "delete":
                        delete(f"tasks/{task_id}/tags/{tag_or_attr}")
                except Exception as e:
                    print(f"Error during {action} on task {task_id}: {e}")

            print("[b]Your tasks' attributes are now clean :cherry_blossom:")
        else:
            print("[b]No changes were made :cherry_blossom:")
