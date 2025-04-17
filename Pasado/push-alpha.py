
#!/usr/bin/env python3

import argparse
import os
import requests
import time
import six
import sys
import emoji_data_python

class Debug(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        import pdb

        pdb.set_trace()



# MAIN
parser = argparse.ArgumentParser(
    description="Moves active tasks with duedates to the top of the To-Dos list in order of duedate"
)
group = parser.add_mutually_exclusive_group()
group.add_argument(
    "-t",
    "--today",
    action="store_true",
    default=False,
    help="send only today's todos to the top",
)
parser.add_argument(
    "-f",
    "--future",
    action="store_true",
    default=False,
    help="include todos with future due dates",
)
parser.add_argument(
    "-u",
    "--user-id",
    help="From https://habitica.com/
#/options/settings/api\n \
                    default: environment variable HAB_API_USER",
)
parser.add_argument(
    "-k",
    "--api-token",
    help="From https://habitica.com/
#/options/settings/api\n \
                    default: environment variable HAB_API_TOKEN",
)
parser.add_argument(
    "--baseurl",
    type=str,
    default="https://habitica.com",
    help="API server (default: https://habitica.com)",
)
parser.add_argument("--debug", action=Debug, nargs=0, help=argparse.SUPPRESS)
args = parser.parse_args()
args.baseurl += "/api/v3/"

try:
    if args.user_id is None:
        args.user_id = os.environ["HAB_API_USER"]
except KeyError:
    print(
        "User ID must be set by the -u/--user-id option or by setting the environment variable 'HAB_API_USER'"
    )
    sys.exit(1)

try:
    if args.api_token is None:
        args.api_token = os.environ["HAB_API_TOKEN"]
except KeyError:
    print(
        "API Token must be set by the -k/--api-token option or by setting the environment variable 'HAB_API_TOKEN'"
    )
    sys.exit(1)


headers = {
    "x-api-user": args.user_id,
    "x-api-key": args.api_token,
    "Content-Type": "application/json",
}

today = six.text_type(time.strftime("%Y-%m-%d"))
todos_with_duedates = []

req = requests.get(args.baseurl + "tasks/user", headers=headers)

infor = req.json()["data"]
tasks = []
for task in infor:
    item = {}
    item.update({"id": task["id"], "title": task["text"], "tag": task["tags"]})
    tasks.append(item)


def sortFunction(value):
    return value["title"].lower()


sortedtasks = sorted(tasks, key=sortFunction)

# print(sortedtasks)

# Push todos_with_duedates to the top
for count, tasq in enumerate(sortedtasks):
    requests.post(args.baseurl + "tasks/" + tasq["id"] + "/move/to/-1", headers=headers)
    print(count)
    time.sleep(60 / 30)
