from core import habitica_api, save_file
import time


def get_my_challenges():
    """
    Get a list of all challenges associated with the user.

    This function retrieves all challenges associated with the user's account from
    Habitica using paginated requests. The retrieved challenge data is saved to a JSON
    file named "my_challenges.json" using the save_file module.

    Returns:
        list: A list containing dictionaries representing user's challenges.

    Example:
        challenges = get_my_challenges()
        print(challenges)
    """
    counter = 0
    all_challenges = []

    while True:
        challenge_data = habitica_api.get(
            f"challenges/user?page={counter}&member=true"
        )["data"]

        if not challenge_data:
            break

        all_challenges.extend(challenge_data)
        counter += 1
        time.sleep(60 / 30)  # Delay to avoid overloading the API

    save_file.save_file(all_challenges, "my_challenges", "_json")
    return all_challenges
