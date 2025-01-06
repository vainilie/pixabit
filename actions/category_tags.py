from core.auth_file import get_key_from_config
from core.habitica_api import post, delete
from utils.rich_utils import Confirm, print
from rich.progress import track


def ischallenge_or_personal_tags(all_tasks):
    challenge_tag = get_key_from_config("tags", "challenge", "tags.ini")
    personal_tag = get_key_from_config("tags", "owned", "tags.ini")

    categories = {"challenge": [], "unpersonal": [], "unchallenge": [], "personal": []}
    tags_to_fix = 0  # Initialize the count of tags to fix
    actions_to_perform = []  # List to store batched actions

    for task_id, item in all_tasks.items():
        tags = item["tag_id"]
        is_challenge = len(item["challenge"]) != 0

        if is_challenge and challenge_tag not in tags:
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("post", task_id, challenge_tag))

        if is_challenge and personal_tag in tags:
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("delete", task_id, personal_tag))

        if not is_challenge and challenge_tag in tags:
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("delete", task_id, challenge_tag))

        if personal_tag not in tags and not is_challenge:
            tags_to_fix += 1  # Increment the count
            actions_to_perform.append(("post", task_id, personal_tag))

    if tags_to_fix == 0:
        print(f"All your tags are OK :thumbsup:")
    else:
        if tags_to_fix > 30:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (minutes): {round(tags_to_fix/30, 2)}"""
            )
        else:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (seconds)  {round((tags_to_fix*60)/30, 2)}"""
            )

        prompt = f"Continue?"
        if Confirm.ask(prompt, default=False):
            for action, task_id, tag in track(
                actions_to_perform, description="Fixing tags..."
            ):
                if action == "post":
                    post(f"tasks/{task_id}/tags/{tag}")
                elif action == "delete":
                    delete(f"tasks/{task_id}/tags/{tag}")
            print("[b]Your tasks' tags are now clean  :cherry_blossom:")
        else:
            print("[b]OK, no changes done :cherry_blossom:")

    return categories


def ispsn_ornot(all_tasks):
    psn_tag = get_key_from_config("tags", "psn", "tags.ini")
    notpsn_tag = get_key_from_config("tags", "not_psn", "tags.ini")

    categories = {"psn": [], "not_psn": []}
    tags_to_fix = 0  # Initialize the count of tags to fix
    actions_to_perform = []  # List to store batched actions

    for task_id, item in all_tasks.items():
        tags = item["tag_id"]
        if psn_tag not in tags:
            if notpsn_tag not in tags:
                tags_to_fix += 1  # Increment the count
                actions_to_perform.append(("post", task_id, notpsn_tag))

    if tags_to_fix == 0:
        print(f"All your tags are OK :thumbsup:")
    else:
        if tags_to_fix > 30:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (minutes): {round(tags_to_fix/30, 2)}"""
            )
        else:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (seconds)  {round((tags_to_fix*60)/30, 2)}"""
            )

        prompt = f"Continue?"

        if Confirm.ask(prompt, default=False):
            for action, task_id, tag in track(
                actions_to_perform, description="Fixing poisoned tags..."
            ):
                if action == "post":
                    post(f"tasks/{task_id}/tags/{tag}")
                elif action == "delete":
                    delete(f"tasks/{task_id}/tags/{tag}")
            print("[b]Your tasks' tags are now clean  :cherry_blossom:")
        else:
            print("[b]OK, no changes done :cherry_blossom:")

    return categories


def tags_replace(del1, add1, all_tasks, what=None):
    categories = {"psn": [], "not_psn": []}
    tags_to_fix = 0  # Initialize the count of tags to fix
    actions_to_perform = []  # List to store batched actions

    for task_id, item in all_tasks.items():
        tags = item["tag_id"]
        if del1 in tags:
            if add1 not in tags:
                tags_to_fix += 1  # Increment the count

                actions_to_perform.append(("post", task_id, add1))
            if what == "replace":
                tags_to_fix += 1  # Increment the count
                actions_to_perform.append(("delete", task_id, del1))

    if tags_to_fix == 0:
        print(f"All your tags are OK :thumbsup:")
    else:
        if tags_to_fix > 30:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (minutes): {round(tags_to_fix/30, 2)}"""
            )
        else:
            print(
                f"""Total tags to be fixed: {tags_to_fix}.
                Estimated time to fix the tags (seconds)  {round((tags_to_fix*60)/30, 2)}"""
            )

        prompt = f"Continue?"
        if Confirm.ask(prompt, default=False):

            for action, task_id, tag in track(
                actions_to_perform, description="Fixing tags..."
            ):
                if action == "post":
                    post(f"tasks/{task_id}/tags/{tag}")
                elif action == "delete":
                    delete(f"tasks/{task_id}/tags/{tag}")
            print("[b]Your tasks' tags are now clean  :cherry_blossom:")
        else:
            print("[b]OK, no changes done :cherry_blossom:")

    return categories
