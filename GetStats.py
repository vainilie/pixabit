import Requests, SaveFile
import json
import emoji_data_python

"""parse stats"""
def GetStats():
    RawStats = Requests.GetAPI("user?userFields=stats,party")
    get_stats = requests.get(BASEURL + ", headers=HEADERS)
    print(get_stats.headers)
    _stats = get_stats.json()["data"]["stats"]
    _username = get_stats.json()["data"]["auth"]["local"]["username"]
    _sleeping = get_stats.json()["data"]["preferences"]["sleep"]
    _quests = get_stats.json()["data"]["party"]["quest"]
    _time = date(get_stats.json()["data"]["auth"]["timestamps"]["loggedin"])
    _start = get_stats.json()["data"]["preferences"]["dayStart"]
    _habits = len(all_["habits"])
    _reward = len(all_["rewards"])
    _dailies = {}
    _dailies.update(
        {
            "done": len(all_["dailies"]["done"]),
            "due": len(all_["dailies"]["due"]),
            "grey": len(all_["dailies"]["grey"]),
            "total": (
                len(all_["dailies"]["done"])
                + len(all_["dailies"]["due"])
                + len(all_["dailies"]["grey"])
            ),
        }
    )
    _todos = {}
    _todos.update(
        {
            "expired": len(all_["todos"]["expired"]),
            "due": len(all_["todos"]["due"]),
            "grey": len(all_["todos"]["grey"]),
            "total": (
                len(all_["todos"]["expired"])
                + len(all_["todos"]["due"])
                + len(all_["todos"]["grey"])
            ),
        }
    )

    _total = {}
    _total.update(
        {
            "habits": _habits,
            "dailies": _dailies,
            "todos": _todos,
            "rewards": _reward,
            "total": _habits + _reward + _todos["total"] + _dailies["total"],
        }
    )
    _stats.update(
        {
            "username": _username,
            "sleeping": _sleeping,
            "quest": _quests,
            "time": _time,
            "start": _start,
            "total": _total,
        }
    )
    with open("stats.json", "w", encoding="utf8") as json_file:
        json.dump(
            _stats,
            json_file,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            indent=3,
            default=str,
        )

    return _stats
