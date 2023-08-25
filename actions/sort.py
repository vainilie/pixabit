from core import habitica_api
from get import get_rawtasks
import time


def sort_alpha():
    tasks = get_rawtasks.get_rawtasks()
    for idx, task in enumerate(tasks):
        habitica_api.post(f"tasks/{task['_id']}/move/to/-1")
        print(idx, len(tasks), "/")
