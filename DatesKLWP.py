import dateutil.parser
from datetime import datetime, timezone
nowUTC = datetime.now(timezone.utc)
nowLOC = nowUTC.astimezone()
#
# ─── MODIFY DATE ──────────────────────────────────────────────────────────────
#


def Date(utc):
    """convert time"""
    utc_time = dateutil.parser.parse(utc)
    return utc_time.astimezone().replace(microsecond=0)


def next_one(next_one):
    """str next"""
    nextDue = date(next_one)
    diff = nextDue - nowLOC
    if diff.days < 8:
        next_ = nextDue.strftime("%dd%mM%Yy%Hh%Mm%Ss")
    else:
        next_ = nextDue.strftime("%A %d %B %H:%M")
    return next_


def expired(eval):
    """check if date was in the past"""
    evaluate = date(eval)
    return evaluate < nowLOC
