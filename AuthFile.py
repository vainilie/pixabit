# ────────────────────────────────────────────── #
#          CREATE FILE WITH CREDENTIALS          #
# ────────────────────────────────────────────── #

import configparser
import os.path

config = configparser.ConfigParser()
config["habitica"] = {"apiUser": "user-id-here", "apiToken": "api-token-here"}
config["tags"] = {}
tags = config["tags"]
tags["challenge"] = "tag-id-here"
tags["owned"] = "tag-id-here"


def CreateAuth():
    """to create file <auth.ini>"""
    with open("auth.ini", "w") as configfile:
        config.write(configfile)


def CheckAuth():
    """to check if the file <auth.ini> exists. if not, it will call the create function"""
    if os.path.exists("auth.ini"):
        config.read("auth.ini")
        print("File exists")

    else:
        CreateAuth()
        print("auth.ini file created")


def GetKey(section, key):
    """Get keys from file [section and key to get]"""
    config.read("auth.ini")
    return config[section][key]
