import habitica_api
import save_file


def save_all_user_data():
    """
    Retrieve all user data from Habitica API and save it to a file.

    This function makes a request to the Habitica API to get all user data
    and then saves the retrieved data to a file named "all_user_data.json".

    Example:
        save_all_user_data()
    """
    user_data = habitica_api.get("user")
    user_challenges = habitica_api.get("challenges/user?page=1")
    save_file.save_file(user_data, "all_user_data")
    save_file.save_file(user_challenges, "challenges")

