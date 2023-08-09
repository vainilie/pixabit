#!/usr/bin/env python3
from core import auth_file, save_file, habitica_api
from get import get_tags, get_tasks, get_stats, get_userdata
from interface import Rich, rich_tags
from actions import unused_tags, filter_task, sleeping, category_tags
from utils.rich_utils import print, Confirm, IntPrompt, Prompt, console
import time
auth_file.check_auth_file()
tags = get_tags.get_tags()
all_tasks = get_tasks.process_tasks(tags)
save_file.save_file(all_tasks,"rawtasks")
stats = get_stats.get_user_stats(all_tasks["cats"])
unused = unused_tags.get_unused_tags(tags, all_tasks["cats"]["tags"])

num = 0
while num >= 0 :
     save_file.save_file(habitica_api.get(f"challenges/user?page={num}&member=true")["data"], f"Member{num}")
     num += 1
     time.sleep(60/30)


if Confirm.ask("Print [i]stats[/i]?", default=True):
    if True:
        Rich.print_stats(stats)
if Confirm.ask("Print [i]unused tags[/i]?", default=True):
    if True:
        rich_tags.print_unused(unused)
        if Confirm.ask("Delete [i]unused tags[/i]?", default=False):
            if True:
                unused_tags.delete_unused_tags(unused)
#category_tags.category_Tags(all_tasks["data"])
fruit = Prompt.ask("Enter a fruit", choices=["save", "tags", "broken"])
print(f"Selected {fruit!r}")
if fruit == "save":
    get_userdata.save_all_user_data()
elif fruit == "tags":
    rich_tags.print_tags(tags)
elif fruit == "broken":
    if stats["broken"] > 0:
        filter_task.list_broken(all_tasks["data"], all_tasks["cats"]["broken"])
        if Confirm.ask("Unlink [i]broken tasks[/i]?", default=False):
            if True:
                filter_task.delete_broken(all_tasks["data"], all_tasks["cats"]["broken"])
    else:
        print("No broken tasks")
elif fruit == "sleep":
    if stats["sleeping"] is True:
        sleeping.toggle_sleeping_status("sleeping", "awake")
    else:
        sleeping.toggle_sleeping_status("awake", "sleeping")

else:
    print("[b]OK :loudly_crying_face:")
