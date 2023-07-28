import habitica_api, save_file
import json
import emoji_data_python
import dateutil
import dateutil.parser
import timeago, datetime


"""parse stats"""


def Date(utc):
    """convert time"""
    utc_time = dateutil.parser.parse(utc)
    return utc_time.astimezone().replace(microsecond=0)


def GetStats():

    Response = habitica_api.get("user?userFields=stats,party")
    RawData = Response["data"]
    Stats = {}
    LastLogin = RawData["auth"]["timestamps"]["loggedin"]
    LastLogin = datetime.datetime.fromisoformat(LastLogin)
    while RawData["stats"]["class"] =="wizard":
        RawData["stats"]["class"] = "mage"
    # Habits = len(all_["habits"])
    # Rewards = len(all_["rewards"])
    # Dailies = {}
    # Dailies.update(
    #     {
    #         "done": len(all_["dailies"]["done"]),
    #         "due": len(all_["dailies"]["due"]),
    #         "grey": len(all_["dailies"]["grey"]),
    #         "total": (
    #             len(all_["dailies"]["done"])
    #             + len(all_["dailies"]["due"])
    #             + len(all_["dailies"]["grey"])
    #         ),
    #     }
    # )
    # _todos = {}
    # _todos.update(
    #     {
    #         "expired": len(all_["todos"]["expired"]),
    #         "due": len(all_["todos"]["due"]),
    #         "grey": len(all_["todos"]["grey"]),
    #         "total": (
    #             len(all_["todos"]["expired"])
    #             + len(all_["todos"]["due"])
    #             + len(all_["todos"]["grey"])
    #         ),
    #     }
    # )

    # _total = {}
    # _total.update(
    #     {
    #         "habits": Habits,
    #         "dailies": Dailies,
    #         "todos": _todos,
    #         "rewards": Rewards,
    #         "total": Habits + Rewards + _todos["total"] + Dailies["total"],
    #     }
    # )
    Stats.update(
        {
            "class": RawData["stats"]["class"],
            "level": RawData["stats"]["lvl"],
            "quest": RawData["party"]["quest"],
            "sleeping": RawData["preferences"]["sleep"],
            "start": RawData["preferences"]["dayStart"],
            "stats": RawData["stats"],
            "time": str(LastLogin),
            "username": RawData["auth"]["local"]["username"],
        }
    )
    save_file.save_file(Stats, "Stats")

    return Stats


GetStats()
