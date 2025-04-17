import json

from core import habitica_api


def create_challenge_from_json(json_path):
    """Create a challenge in Habitica based on data from a JSON file.

    Args:
        json_path (str): The path to the JSON file containing challenge data.

    Returns:
        None
    """
    with open(json_path) as json_file:
        data = json.load(json_file)

        challenge_data = {
            "group": "00000000-0000-4000-A000-000000000000",
            "name": data["_name"],
            "shortName": data["shortName"],
            "summary": data["_summary"],
            "description": data["_description"],
            "prize": 1,
        }

        if len(challenge_data["summary"]) < 250:
            created_challenge = habitica_api.post("challenges", data=challenge_data)
            challenge_id = created_challenge["data"]["id"]
            print("Challenge created with ID:", challenge_id)

            tasks = data["_tasks"]
            keys_to_remove = ["id", "_id", "challenge", "tags"]
            for task in tasks:
                for key in keys_to_remove:
                    task.pop(key, None)

            habitica_api.post(f"tasks/challenge/{challenge_id}", data=tasks)
        else:
            print("Summary is too long. Challenge not created.")


# Usage
json_file_path = "_challenges/Magic Pills.json"
create_challenge_from_json(json_file_path)
