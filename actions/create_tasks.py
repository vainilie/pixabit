from core import habitica_api
import json


with open('_challenge/Take care of yourself.json', 'r') as json_file:
    data = json.load(json_file)
    tasks = data["tasks"]
    habitica_api.post("tasks/user", data=tasks)
    
    
