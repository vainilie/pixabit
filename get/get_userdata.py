"""
user_data_manager.py - Module for managing user data from the Habitica API.

This module interacts with the Habitica API to retrieve all user data, including
user details, tasks, and other information. It provides a function to save the
retrieved data to a file named "all_user_data.json" using the save_file module.

Functions:
    save_all_user_data():
        Retrieve all user data from Habitica API and save it to a file.

Note:
    The user data includes sensitive information such as API keys and should be
    handled and stored securely.

Example:
    save_all_user_data()

Raises:
    requests.exceptions.RequestException:
        If there is an error in the API response or the API is unavailable.
"""


# user_data_manager.py
from core import habitica_api, save_file


def save_all_user_data():
    """
    Retrieve all user data from Habitica API and save it to a file.

    This function makes a request to the Habitica API to get all user data,
    including user details, tasks, and other information. It then saves the
    retrieved data to a file named "all_user_data.json" using the save_file
    module.

    Note:
        The user data includes sensitive information such as API keys and should
        be handled and stored securely.

    Example:
        save_all_user_data()

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    user_data = habitica_api.get("user")
    save_file.save_file(user_data, "all_user_data", "_json")
