"""
unused_tags.py - Module for managing unused tags in Habitica.

This module provides functions to handle unused tags in the Habitica app. It allows
users to retrieve all unused tags and delete them from the Habitica API. The module
contains two main functions: `get_unused_tags` and `delete_unused_tags`.

The `get_unused_tags` function takes a dictionary `tags` containing tag data categorized
by type, and a set `used_tags` containing tag IDs that are already in use. It finds all
tag IDs from the given `tags` dictionary that are not present in the `used_tags` set and
returns a list of dictionaries representing the unused tags. Each dictionary contains
information about the tag name, category, and ID.
The `delete_unused_tags` function takes a list of dictionaries representing unused tags
and deletes them from the Habitica API. Each dictionary in the list must have an "id"
field to specify the tag ID to be deleted.

Example:
    tags_data = {
        "habits": [{"id": "tag1", "name": "Tag1"}, {"id": "tag2", "name": "Tag2"}],
        "todos": [{"id": "tag3", "name": "Tag3"}],
        "dailys": [{"id": "tag4", "name": "Tag4"}, {"id": "tag5", "name": "Tag5"}],
    }
    used_tags = {"tag1", "tag3"}
    unused_tags = get_unused_tags(tags_data, used_tags)
    print(unused_tags)
    # Output: [
    #     {"name": "Tag2", "category": "habits", "id": "tag2"},
    #     {"name": "Tag4", "category": "dailys", "id": "tag4"},
    #     {"name": "Tag5", "category": "dailys", "id": "tag5"}
    # ]
    Note:
    - The user should ensure that the `tags` dictionary and `used_tags` set are
      correctly formatted to avoid any errors.
    - The `delete_unused_tags` function requires the Habitica API to be accessible
      and the user to have proper authentication and authorization.
"""

from typing import Dict, List, Set
from basis import api_method
from rich.progress import track
from processors import process_tags, process_task

def get_unused_tags(
    tags_data: Dict[str, List[Dict[str, str]]]=None, 
    used_tags_data: Set[str]=None
) -> List[Dict[str, str]]:
    """
    Get a list of dictionaries representing all unused tags.

    This function takes a dictionary `tags` containing tag data categorized by type,
    and a set `used_tags` containing tag IDs that are already in use. It finds all
    tag IDs from the given `tags` dictionary and returns a list of dictionaries,
    where each dictionary represents an unused tag.

    Args:
        tags (dict): A dictionary containing tag data categorized by type.
        used_tags (set): A set of used tag IDs.

    Returns:
        list: A list of dictionaries representing all unused tags.
            Each dict contains the "name", "category", and "id" of an unused tag.

    Example:
        tags_data = {
            "habits": [{"id": "tag1", "name": "Tag1"}, {"id": "tag2", "name": "Tag2"}],
            "todos": [{"id": "tag3", "name": "Tag3"}],
            "dailys": [{"id": "tag4", "name": "Tag4"}, {"id": "tag5", "name": "Tag5"}],
        }
        used_tags = {"tag1", "tag3"}
        unused_tags = get_unused_tags(tags_data, used_tags)
        print(unused_tags)
        # Output: [
        #     {"name": "Tag2", "category": "habits", "id": "tag2"},
        #     {"name": "Tag4", "category": "dailys", "id": "tag4"},
        #     {"name": "Tag5", "category": "dailys", "id": "tag5"}
        # ]

    Note:
        The user should ensure that the `tags` dictionary and `used_tags` set are
        correctly formatted to avoid any errors.

    """
    tags = tags_data if tags_data is not None else process_tags.get_tags() 
    used_tags = used_tags_data if used_tags_data is not None else process_task.process_tasks()["data"]["tags"]
    unused_tags_list = []
    for category, tag_list in tags.items():
        for tag in tag_list:
            if tag["id"] not in used_tags:
                unused_tags_list.append(
                    {"name": tag["name"], "category": category, "id": tag["id"]}
                )
    return unused_tags_list


def delete_unused_tags(unused_tags_data: List[Dict[str, str]] =None) -> None:
    """
    Delete all unused tags from Habitica.

    This function takes a list of dictionaries representing unused tags and deletes
    them from the Habitica API. Each dictionary in the list must have "id" to specify
    the tag ID to be deleted.

    Args:
        unused_tags (list): A list of dictionaries representing unused tags.

    Returns:
        None

    Example:
        unused_tags = [
            {"name": "Tag2", "category": "habits", "id": "tag2"},
            {"name": "Tag4", "category": "dailys", "id": "tag4"},
            {"name": "Tag5", "category": "dailys", "id": "tag5"}
        ]
        delete_unused_tags(unused_tags)

    Note:
        This function requires the Habitica API to be accessible and the user to
        have proper authentication and authorization.

    """
    unused_tags = unused_tags_data if unused_tags_data is not None else get_unused_tags() 

    for unused_tag in track(unused_tags, description="Deleting empty tags..."):
        tag_id = unused_tag["id"]
        api_method.delete(f"tags/{tag_id}")
