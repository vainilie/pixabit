from heart.basis.auth_file import get_key_from_config, create_auth_file


def get_user_id():
    """
    Retrieve the user ID from the configuration or generate a default ID.

    Returns:
        str: The user ID.
    """
    try:
        return get_key_from_config("habitica", "user")
    except KeyError:
        print("Error: User ID not found in configuration file.")
        create_auth_file()
        return "DEFAULT_USER_ID"


def get_api_token():
    """
    Retrieve the API token from the configuration or generate a default token.

    Returns:
        str: The API token.
    """
    try:
        return get_key_from_config("habitica", "token")
    except KeyError:
        print("Error: API token not found in configuration file.")
        create_auth_file()
        return "DEFAULT_API_TOKEN"
