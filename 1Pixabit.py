#!/usr/bin/env python3
"""open env"""
import auth_file
import habitica_api
import save_file
import tags
import GetStats
import sleeping_status
import rich_tags
import Rich
import GetUserData

auth_file.check_auth_file()
user = habitica_api.get("user")
save_file.save_file(user, "UserData")
Tagsx = tags.get_tags()
Stats = GetStats.GetStats()
Rich.display(Stats)
# if Stats["sleeping"] is True:
#     sleeping_status.sleeping_status("sleeping", "awake")
# else:
#     sleeping_status.sleeping_status("awake", "sleeping")
rich_tags.show_tags(Tagsx, "name")
user = GetUserData.getTasks(Tagsx)
ids = tags.get_all_tag_ids(Tagsx,set(user["tags"]))
