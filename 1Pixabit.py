#!/usr/bin/env python3
import auth_file
import get_stats
import get_tags
import clean_tags
import get_tasks
import get_all_data
import filter_task
import Rich
import rich_tags
from rich.theme import Theme
from rich.console import Console

# Read the theme from "styles" file and initialize the console with the theme
theme = Theme.read("styles")
console = Console(theme=theme)

auth_file.check_auth_file()
all_tags = get_tags.get_tags()
all_tasks = get_tasks.process_tasks(all_tags)
stats = get_stats.get_stats(all_tasks["stats"])
unused_tags = clean_tags.get_unused_tags(all_tags, all_tasks["stats"]["tags"])
get_all_data.save_all_user_data()
Rich.print_stats(stats)
# rich_tags.print_tags(all_tags)
# rich_tags.print_unused(unused_tags)
# filter_task.find_broken(all_tasks["data"], all_tasks["stats"]["broken"])
# filter_task.list_broken(all_tasks["data"], all_tasks["stats"]["broken"])

# # if Stats["sleeping"] is True:
# #     sleeping_status.sleeping_status("sleeping", "awake")
# # else:
# #     sleeping_status.sleeping_status("awake", "sleeping")
# rich_tags.show_tags(Tagsx, "name")
