#!/usr/bin/env python3
"""open env"""
import AuthFile
import Requests
import SaveFile
import Tags

AuthFile.CheckAuth()
user = Requests.GetAPI("user")
SaveFile.SaveFile(user, "UserData")
Tags.GetTags()
