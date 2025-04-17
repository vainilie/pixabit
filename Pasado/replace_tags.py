
#!/usr/bin/env python3

import argparse
import json
import os
import requests
import sys
from collections import Counter
import time


class Debug(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        import pdb; pdb.set_trace()


# MAIN
parser = argparse.ArgumentParser(description="Dumps your tasks to a file user-tasks.json in the current directory")
parser.add_argument('-o', '--outfile',
                    type=argparse.FileType('w'), default="user-tasks.json",
                    help='JSON data file (default: user-tasks.json)')
parser.add_argument('-u', '--user-id',
                    help='From https://habitica.com/
#/options/settings/api\n \
                    default: environment variable HAB_API_USER')
parser.add_argument('-k', '--api-token',
                    help='From https://habitica.com/
#/options/settings/api\n \
                    default: environment variable HAB_API_TOKEN')
parser.add_argument('--baseurl',
                    type=str, default="https://habitica.com",
                    help='API server (default: https://habitica.com)')
parser.add_argument('--debug',
                    action=Debug, nargs=0,
                    help=argparse.SUPPRESS)
parser.add_argument('-d', '--delete-tag',
                    type=str)
parser.add_argument('-a', '--add-tag',
                    type=str)
parser.add_argument('-s', '--second-tag',
                    type=str)
parser.add_argument('-t', '--task-id',
                    type=str)
args = parser.parse_args()
args.baseurl += "/api/v3/"

try:
    if args.user_id is None:
        args.user_id = os.environ['HAB_API_USER']
except KeyError:
    print("User ID must be set by the -u/--user-id option or by setting the environment variable 'HAB_API_USER'")
    sys.exit(1)

try:
    if args.api_token is None:
        args.api_token = os.environ['HAB_API_TOKEN']
except KeyError:
    print("API Token must be set by the -k/--api-token option or by setting the environment variable 'HAB_API_TOKEN'")
    sys.exit(1)

headers = {"x-api-user": args.user_id, "x-api-key": args.api_token, "Content-Type": "application/json"}
req = requests.get(args.baseurl + "tasks/user", headers=headers)

# with open(args.outfile, 'w') as f:

#json.dump(req.json(), args.outfile, separators=(',', ':'), sort_keys=True)
allTasks= req.json()['data']
pTag="0465135b-7652-4aac-8a15-9db5fc9af803"
cTag="48924274-1ba1-49ba-8dc5-48b0ff225d25"
cDelTag = []
cHasTag = []
cTasks = []
cToTag = []
pDelTag = []
pHasTag= []
pTasks = []
pToTag=[]


def DeleteTag(tasks,tag):
    for counter,item in enumerate(tasks, start=1):
        requests.delete(args.baseurl + "tasks/" + item + "/tags/" + tag,  headers=headers)
        time.sleep(60/30)
        print(counter)


def AddTag(tasks,tag):
    for counter2, item in enumerate(tasks, start=1):
        requests.post(args.baseurl + "tasks/" + item + "/tags/" + tag,  headers=headers)
        time.sleep(60/30)
        print(counter2)

def getList(theTasks,tag_e):
    list = []
    for task in theTasks:
        for tag in task['tags']:
            if tag == tag_e:
                list.append(task['id'])
            else:
                continue
    return list


# Python code t get difference of two lists

# Using set()
def Diff(li1, li2):
    return list(set(li1) - set(li2)) + list(set(li2) - set(li1))

def Differ(dict,list):
    newlist=[]
    for item in dict:
        if item['id'] not in list:
            newlist.append(item['id'])
        else:
            continue
    return(newlist)


if args.task_id:
    if args.add_tag:
        print("Adding the tag on the task.")
        requests.post(args.baseurl + "tasks/" + args.task_id + "/tags/" + args.add_tag,  headers=headers)
        print("Done")
    elif args.delete_tag:
        print("Deleting the tag on the task.")
        requests.delete(args.baseurl + "tasks/" + args.task_id + "/tags/" + args.delete_tag,  headers=headers)
        print("Done")
    if args.delete_tag is None and args.add_tag is None:
        print("Add with the -/--add-tag or -d/--delete-tag the tag ID you want to add, delete or both to replace.")

else:
    if args.add_tag and args.delete_tag:
        print("Custom action: replace tags in all tasks")
        changeTags = []
        changeTags = getList(allTasks, args.delete_tag)
        print(f"Replacing tag in {len(changeTags)} tasks.")
        DeleteTag(changeTags,args.delete_tag)
        AddTag(changeTags,args.add_tag)
        print("Done")
    elif args.add_tag and args.second_tag:
        print("Add a second tag")
        secondTags = []
        secondTags = getList(allTasks, args.second_tag)
        print(f"Adding second tag in {len(secondTags)} tasks.")
        AddTag(secondTags,args.add_tag)
        print("Done")
    elif args.add_tag is None and args.delete_tag:
        print("Custom action: delete tag")
        deleteTags = []
        deleteTags = getList(allTasks, args.delete_tag)
        print(f"Deleting tag in {len(deleteTags)} tasks.")
        AddTag(deleteTags,args.delete_tag)
        print("Done")
    elif args.add_tag and args.delete_tag is None:
        print("Add with the  -a/--add-tag or -d/--delete-tag options the tag ID you want to add, delete, or both to replace. Add with -t/--task-id the task ID you want to tag. ")

    elif args.delete_tag is None and args.add_tag is None:
        print("Default action: add a tag to the challenge tasks and the no-challenge tasks")
        for counter1, item in enumerate(allTasks, start=1):
            myTags = item['tags']
            task = {}
            task.update({'id': item['id'], "tags": item['tags']})
            if len(item['challenge']) != 0:
                cTasks.append(task)
            else:
                pTasks.append(task)

        pDelTag=getList(pTasks,cTag)
        pHasTag=getList(pTasks,pTag)
        pToTag=Differ(pTasks,pHasTag)
        cDelTag=getList(cTasks,pTag)
        cHasTag=getList(cTasks,cTag)
        cToTag=Differ(cTasks,cHasTag)

        print(f'TOTAL TASKS: {counter1}')
        print(f'CHALLENGE TASKS: {len(cTasks)} \nWrong tag: {len(cDelTag)}\tGood tag: {len(cHasTag)}\tTo tag: {len(cToTag)}')
        print(f'PERSONAL TASKS: {len(pTasks)} \nWrong tag: {len(pDelTag)}\tGood tag: {len(pHasTag)}\tTo tag: {len(pToTag)}')
        input("Press Enter to continue...")

        print("Adding challenge tag to tasks...")
        AddTag(cToTag,cTag)
        print("Done")
        print("Deleting wrong tag in challenge tags...")
        DeleteTag(cDelTag,pTag)
        print("Done")
        print("Adding personal tag to tasks...")
        AddTag(pToTag,pTag)
        print("Done")
        print("Deleting wrong tag in personal tasks...")
        DeleteTag(pDelTag,cTag)
        print("Done")

