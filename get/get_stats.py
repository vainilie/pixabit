#             _         _        _
#            | |       | |      | |
#   __ _  ___| |_   ___| |_ __ _| |_ ___
#  / _` |/ _ \ __| / __| __/ _` | __/ __|
# | (_| |  __/ |_  \__ \ || (_| | |_\__ \
#  \__, |\___|\__| |___/\__\__,_|\__|___/
#   __/ |
#  |___/


"""
get_stats Module
================

This module provides a function to retrieve user statistics from the Habitica API and
generate task statistics based on the provided tasks dictionary. The user statistics
include information such as the user's class, level, quest status, sleeping preference,
start time, user stats, last login time, and username. The task statistics provide the
count of tasks for each category and status.

The module uses the "habitica_api" module to interact with the Habitica API for fetching
user data. It also relies on the "convert_date" module to convert the last login time to
the local time zone and the "save_file" module to save the generated user statistics.

Usage:
------

To use this module, you need to provide a tasks dictionary, which contains task data.
The function "get_user_stats" takes the tasks dictionary as input and returns a
dictionary containing user statistics and task statistics.

Example:
--------

import get_stats

# Assuming tasks_dict contains the data of all user tasks
user_stats = get_stats.get_user_stats(tasks_dict)
print(user_stats)
"""

from core import habitica_api
from utils import convert_date
from core import save_file


def get_user_stats(tasks_dict):
    """
    Retrieve user statistics from Habitica API and generate task statistics.

    This function makes a request to the Habitica API to get user statistics
    and generates statistics for the tasks in the provided tasks_dict.
    It then saves the user statistics to a file named "user_stats.json".

    Args:
        tasks_dict (dict): The dictionary containing task data.

    Returns:
        dict: A dictionary containing user statistics and task statistics.
              The structure of the returned dictionary is:
              {
                  "class": class_name,
                  "level": user_level,
                  "quest": party_quest,
                  "sleeping": sleep_status,
                  "start": day_start,
                  "stats": user_stats,
                  "time": last_login_time,
                  "username": username,
                  "numbers": task_numbers,
                  "broken": broken_challenges_count,
              }
    """
    # Get user statistics from Habitica API
    response = habitica_api.get("user?userFields=stats,party")
    raw_data = response["data"]

    # Convert class name "wizard" to "mage" (Mage is a subclass of Wizard)
    if raw_data["stats"]["class"] == "wizard":
        raw_data["stats"]["class"] = "mage"

    # Convert last login time to local time
    last_login = raw_data["auth"]["timestamps"]["loggedin"]
    last_login = convert_date.convert_to_local_time(last_login)

    # Generate task statistics
    numbers = {}
    for category in tasks_dict["tasks"]:
        if isinstance(tasks_dict["tasks"][category], dict):
            numbers[category] = {
                status: len(tasks_dict["tasks"][category][status])
                for status in tasks_dict["tasks"][category]
            }
        else:
            numbers[category] = len(tasks_dict["tasks"][category])

    # Prepare user statistics dictionary
    user_stats = {
        "class": raw_data["stats"]["class"],
        "level": raw_data["stats"]["lvl"],
        "quest": raw_data["party"]["quest"],
        "sleeping": raw_data["preferences"]["sleep"],
        "start": raw_data["preferences"]["dayStart"],
        "stats": raw_data["stats"],
        "time": str(last_login),
        "username": raw_data["auth"]["local"]["username"],
        "numbers": numbers,
        "broken": len(tasks_dict["broken"]),
    }

    # Save user statistics to file
    save_file.save_file(user_stats, "user_stats", "_json")

    return user_stats
