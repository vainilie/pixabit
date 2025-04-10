from typing import Dict, List

import emoji_data_python
from heart.basis.__get_data import get_tags


async def process_tags(tags_data=None) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch tags from the Habitica API, process them, and return processed data.

    Args:
        tags_data (list, optional): Pre-fetched list of tags. Defaults to None.

    Returns:
        Dict[str, List[Dict[str, str]]]: A dictionary containing processed tags data
        with 'challenge_tags' and 'personal_tags' keys.
    """
    # Fetch tags if not provided
    tags = tags_data if tags_data else await get_tags()

    if not tags:
        raise ValueError("No tags data found.")

    processed_tags_data = {
        "challenge_tags": [],
        "personal_tags": [],
    }

    # Process each tag
    for tag in tags:
        processed_tag = {}
        name = emoji_data_python.replace_colons(tag["name"].replace("target", "dart"))
        processed_tag.update({"id": tag["id"], "name": name})

        if "challenge" in tag:
            processed_tags_data["challenge_tags"].append(processed_tag)
        else:
            processed_tags_data["personal_tags"].append(processed_tag)

    # Sort tags
    processed_tags_data["challenge_tags"].sort(key=lambda x: x["name"].lower())
    processed_tags_data["personal_tags"].sort(key=lambda x: x["name"].lower())

    return processed_tags_data
