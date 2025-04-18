# pixabit/utils/clean_name.py

# SECTION: MODULE DOCSTRING
"""Provides utility functions for cleaning filenames.

Replaces characters that are illegal in many file systems, typically using
full-width Unicode variants or underscores, and handles leading whitespace.
"""

# SECTION: IMPORTS
import re
from re import Pattern  # Import Pattern for compiled regex type hint

# SECTION: CONSTANTS
# Translation table for illegal characters -> full-width variants/space
CHARACTER_TRANSLATION_TABLE = str.maketrans(
    '"\\*/:<>?\\|\t\n\v\f\r',  # Illegal characters + whitespace variants
    "＂＊／：＜＞？＼￨ ",  # Replacements (full-width + spaces)
)
# Compiled regex pattern to find one or more leading whitespace characters
LEADING_SPACE_PATTERN: Pattern[str] = re.compile(r"^\s+")


# SECTION: FUNCTIONS


# FUNC: replace_illegal_filename_characters
def replace_illegal_filename_characters(input_filename: str) -> str:
    """Replaces illegal filename characters with full-width Unicode variants or spaces.

    Also strips leading/trailing whitespace from the result.

    Args:
        input_filename: The original filename string.

    Returns:
        The cleaned filename string.
    """
    return input_filename.translate(CHARACTER_TRANSLATION_TABLE).strip()


# FUNC: replace_illegal_filename_characters_leading_underscores
def replace_illegal_filename_characters_leading_underscores(
    input_filename: str,
) -> str:
    """Replaces illegal characters and converts leading whitespace to underscores.

    Illegal characters are replaced using `CHARACTER_TRANSLATION_TABLE`. Any
    sequence of leading whitespace characters in the *original* string is
    replaced by the same number of underscore characters. Strips trailing
    whitespace from the final result.

    Args:
        input_filename: The original filename string.

    Returns:
        The cleaned filename string with leading spaces converted to underscores.
    """
    # First, replace illegal characters globally
    output_filename = input_filename.translate(CHARACTER_TRANSLATION_TABLE)

    # Then, specifically replace any sequence of leading spaces with underscores
    output_filename = LEADING_SPACE_PATTERN.sub(
        lambda match: "_"
        * len(match.group(0)),  # Replace with matching number of underscores
        output_filename,
    )

    # Finally, strip any remaining trailing whitespace (leading are now underscores)
    return output_filename.rstrip()  # Only strip trailing


# FUNC: replace_illegal_filename_characters_prefix_underscore
def replace_illegal_filename_characters_prefix_underscore(
    input_filename: str,
) -> str:
    """Replaces illegal chars and adds '_' prefix if the original started with space.

    Illegal characters are replaced using `CHARACTER_TRANSLATION_TABLE`. If the
    *original* filename (before replacements) started with any whitespace, an
    underscore `_` is prepended to the result. Strips leading/trailing
    whitespace from the final result (after potential prefixing).

    Args:
        input_filename: The original filename string.

    Returns:
        The cleaned filename string, potentially prefixed with an underscore.
    """
    # Perform standard illegal character replacement first
    output_filename = input_filename.translate(CHARACTER_TRANSLATION_TABLE)

    # Check the *original* string for leading space before deciding to prefix
    result = (
        "_"
        + output_filename.lstrip()  # Prepend _ and remove original leading space *from output*
        if input_filename
        != input_filename.lstrip()  # Check if original had leading space
        else output_filename
    )

    # Strip any remaining whitespace (leading or trailing) from the final result
    return result.strip()
