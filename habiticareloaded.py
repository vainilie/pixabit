#!/usr/bin/env python3
"""open env"""
import authf
import argparse
import emoji_data_python
import configparser
import json
import requests
import rich
import os
import sys
from rich.prompt import Confirm, Prompt, IntPrompt

import timeago
from rich import box
from rich import print
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.padding import Padding
from art import *
import json
from rich.theme import Theme

theme = Theme.read("styles")
console = Console(theme=theme)
nowUTC = datetime.now(timezone.utc)
nowLOC = nowUTC.astimezone()


import requests
from ratelimit import limits, RateLimitException, sleep_and_retry


#
# ─── % GET TAGS ─────────────────────────────────────────────────────────────────
#


def get_tags():
    """get tags"""
    tags = {}
    outfile = open("tags.json", "w", encoding="utf-8")
    load_tags = requests.get(BASEURL + "tags", headers=HEADERS)

    for idx, tag in enumerate(load_tags.json()["data"]):
        a_tag = {}
        name = emoji_data_python.replace_colons(tag["name"])
        challenge = "challenge" in tag
        a_tag.update(
            {"_idx": idx, "id": tag["id"], "name": name, "challenge": challenge}
        )

        tags.update({tag["id"]: a_tag})
    json.dump(
        tags,
        outfile,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        indent=3,
    )
    return tags


#
# ─── MODIFY DATE ──────────────────────────────────────────────────────────────
#


def date(utc):
    """convert time"""
    utc_time = dateutil.parser.parse(utc)
    return utc_time.astimezone().replace(microsecond=0)


def next_one(next_one):
    """str next"""
    nextDue = date(next_one)
    diff = nextDue - nowLOC
    if diff.days < 8:
        next_ = nextDue.strftime("%dd%mM%Yy%Hh%Mm%Ss")
    else:
        next_ = nextDue.strftime("%A %d %B %H:%M")
    return next_


def expired(eval):
    """check if date was in the past"""
    evaluate = date(eval)
    return evaluate < nowLOC


# ─── % GET STATS ────────────────────────────────────────────────────────────────
#


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
# ─── % DISPLAY STATS ────────────────────────────────────────────────────────────
#


def display(stat):
    """display"""
    _stats = stat
    _quest = bool(_stats.get("quest"))
    about_album = Table.grid(padding=0, expand=True)
    about_album.add_column(no_wrap=True, justify="right")
    about_album.add_column(no_wrap=True, justify="left")

    about_album.add_row(
        "[i #BDA8FF i]username",
        f"{_stats.get('username')}",
    )
    about_album.add_row(
        "[i #BDA8FF i]level",
        f"{_stats.get('lvl')}",
    )
    about_album.add_row("[i #2995CD i]class", f"{_stats.get('class')}")
    about_album.add_row("[i #BDA8FF i]sleeping", f"{_stats.get('sleeping')}")

    about_album.add_row(
        "[i #BDA8FF i]last time logged in",
        f"{timeago.format(_stats.get('time'), nowLOC)}",
    )

    about_album.add_row("[i #BDA8FF i]quest", f"{_quest}")

    about_album.add_row(
        "[i #BDA8FF i]damage up",
        f"{int(_stats.get('quest').get('progress').get('up'))}",
    )
    about_album.add_row(
        "[i #BDA8FF i]damage down",
        f"{_stats.get('quest').get('progress').get('down')}",
    )
    about_album.add_row(
        "[i #2995CD i]start time down",
        f"{_stats.get('start')} am",
    )
    for x in all_["rewards"]:
        about_album.add_row(
            "[i #2995CD i]start time down",
            f"{x.get('value')} am",
        )

    stats = Table.grid(padding=0, expand=True)

    stats.add_row("[i #FFA624 i]gold", f"{int(_stats.get('gp'))}")

    stats.add_row("[i #F74E52 i]health", f"{int(_stats.get('hp'))}")

    stats.add_row("[i #FFBE5D i]experience", f"{int(_stats.get('exp'))}")

    stats.add_row("[i #50B5E9 i]mana", f"{int(_stats.get('mp'))}")
    about = Table.grid(padding=0, expand=True)
    about.add_column(no_wrap=True)
    about.add_row(text2art(_stats.get("username"), font="doom"))
    about.add_row(about_album)
    aboute = Table.grid(padding=0, expand=True)
    aboute.add_column(no_wrap=True)
    aboute.add_column(no_wrap=True)
    aboute.add_row(about, stats)

    console.print(
        Panel(
            aboute,
            box=box.ROUNDED,
            title=f":space_invader: [b]{text2art('Habitica Stats', font='foxy')} :space_invader:",
            border_style="#BDA8FF",
            expand=False,
        ),
    )
    return _stats


#
# ─── % TOGGLE SLEEPING ──────────────────────────────────────────────────────────
#


def display_sleep(stat):
    if stat["sleeping"] is True:
        prompt = "You are sleeping. Wanna wake up?"
    else:
        prompt = "You are awake. Wanna sleep?"
    if Confirm.ask(prompt, default=False):
        sleep(stat)
    else:
        print(f"[b]OK :cherry_blossom:")


def sleep(stat):
    """toggle sleep"""

    if stat["sleeping"] is True:
        requests.post(BASEURL + "user/sleep", headers=HEADERS)
        print("Woke up!")
    else:
        requests.post(BASEURL + "user/sleep", headers=HEADERS)
        print("Sing me to sleep:notes:")


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
