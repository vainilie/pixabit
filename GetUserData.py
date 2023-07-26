import Requests
import SaveFile


def getTasks(ids):
    Taks = Requests.GetAPI("tasks/user")
    Taks = Taks["data"]
    habits = []
    todos = []
    dailies = []
    rewards = []
    Tasks = {}
    usedtags = []
    for Tak in Taks:
        for tag in Tak["tags"]:
            usedtags.append(tag)
        if Tak["type"] == "habit":
            habits.append(Tak)
        elif Tak["type"] == "todo":
            todos.append(Tak)
        elif Tak["type"] == "daily":
            dailies.append(Tak)
        else:
            rewards.append(Tak)
    Tasks.update(
        {"dailies": dailies, "habits": habits, "todos": todos, "rewards": rewards, "tags": sorted(set(usedtags))}
    )
    print(
        f" Total: {len(Taks)} \n Habits: {len(habits)} \n Todos: {len(todos)}\n Dailys: {len(dailies)} \n Rewards:{len(rewards)}"
    )
    SaveFile.SaveFile(Tasks, "AllTasks")
    
    print(set(ids).difference(set(usedtags)))
