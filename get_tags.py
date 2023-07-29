import habitica_api
from save_file import save_file
import emoji_data_python
from typing import Dict, List


def get_tags() -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch tags from the Habitica API, process them, and save the data to a JSON file.

    Returns:
        dict: A dictionary containing processed tags data with
        'challengeTags' and 'personalTags' keys.
    """

    all_tags = habitica_api.get("tags")
    processed_tags_data = {
        "challengeTags": [],
        "personalTags": [],
    }

    for tag in all_tags["data"]:
        processed_tag = {}
        name = emoji_data_python.replace_colons(tag["name"].replace("target", "dart"))
        processed_tag.update({"id": tag["id"], "name": name})
        if "challenge" in tag:
            processed_tags_data["challengeTags"].append(processed_tag)
        else:
            processed_tags_data["personalTags"].append(processed_tag)

    processed_tags_data["challengeTags"].sort(key=lambda x: x["name"].lower())
    processed_tags_data["personalTags"].sort(key=lambda x: x["name"].lower())

    save_file(processed_tags_data, "all_tags")
    return processed_tags_data