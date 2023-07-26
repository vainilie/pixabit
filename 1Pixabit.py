#!/usr/bin/env python3
"""open env"""
import AuthFile
import Requests
import SaveFile
import Tags
import GetStats
import Sleeping
import ListTags
import Rich
import GetUserData

AuthFile.CheckAuth()
user = Requests.GetAPI("user")
SaveFile.SaveFile(user, "UserData")
Tagsx = Tags.GetTags()
Stats = GetStats.GetStats()
Rich.display(Stats)
# if Stats["sleeping"] is True:
#     Sleeping.Sleeping("sleeping", "awake")
# else:
#     Sleeping.Sleeping("awake", "sleeping")

ListTags.Show(Tagsx, "name")
ids = ListTags.IDs(Tagsx)
GetUserData.getTasks(ids)