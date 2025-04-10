from typing import Any, Dict

from basis import api_request as habitica_api
from heart.__common import __convert_date
from heart.__common.__save_file import save_file
from heart.basis import __get_data as get
from processors.process_task import process_tasks


def get_user_stats(
    stats_data: Dict[str, Any] = None, processed_tasks: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Retrieve user statistics from Habitica API and generate task statistics.

    This function processes user stats and task data, converting it into a
    structured format with additional statistics, and ensures all data is
    handled securely.

    Args:
        stats (dict): The dictionary containing raw user stats from Habitica.
        processed_tasks (dict): The dictionary containing processed task data.

    Returns:
        dict: A dictionary containing user statistics and task statistics.
    """
    try:
        stats = stats_data if stats_data else get.stats()
        processed_tasks = processed_tasks if processed_tasks else process_tasks()

        if not stats or not processed_tasks:
            raise ValueError("Missing required stats or processed tasks data.")

        # Convert class name "wizard" to "mage" (Mage is a subclass of Wizard)
        user_class = stats["stats"]["class"]
        if user_class == "wizard":
            user_class = "mage"

        # Convert last login time to local time
        last_login = stats["auth"]["timestamps"]["loggedin"]
        last_login_local = __convert_date.convert_to_local_time(last_login)

        # Generate task statistics
        task_numbers = {}
        for category, tasks in processed_tasks.get("cats", {}).get("tasks", {}).items():
            if isinstance(tasks, dict):
                task_numbers[category] = {
                    status: len(tasks[status]) for status in tasks
                }
            else:
                task_numbers[category] = len(tasks)

        # Count broken challenges
        broken_challenges = processed_tasks.get("broken", [])
        broken_challenges_count = len(broken_challenges)

        # Prepare user statistics dictionary
        user_stats = {
            "class": user_class,
            "level": stats["stats"]["lvl"],
            "quest": stats["party"]["quest"],
            "sleeping": stats["preferences"]["sleep"],
            "start": stats["preferences"]["dayStart"],
            "stats": stats["stats"],
            "time": str(last_login_local),
            "username": stats["auth"]["local"]["username"],
            "numbers": task_numbers,
            "broken": broken_challenges_count,
        }
        save_file(user_stats, "user_stats.json")
        return user_stats

    except Exception as e:
        print(f"Error in get_user_stats: {e}")
        return {}
