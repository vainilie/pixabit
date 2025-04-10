"""Replace illegal characters with full-width variant"""

import re

character_translation_table = str.maketrans(
    '"*/:<>?\\|\t\n\v\f\r', "＂＊／：＜＞？＼￨     "
)
leading_space_pattern = re.compile(r"^\s+")


def replace_illegal_filename_characters(input_filename: str):
    r"""
    Replace illegal characters with full-width variant
    Table
    "           ->  uff02 full-width quotation mark         ＂
    *           ->  uff0a full-width asterisk               ＊
    /           ->  uff0f full-width solidus                ／
    :           ->  uff1a full-width colon                  ：
    <           ->  uff1c full-width less-than sign         ＜
    >           ->  uff1e full-width greater-than sign      ＞
    ?           ->  uff1f full-width question mark          ？
    \           ->  uff3c full-width reverse solidus        ＼
    |           ->  uffe8 half-width forms light vertical   ￨
    \t\n\v\f\r  ->  u0020 space
    """
    return input_filename.translate(character_translation_table)


def replace_illegal_filename_characters_leading_underscores(input_filename: str):
    r"""
    Replace illegal characters with full-width variant
    Replace leading spaces with underscores
    Table
    "           ->  uff02 full-width quotation mark         ＂
    *           ->  uff0a full-width asterisk               ＊
    /           ->  uff0f full-width solidus                ／
    :           ->  uff1a full-width colon                  ：
    <           ->  uff1c full-width less-than sign         ＜
    >           ->  uff1e full-width greater-than sign      ＞
    ?           ->  uff1f full-width question mark          ？
    \           ->  uff3c full-width reverse solidus        ＼
    |           ->  uffe8 half-width forms light vertical   ￨
    \t\n\v\f\r  ->  u0020 space
    """
    output_filename = input_filename.translate(character_translation_table)
    output_filename = re.sub(
        leading_space_pattern, lambda match: "_" * len(match.group(0)), output_filename
    )
    return output_filename


def replace_illegal_filename_characters_prefix_underscore(input_filename: str):
    r"""
    Replace illegal characters with full-width variant
    if leading space then add underscore prefix
    Table
    "           ->  uff02 full-width quotation mark         ＂
    *           ->  uff0a full-width asterisk               ＊
    /           ->  uff0f full-width solidus                ／
    :           ->  uff1a full-width colon                  ：
    <           ->  uff1c full-width less-than sign         ＜
    >           ->  uff1e full-width greater-than sign      ＞
    ?           ->  uff1f full-width question mark          ？
    \           ->  uff3c full-width reverse solidus        ＼
    |           ->  uffe8 half-width forms light vertical   ￨
    \t\n\v\f\r  ->  u0020 space
    """
    output_filename = input_filename.translate(character_translation_table)
    return "_" + output_filename if output_filename.startswith(" ") else output_filename


if __name__ == "__main__":
    filename = "\t\n\v\f\ra*b/c:d<e>f?g\\h|i\t\n\v\f\r.txt"
    print(
        f"""Original:
"{filename}"
Replaced:
"{replace_illegal_filename_characters(filename)}"
"{replace_illegal_filename_characters_leading_underscores(filename)}"
"{replace_illegal_filename_characters_prefix_underscore(filename)}"
"""
    )
