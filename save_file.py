import json


def save_file(data, title):
    """
    Save JSON data to a file.

    Args:
        data (dict or list): The JSON data to be saved.
        filename (str): The name of the file to save the JSON data to.
    """
    with open(title + ".json", "w", encoding="utf-8") as outfile:
        json.dump(
            data,
            outfile,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            indent=3,
        )
