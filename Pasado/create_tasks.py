from core import habitica_api
import json


def create_tasks_from_challenge_json(json_path):
    """
    Create tasks in Habitica from challenge data in a JSON file.

    Args:
        json_path (str): The path to the JSON file containing challenge data.

    Returns:
        None
    """
    with open(json_path, "r") as json_file:
        data = json.load(json_file)

        # Create a tag for the challenge
        tag_data = {"name": data["_name"]}
        created_tag = habitica_api.post("tags", data=tag_data)
        tag_id = created_tag["data"]["id"]

        tasks = data["_tasks"]
        keys_to_remove = ["id", "_id", "challenge"]

        for task in tasks:
            for key in keys_to_remove:
                task.pop(key, None)
            task["tags"] = tag_id

        created_tasks = habitica_api.post("tasks/user", data=tasks)

        print("Tasks created:", created_tasks)


# Usage
json_file_path = "_challenges/Sandman.json"
create_tasks_from_challenge_json(json_file_path)
