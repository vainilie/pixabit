#!/usr/bin/env python3

# Import necessary modules
from core import auth_file
from get import (
    bkup_challenges,
    get_tags,
    get_tasks,
    get_stats,
    get_userdata,
)
from interface import Rich, rich_tags
from actions import unused_tags, filter_task, sleeping
from utils.rich_utils import print, Confirm, Prompt

# Check authentication file
auth_file.check_auth_file()

# Get tags and tasks data
tags = get_tags.get_tags()
all_tasks = get_tasks.process_tasks(tags)
stats = get_stats.get_user_stats(all_tasks["cats"])
unused = unused_tags.get_unused_tags(tags, all_tasks["cats"]["tags"])

# Print backup options
if Confirm.ask("Backup [i]challenges[/i]?", default=True):
    bkup_challenges.join_challenges_and_tasks()
    print("Challenges Saved")

# Print user stats
if Confirm.ask("Print [i]stats[/i]?", default=True):
    Rich.print_stats(stats)

# Print unused tags and offer deletion option
if Confirm.ask("Print [i]unused tags[/i]?", default=True):
    rich_tags.print_unused(unused)
    if Confirm.ask("Delete [i]unused tags[/i]?", default=False):
        unused_tags.delete_unused_tags(unused)

# Perform actions based on user input
fruit = Prompt.ask("Enter a fruit", choices=["save", "tags", "broken", "sleep"])
print(f"Selected {fruit!r}")

if fruit == "save":
    get_userdata.save_all_user_data()
elif fruit == "tags":
    rich_tags.print_tags(tags)
elif fruit == "broken":
    if stats["broken"] > 0:
        filter_task.list_broken(all_tasks["data"], all_tasks["cats"]["broken"])
        if Confirm.ask("Unlink [i]broken tasks[/i]?", default=False):
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
