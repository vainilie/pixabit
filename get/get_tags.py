"""
get_tags Module
===============

This module provides a function to fetch tags from the Habitica API, process them,
and save the data to a JSON file. The processed tags data is organized into
'challenge_tags' and 'personal_tags' keys in a dictionary.

Usage:
------
Call the `get_tags()` function to fetch tags from the Habitica API, process them,
sort them alphabetically, and save the data to a JSON file named "all_tags.json".

Example:
--------
import get_tags

# Fetch and process tags from the Habitica API
tags_data = get_tags.get_tags()

# Access the processed tags data
challenge_tags = tags_data["challenge_tags"]
personal_tags = tags_data["personal_tags"]
"""


from core import habitica_api
from core.save_file import save_file
from typing import Dict, List
import emoji_data_python


def get_tags() -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch tags from the Habitica API, process them, and save the data to a JSON file.

    Returns:
        Dict[str, List[Dict[str, str]]]: A dictionary containing processed tags data
        with 'challenge_tags' and 'personal_tags' keys.
    """

    all_tags = habitica_api.get("tags")
    processed_tags_data = {
        "challenge_tags": [],
        "personal_tags": [],
    }

    for tag in all_tags["data"]:
        processed_tag = {}
        name = emoji_data_python.replace_colons(tag["name"].replace("target", "dart"))
        processed_tag.update({"id": tag["id"], "name": name})
        if "challenge" in tag:
            processed_tags_data["challenge_tags"].append(processed_tag)
        else:
            processed_tags_data["personal_tags"].append(processed_tag)

    processed_tags_data["challenge_tags"].sort(key=lambda x: x["name"].lower())
    processed_tags_data["personal_tags"].sort(key=lambda x: x["name"].lower())

    save_file(processed_tags_data, "all_tags", "_json")
    return processed_tags_data
