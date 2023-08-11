from core import habitica_api
import json


with open("_challenges/Take care of yourself.json", "r") as json_file:
    data = json.load(json_file)
    tag = {"name": data["_name"]}
    request = habitica_api.post("tags", data=tag)
    tag_id = request["data"]["id"]
    tasks = data["_tasks"]
    keys_del = ["id","_id","challenge"]
    for task in tasks:
        for key in keys_del:
            task.pop(key, None)
            task["tags"] = tag_id
        print(task)
    habitica_api.post("tasks/user", data=tasks)
