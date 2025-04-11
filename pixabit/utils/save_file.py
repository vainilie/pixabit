# Inside pixabit/utils/save_file.py
import json
import os


# Assuming your function looks something like this:
def save_file(data_to_save, base_filename, suffix):
    """Saves data to a JSON file."""  # Or handles other types?
    # Construct the full path - maybe it does this, or maybe full path is passed in
    # Let's assume for now the second argument IS the full filepath like in challenge_backup
    filepath = base_filename  # If the 2nd arg is already the full path

    try:
        dir_name = os.path.dirname(filepath)

        # --- ADD THIS CHECK HERE ---
        if dir_name:  # Only make dirs if a directory path was given
            os.makedirs(dir_name, exist_ok=True)
        # --------------------------

        # Assumes saving as JSON, adjust if it handles other formats
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        # Maybe your original print logic was here or handled differently
        # print(f"Successfully saved data to: {filepath}")

    except Exception as e:
        print(f"Error saving file {filepath}: {e}")
        # Handle or re-raise error as appropriate
