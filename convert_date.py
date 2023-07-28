import dateutil.parser
from datetime import datetime, timezone
import pytz

nowUTC = datetime.now(timezone.utc)
# Replace "YOUR_TIMEZONE" with your desired timezone for nowLOC
nowLOC = datetime.now(pytz.timezone("America/Mexico_City"))


def convert_timestamp(timestamp):
    try:
        # Convert timestamp to a datetime object in UTC timezone
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
        return utc_time

    except ValueError as e:
        return f"Invalid timestamp format: {e}"


def convert_and_check_timestamp(timestamp):
    try:
        # Convert timestamp to a datetime object in UTC timezone
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)

        # Convert UTC time to your local timezone
        local_tz = pytz.timezone(
            "YOUR_TIMEZONE"
        )  # Replace "YOUR_TIMEZONE" with your desired timezone
        local_time = utc_time.astimezone(local_tz)

        # Check if the date has already passed
        now = datetime.now(local_tz)
        if local_time < now:
            past_time = now - local_time
            days = past_time.days
            hours, remainder = divmod(past_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} was {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds ago."

        # Calculate the time left to the date
        time_left = local_time - now
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} is in {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds."

    except ValueError as e:
        return f"Invalid timestamp format: {e}"


def is_date_passed(timestamp):
    try:
        # Convert timestamp to a datetime object in UTC timezone
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)

        # Get the current datetime in UTC timezone
        now = datetime.now(timezone.utc)

        # Check if the date has already passed
        return utc_time < now

    except ValueError:
        # Invalid timestamp format
        return False
