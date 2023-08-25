from core import habitica_api
import json


def create_challenge_from_json(json_path):
    """
    Create a challenge in Habitica based on data from a JSON file.

    Args:
        json_path (str): The path to the JSON file containing challenge data.

    Returns:
        None
    """
    with open(json_path, "r") as json_file:
        data = json.load(json_file)

        challenge_data = {
            "group": "00000000-0000-4000-A000-000000000000",
            "name": f"[Permanent] ∞ {data['_name']}",
            "shortName": data["shortName"],
            "summary": f"{data['_summary']}]",
            "description": f"{data['_description']}\n\n---\n---\n- This is an identical copy of the challenge created by [@{data['leader']['auth']['local']['username']}](https://habitica.com/profile/{data['leader']['id']}) in the _{data['group']['name']}_ †.\n- This is a **[ᴘᴇʀᴍᴀɴᴇɴᴛ ᴄʜᴀʟʟᴇɴɢᴇ ∞]** so it will never end. Feel free to join, leave and modify the tasks to fulfill your needs.",
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
json_file_path = "___challenges/DailySpell.json"
create_challenge_from_json(json_file_path)
