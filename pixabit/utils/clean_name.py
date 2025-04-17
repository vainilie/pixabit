# pixabit/utils/clean_name.py

# MARK: - MODULE DOCSTRING
"""Provides utility functions for cleaning filenames by replacing characters
that are illegal in many file systems, typically using full-width Unicode
variants or underscores.
"""


# MARK: - IMPORTS
import re

# MARK: - CONSTANTS
CHARACTER_TRANSLATION_TABLE = str.maketrans(
    '"*/:<>?\\|\t\n\v\f\r',
    # Illegal characters + whitespace variants
    "＂＊／：＜＞？＼￨     ",
    # Replacements (full-width + spaces)
)
LEADING_SPACE_PATTERN = re.compile(r"^\s+")


# MARK: - FUNCTIONS


# & - def replace_illegal_filename_characters(input_filename: str) -> str:
def replace_illegal_filename_characters(input_filename: str) -> str:
    r"""Replaces illegal filename characters with full-width variants."""
    return input_filename.translate(CHARACTER_TRANSLATION_TABLE).strip()


# Also strip leading/trailing whitespace


# & - def replace_illegal_filename_characters_leading_underscores(input_filename: str) -> str:
def replace_illegal_filename_characters_leading_underscores(input_filename: str) -> str:
    r"""Replaces illegal chars; replaces leading whitespace with underscores."""
    output_filename = input_filename.translate(CHARACTER_TRANSLATION_TABLE)

    # Replace any sequence of leading spaces with the same number of underscores
    output_filename = re.sub(
        LEADING_SPACE_PATTERN, lambda match: "_" * len(match.group(0)), output_filename
    )
    return output_filename.strip()


# Strip trailing whitespace


# & - def replace_illegal_filename_characters_prefix_underscore(input_filename: str) -> str:
def replace_illegal_filename_characters_prefix_underscore(input_filename: str) -> str:
    r"""Replaces illegal chars; adds '_' prefix if original started with space."""
    output_filename = input_filename.translate(CHARACTER_TRANSLATION_TABLE)

    # Check the *original* string for leading space before adding prefix
    result = (
        "_" + output_filename if input_filename.lstrip() != input_filename else output_filename
    )
    return result.strip()


# Strip trailing whitespace


# MARK: - EXAMPLE USAGE (Commented out for library use)

# if __name__ == "__main__":

#
# ... (example usage from clean_name_v2.txt) ...
