#
# ─── VALUES ───────────────────────────────────────────────────────────────────
#


def Values(val):
    """replace value with the category"""
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
