import habitica_api
from tzlocal import get_localzone
import dateutil.parser
import save_file


def convert_to_local_time(utc):
    """
    Convert UTC time to local timezone.

    Args:
        utc (str): UTC timestamp to be converted.

    Returns:
        datetime: The converted datetime object in the local timezone.
    """
    utc_time = dateutil.parser.parse(utc)
    local_timezone = get_localzone()
    return utc_time.astimezone(local_timezone).replace(microsecond=0)


def get_stats(tasks_dict):
    """
    Get user statistics from the Habitica API and save them to a file.

    Returns:
        dict: A dictionary containing the user statistics.
    """
    response = habitica_api.get("user?userFields=stats,party")
    raw_data = response["data"]

    while raw_data["stats"]["class"] == "wizard":
        raw_data["stats"]["class"] = "mage"

    last_login = raw_data["auth"]["timestamps"]["loggedin"]
    last_login = convert_to_local_time(last_login)

    stats = {
        "class": raw_data["stats"]["class"],
        "level": raw_data["stats"]["lvl"],
        "quest": raw_data["party"]["quest"],
        "sleeping": raw_data["preferences"]["sleep"],
        "start": raw_data["preferences"]["dayStart"],
        "stats": raw_data["stats"],
        "time": str(last_login),
        "username": raw_data["auth"]["local"]["username"],
        "numbers": tasks_dict["counts"],
    }

    save_file.save_file(stats, "Stats")

    return stats


# This part is left unchanged as it appears to be the main entry point of the script.
# It calls the `get_stats()` function to fetch and save user statistics.
if __name__ == "__main__":
    user_stats = get_stats()
    # Do something with the user_stats dictionary if needed.
