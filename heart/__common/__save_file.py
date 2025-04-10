# ?                         __ _ _
# ?  ___  __ ___   _____   / _(_) | ___
# ? / __|/ _` \ \ / / _ \ | |_| | |/ _ \
# ? \__ \ (_| |\ V /  __/ |  _| | |  __/
# ? |___/\__,_| \_/ \___| |_| |_|_|\___|
# ?
# ?                   vainilie, 23/08/03

"""
core.savefile Module -
This module provides a function to save JSON data to a file.

Functions:
    save_file(data, title, folder=None)
        Save JSON data to a file.
"""

import json
import os

# % ─── save_file ───────────────────────────────────────────────────────────── ✰ ─


def save_json(data, title, folder_data=None):
    """
    Save JSON data to a file.

    Args:
        data (dict or list): The JSON data to be saved.
        title (str): The name of the file to save the JSON data to (without the ext).
        folder (str, optional): The folder path where the file should be saved.
            Defaults to the current working directory if not specified.

    Note:
        If the `folder` argument is provided, the function will create the folder
        (if it doesn't exist) and save the file in that folder. If `folder` is None,
        the file will be saved in the current working directory.

    Example:
        data = {"name": "John Doe", "age": 30}
        save_file(data, "data", folder="data_files")

    Example:
        data = {"name": "Jane Smith", "age": 25}
        save_file(data, "data")
    """
    folder = folder_data if folder_data else "data"
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, title + ".json")

    with open(filepath, "w", encoding="utf-8") as outfile:
        json.dump(
            data,
            outfile,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            indent=3,
        )
