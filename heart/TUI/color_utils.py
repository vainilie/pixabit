#             _                        _
#            | |                      | |
# __   ____ _| |_   _  ___    ___ ___ | | ___  _ __
# \ \ / / _` | | | | |/ _ \  / __/ _ \| |/ _ \| '__|
#  \ V / (_| | | |_| |  __/ | (_| (_) | | (_) | |
#   \_/ \__,_|_|\__,_|\___|  \___\___/|_|\___/|_|


def value_color(val):
    """
    Determine the color classification for a given numerical value.

    The function categorizes the input value into one of the following color
    classifications based on the value ranges:
    - "best" for values greater than 11.
    - "better" for values greater than 5 but less than or equal to 11.
    - "good" for positive values greater than 0 but less than or equal to 5.
    - "neutral" for a value of 0.
    - "bad" for negative values greater than -9 but less than or equal to 0.
    - "worse" for values greater than -16 but less than or equal to -9.
    - "worst" for values less than or equal to -16.

    Args:
        val (int or float): The numerical value to be categorized.

    Returns:
        str: The color classification corresponding to the input value.

    Example:
        value_color(10)  # Output: "better"
        value_color(-5)  # Output: "bad"
    """
    if val > 11:
        value = "best"
    elif val > 5:
        value = "better"
    elif val > 0:
        value = "good"
    elif val == 0:
        value = "neutral"
    elif val > -9:
        value = "bad"
    elif val > -16:
        value = "worse"
    else:
        value = "worst"
    return value
