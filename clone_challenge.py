from core import habitica_api
import json


with open("_challenges/What tasks should I add? .json", "r") as json_file:
    data = json.load(json_file)
    challenge = {
        "group": "00000000-0000-4000-A000-000000000000",
        "name": data["_name"],
        "shortName": data["shortName"],
        "summary": data["summary"],
        "description": data["_description"],
        "prize": 1,
    }
    chall = habitica_api.post("challenges", data=challenge)
    print(chall["data"]["id"])
    challengeid = chall["data"]["id"]

    tasks = data["_tasks"]
    keys_del = ["id", "_id", "challenge", "tags","startDate"]
    for task in tasks:
        for key in keys_del:
            task.pop(key, None)
        print(task)
    habitica_api.post(f"tasks/challenge/{challengeid}", data=tasks)
