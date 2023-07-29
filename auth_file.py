import configparser
import os.path
from rich import print
from rich.prompt import Confirm, Prompt

DEFAULT_CONFIG_FILE = "auth.ini"


def create_auth_file(filename=DEFAULT_CONFIG_FILE):
    """
    Create an authentication configuration file for Habitica API.

    Args:
        filename (str, optional): The name of the configuration file.
        Defaults to "auth.ini".
    """
    if Confirm.ask("Should I help you create the file?"):
        input_userid = Prompt.ask(
            "Enter your [b]Habitica user id[/]", default="YOUR_HABITICA_USER_ID_HERE"
        )
        input_apitoken = Prompt.ask(
            "Enter your [b]API token[/]", default="YOUR_API_TOKEN_HERE"
        )
    else:
        input_userid = "YOUR_HABITICA_USER_ID_HERE"
        input_apitoken = "YOUR_API_TOKEN_HERE"

    config = configparser.ConfigParser()
    config["habitica"] = {
        "user": input_userid,
        "token": input_apitoken,
    }
    config["tags"] = {
        "challenge": "YOUR_CHALLENGE_TAG_ID_HERE",
        "owned": "YOUR_OWNED_TAG_ID_HERE",
    }

    with open(filename, "w") as configfile:
        config.write(configfile)
        print(f":heavy_check_mark: [b]{filename}[/] created.")
    exit()


def get_key_from_config(section, key, filename=DEFAULT_CONFIG_FILE):
    """
    Get a specific key value from the authentication configuration file.

    Args:
        section (str): The section name in the configuration file.
        key (str): The key to retrieve the value for.
        filename (str, optional): The name of the configuration file.
        Defaults to "auth.ini".

    Returns:
        str: The value associated with the specified key in the given section.
    """
    config = configparser.ConfigParser()
    config.read(filename)
    return config[section][key]


def check_auth_file(filename=DEFAULT_CONFIG_FILE):
    """
    Check if the authentication configuration file exists and create it if missing.

    Args:
        filename (str, optional): The name of the configuration file.
        Defaults to "auth.ini".
    """
    print(f"[b]Checking if {filename}[/] exists...")

    if not os.path.exists(filename):
        print(f":x: [b]{filename}[/] doesn't exist.")
        create_auth_file(filename)
    else:
        print(f":heavy_check_mark: [b]{filename}[/] file exists.")
