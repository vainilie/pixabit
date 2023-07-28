import configparser
import os.path

DEFAULT_CONFIG_FILE = "auth.ini"


def create_auth_file(filename=DEFAULT_CONFIG_FILE):
    """
    Create the auth.ini file with default credentials for Habitica and tags.

    This function creates the auth.ini file if it doesn't exist and sets
    default credentials for the "habitica" section and "tags" section.

    Args:
        filename (str): The name of the configuration file to create.
    """
    config = configparser.ConfigParser()
    config["habitica"] = {
        "user": "YOUR_HABITICA_USER_ID_HERE",
        "token": "YOUR_API_TOKEN_HERE",
    }
    config["tags"] = {
        "challenge": "YOUR_CHALLENGE_TAG_ID_HERE",
        "owned": "YOUR_OWNED_TAG_ID_HERE",
    }

    with open(filename, "w") as configfile:
        config.write(configfile)


def get_key_from_config(section, key, filename=DEFAULT_CONFIG_FILE):
    """
    Get the value of a specific key from the auth.ini file.

    This function retrieves the value of a specific key from the auth.ini file.

    Args:
        section (str): The section name in the auth.ini file.
        key (str): The key name to get the value for in the specified section.
        filename (str): The name of the configuration file to read.

    Returns:
        str: The value of the specified key in the given section.
    """
    config = configparser.ConfigParser()
    config.read(filename)
    return config[section][key]


def check_auth_file(filename=DEFAULT_CONFIG_FILE):
    """
    Check if the auth.ini file exists. If not, create it with default credentials.

    This function checks if the auth.ini file exists in the specified directory.
    If the file doesn't exist, it calls the create_auth_file() function
    to create it with default credentials.

    Args:
        filename (str): The name of the configuration file to check/create.
    """
    if not os.path.exists(filename):
        create_auth_file(filename)
        print(f"{filename} file created")
    else:
        print("File exists")
