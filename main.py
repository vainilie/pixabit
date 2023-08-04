#!/usr/bin/env python3
from core import auth_file, habitica_api
from core import save_file
from get import get_tags, get_tasks, get_stats
from interface import Rich, rich_tags
from actions import unused_tags, filter_task
auth_file.check_auth_file()
tags = get_tags.get_tags()
all_tasks = get_tasks.process_tasks(tags)
stats = get_stats.get_user_stats(all_tasks["cats"])


unused = unused_tags.get_unused_tags(tags, all_tasks["cats"]["tags"])
unused_tags.delete_unused_tags(unused)
#save_user_data.save_all_user_data()
Rich.print_stats(stats)
#rich_tags.print_tags(all_tags)
rich_tags.print_unused(unused)
filter_task.find_broken(all_tasks["data"], all_tasks["cats"]["broken"])
filter_task.list_broken(all_tasks["data"], all_tasks["cats"]["broken"])

# # if Stats["sleeping"] is True:
# #     sleeping_status.sleeping_status("sleeping", "awake")
# # else:
# #     sleeping_status.sleeping_status("awake", "sleeping")
# rich_tags.show_tags(Tagsx, "name")
