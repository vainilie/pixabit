"""Fech data from Habitica API."""

import asyncio

import httpx
from heart.__common.__convert_date import get_actual_date
from heart.basis.auth_keys import get_api_token, get_user_id

BASEURL = "https://habitica.com/api/v3/"
USER_ID = get_user_id()
API_TOKEN = get_api_token()

HEADERS = {
    "x-api-user": USER_ID,
    "x-api-key": API_TOKEN,
    "Content-Type": "application/json",
}


async def get_user_stats():
    """Fetch user stats from Habitica API."""

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASEURL}user", headers=HEADERS)
        response.raise_for_status()  # Raise an error for non-200 status codes

        stats_json = response.json()["data"]["stats"]
        stats_json["party"] = response.json()["data"]["party"]
        stats_json["timestamp"] = get_actual_date()
        stats_json["sleep"] = response.json()["data"]["preferences"]["sleep"]
        return stats_json


async def get_challenges():
    """Fetch all challenges where the user is a member."""

    async with httpx.AsyncClient() as client:
        counter = 0
        all_challenges = []

        while True:
            response = await client.get(
                f"{BASEURL}challenges/user?member=true&page={counter}",
                headers=HEADERS,
            )
            response.raise_for_status()
            challenge_data = response.json()["data"]

            if not challenge_data:
                break

            all_challenges.extend(challenge_data)
            counter += 1

        return all_challenges


async def get_tags():
    """Fetch all user-defined tags."""

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASEURL}tags", headers=HEADERS)
        response.raise_for_status()
        tags = response.json()["data"]

        return tags


async def get_tasks():
    """Fetch all tasks for the user."""

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASEURL}tasks/user", headers=HEADERS)
        response.raise_for_status()
        tasks = response.json()["data"]

        # Process and sort tasks
        # for task in tasks:
        #     task["text"] = emoji_data_python.replace_colons(task["text"])
        #        sorted_tasks = sorted(tasks, key=lambda x: x["text"].lower())

        return tasks


async def get_user_data():
    """Fetch user data."""

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASEURL}user", headers=HEADERS)
        response.raise_for_status()
        user_data = response.json()["data"]

        return user_data


# Example usage:
async def main():

    stats = await get_user_stats()
    print("User Stats and Party:", stats)

    challenges = await get_challenges()
    print("Challenges:", challenges)

    tags = await get_tags()
    print("Tags:", tags)

    tasks = await get_tasks()
    print("Tasks:", tasks)

    user_data = await get_user_data()
    print("User Data:", user_data)


async def toggle_sleep_status():
    """Fetch user data."""

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASEURL}user/sleep", headers=HEADERS)
        response.raise_for_status()
        user_data = response.json()

        return user_data


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
