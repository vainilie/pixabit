#              _   _        __ _ _
#             | | | |      / _(_) |
#   __ _ _   _| |_| |__   | |_ _| | ___
#  / _` | | | | __| '_ \  |  _| | |/ _ \
# | (_| | |_| | |_| | | | | | | | |  __/
#  \__,_|\__,_|\__|_| |_| |_| |_|_|\___|


"""
auth_file Module
================

This module provides functions to create and access the authentication
configuration file for Habitica API. The configuration file contains the
user ID, API token, and other settings needed for authentication with the
Habitica API.

Usage:
------
1. Creating the authentication configuration file:
    The `create_auth_file` function allows users to interactively create
    the authentication configuration file. It prompts the user to enter their
    Habitica user ID and API token, or it provides default values that can
    be edited later.

2. Reading values from the authentication configuration file:
    The `get_key_from_config` function is used to retrieve specific values
    from the authentication configuration file. Users can use this function
    to access their user ID, API token, or other settings stored in the file.

Example:
--------
import auth_file

# Create the authentication configuration file
auth_file.create_auth_file()

# Access the user ID and API token from the configuration file
user_id = auth_file.get_key_from_config("habitica", "user")
api_token = auth_file.get_key_from_config("habitica", "token")
"""

import configparser
import os.path
from heart.TUI.rich_utils import Confirm, Prompt, print
from rich import print as rprint, Confirm, Prompt

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
    config["challenge_tags"] = {
        "challenge": "YOUR_CHALLENGE_TAG_ID_HERE",
        "owned": "YOUR_OWNED_TAG_ID_HERE",
    }

    config["attributes_tags"] = {
        "STR": "YOUR_STRENGTH_TAG_ID_HERE",
        "INT": "YOUR_INTELLIGENCE_TAG_ID_HERE",
        "CON": "YOUR_CONSTITUTION_TAG_ID_HERE",
        "PER": "YOUR_PERCEPTION_TAG_ID_HERE",
        "NOT_ATR": "YOUR_NO_ATTRIBUTE_TAG_ID_HERE",
    }

    with open(filename, "w", encoding="utf-8") as configfile:
        config.write(configfile)
        print(f" [b #8ccf7e]:heavy_check_mark: {filename}[/] created.")


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
    try:
        return config[section][key]
    except KeyError as exc:
        raise KeyError(
            f"Key '{key}' not found in section '{section}' in the file {filename}"
        ) from exc


def check_auth_file(filename=DEFAULT_CONFIG_FILE):
    """
    Check if the authentication configuration file exists and create it if missing.

    Args:
        filename (str, optional): The name of the configuration file.
            Defaults to "auth.ini".
    """
    print(f"[b #8ccf7e]Checking if {filename}[/] exists...")

    if not os.path.exists(filename):
        print(f":x: [b]{filename}[/] doesn't exist.")
        create_auth_file(filename)
    else:
        print(f"[b #8ccf7e]:heavy_check_mark: {filename}[/] file exists.")


def create_tags_file(filename=DEFAULT_CONFIG_FILE):
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

    with open(filename, "w", encoding="utf-8") as configfile:
        config.write(configfile)
        print(f" [b #8ccf7e]:heavy_check_mark: {filename}[/] created.")
