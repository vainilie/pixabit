#!/usr/bin/env python3
"""open env"""
console = Console(theme=theme)
from art import *
from ratelimit import limits, RateLimitException, sleep_and_retry
from rich import box
from rich import print
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
import argparse
import authf
import configparser
import emoji_data_python
import json
import os
import requests
import rich
import sys
import timeago


theme = Theme.read("styles")



# ─── % GET TASKS ────────────────────────────────────────────────────────────────
#
def tasks(tags):
    """get all user data"""
    outfile = open("tasks_.json", "w", encoding="utf-8")
    all_tasks = requests.get(BASEURL + "tasks/user", headers=HEADERS)
    json.dump(all_tasks.json(), outfile, separators=(",", ":"), sort_keys=True)
    all_ = {}
    d = {}
    dGrey = []
    dDue = []
    dDone = []
    h = []
    t = {}
    r = []
    tGrey = []
    tExp = []
    tDue = []
    alltags = []

    for idx, task in enumerate(all_tasks.json()["data"]):
        _task = {}

        if len(task["challenge"]) == 0:
            challenge_ = ""
        else:
            challenge_ = emoji_data_python.replace_colons(
                task["challenge"]["shortName"]
            )

        tags_ = []

        for tag in task["tags"]:
            tag_ = tags[tag]["name"]
            tags_.append(tag_)
            alltags.append(tag)
        _task.update(
            {
                "_idx": idx,
                "attr": task["attribute"],
                "challenge": challenge_,
                "id": task["id"],
                "notes": emoji_data_python.replace_colons(task["notes"]),
                "priority": task["priority"],
                "tags": tags_,
                "title": emoji_data_python.replace_colons(task["text"]),
                "value": color_value(task["value"]),
            }
        )

        if task["type"] == "habit":
            if task["up"] and task["down"]:
                _direction = "both"
                _count = f'⧾{task["counterUp"]}｜-{task["counterDown"]}'
            elif not task["up"] and not task["down"]:
                _direction = "none"
                _count = f'⧾{task["counterUp"]}｜-{task["counterDown"]}'

            elif task["up"] and not task["down"]:
                _direction = "up"
                _count = f'⧾{task["counterUp"]}'

            else:
                _direction = "down"
                _count = f'-{task["counterDown"]}'

            _task.update(
                {
                    "counter": _count,
                    "direction": _direction,
                    "frequency": task["frequency"],
                }
            )

            h.append(_task)

        elif task["type"] == "reward":
            _task.update({"value": task["value"]})
            r.append(_task)

        else:
            if len(task["checklist"]) >= 1:
                for idy, check in enumerate(task["checklist"]):
                    idxy = float(str(idx) + "." + str(idy))
                    check.update({"_idx": idxy})

            _task.update(
                {
                    "_status": task["completed"],
                    "subtasks": len(task["checklist"]),
                    "checklist": task["checklist"],
                }
            )

            if task["type"] == "daily":
                _task.update(
                    {
                        "streak": task["streak"],
                        "next": next_one(task["nextDue"][0]),
                        "_isDue": task["isDue"],
                    }
                )

                if not task["isDue"]:
                    dGrey.append(_task)
                else:
                    if task["completed"]:
                        dDone.append(_task)
                    else:
                        dDue.append(_task)
            else:
                if "date" in task:
                    if task["date"] is None:
                        _deadLine = ""
                        _isDue = False
                    else:
                        _deadLine = date(task["date"])
                        _isDue = True
                else:
                    _deadLine = ""
                    _isDue = False
                _task.update({"_isDue": _isDue, "next": _deadLine})

                if _isDue:
                    if expired(task["date"]):
                        tExp.append(_task)
                    else:
                        tDue.append(_task)
                else:
                    tGrey.append(_task)

    t.update({"due": tDue, "grey": tGrey, "expired": tExp})
    d.update({"done": dDone, "due": dDue, "grey": dGrey})
    alltag = l2s(alltags)
    all_.update({"habits": h, "dailies": d, "todos": t, "rewards": r, "tags": alltag})

    with open("tasks.json", "w", encoding="utf8") as json_file:
        json.dump(
            all_,
            json_file,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            indent=3,
            default=str,
        )
    return all_


#
# ─── % TOGGLE SLEEPING ──────────────────────────────────────────────────────────
#


# ArgParse
class Debug(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        import pdb

        pdb.set_trace()


# MAIN

parser = argparse.ArgumentParser(
    description="Dumps your tasks to a file user-tasks.json in the current directory"
)

parser.add_argument(
    "-o",
    "--outfile",
    type=argparse.FileType("w"),
    default="user-tasks.json",
    help="JSON data file (default: user-tasks.json)",
)

parser.add_argument("--debug", action=Debug, nargs=0, help=argparse.SUPPRESS)

args = parser.parse_args()

#

# with open(args.outfile, 'w') as f:
# json.dump(challenges.json(), args.outfile, separators=(",", ":"), sort_keys=True, indent=6)
# print(challenges.json())

myTags = get_tags()
all_ = tasks(myTags)

stats_ = stats()
display(stats_)
display_sleep(stats_)


def clean_tags():
    usedtag = all_["tags"]
    alltag = []

    for tag in myTags:
        alltag.append(tag)
    used = l2s(usedtag)
    alls = l2s(alltag)
    m = alls.difference(used)
    print(f"used: {len(used)} all:{len(alls)}, inter:{len(m)}")
    for x in m:
        print(x)
        print(myTags[x]["name"])
        if Confirm.ask("Delete unused tag?"):
            deletetag = requests.delete(BASEURL + "tags/" + x, headers=HEADERS)

            print(deletetag)


clean_tags()
