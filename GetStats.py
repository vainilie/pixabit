import Requests, SaveFile
import json
import emoji_data_python
from  DatesKLWP import Date
"""parse stats"""
def GetStats():
    Response = Requests.GetAPI("user?userFields=stats,party")
    RawData = Response["data"]
    Stats = {}
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
            "username": RawData["auth"]["local"]["username"],
            "resting": RawData["preferences"]["sleep"],
            "quest": RawData["party"]["quest"],
            "timestamp": RawData["auth"]["timestamps"]["loggedin"],
            "day_start": RawData["preferences"]["dayStart"],
        }
    )
    SaveFile.SaveFile(Stats,"Stats")

    return Stats


GetStats()