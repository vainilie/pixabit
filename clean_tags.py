from typing import Dict, List, Set


def get_unused_tags(
    tags: Dict[str, List[Dict[str, str]]], used_tags: Set[str]
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
    """
    unused_tags_list = []
    for category, tag_list in tags.items():
        for tag in tag_list:
            if tag["id"] not in used_tags:
                unused_tags_list.append(
                    {"name": tag["name"], "category": category, "id": tag["id"]}
                )
    return unused_tags_list