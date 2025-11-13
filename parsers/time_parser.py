"""
Time parser for Kosmos Telegram Bot.
Parses natural language time expressions in Serbian and English.

Supported formats:
- Days: sutra/tomorrow, prekosutra/dat, pon-ned/mon-sun
- Times: HH:MM, H, HAM/PM, HHMM military time

Rules:
1. Time must be at the end of the message
2. If time has passed today, assume tomorrow
3. Weekdays always mean next occurrence
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pytz

logger = logging.getLogger(__name__)


# Day keywords mapping
DAY_KEYWORDS = {
    # Serbian
    'sutra': 1,
    'prekosutra': 2,
    # English
    'tomorrow': 1,
    'dat': 2,  # day after tomorrow
}

# Weekday keywords mapping (both Serbian and English)
WEEKDAY_KEYWORDS = {
    # Serbian (short)
    'pon': 0,  # Monday
    'uto': 1,  # Tuesday
    'sre': 2,  # Wednesday
    'cet': 3,  # Thursday
    'pet': 4,  # Friday
    'sub': 5,  # Saturday
    'ned': 6,  # Sunday
    # English (short)
    'mon': 0,
    'tue': 1,
    'wed': 2,
    'thu': 3,
    'fri': 4,
    'sat': 5,
    'sun': 6,
    # English (full)
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


def parse_time_string(time_str: str) -> Optional[Tuple[int, int]]:
    """
    Parse time string into (hour, minute) tuple.

    Supported formats:
    - 21:00 (HH:MM)
    - 21:30 (HH:MM)
    - 8 (H - assumes :00)
    - 17 (HH - assumes :00)
    - 7am, 7AM (AM/PM format)
    - 6 AM (with space)
    - 2100 (military time - HHMM)
    - 0700 (military time with leading zero)

    Args:
        time_str: Time string to parse

    Returns:
        Tuple of (hour, minute) or None if parsing fails
    """
    time_str = time_str.strip().lower()

    # Format: HH:MM or H:MM
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        return None

    # Format: HAM, HPM, H AM, H PM (with or without space)
    match = re.match(r'^(\d{1,2})\s*(am|pm)$', time_str)
    if match:
        hour = int(match.group(1))
        period = match.group(2)

        if hour < 1 or hour > 12:
            return None

        # Convert to 24-hour format
        if period == 'am':
            if hour == 12:
                hour = 0  # 12 AM = 00:00
        else:  # pm
            if hour != 12:
                hour += 12  # 1 PM = 13:00, but 12 PM = 12:00

        return (hour, 0)

    # Format: HHMM (military time - 4 digits)
    match = re.match(r'^(\d{4})$', time_str)
    if match:
        time_num = match.group(1)
        hour = int(time_num[:2])
        minute = int(time_num[2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        return None

    # Format: H or HH (just hour, assumes :00)
    match = re.match(r'^(\d{1,2})$', time_str)
    if match:
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return (hour, 0)
        return None

    return None


def get_next_weekday(target_weekday: int, current_time: datetime) -> datetime:
    """
    Get the next occurrence of a specific weekday.

    Args:
        target_weekday: Target weekday (0=Monday, 6=Sunday)
        current_time: Current datetime

    Returns:
        Datetime of next occurrence of target weekday
    """
    current_weekday = current_time.weekday()
    days_ahead = target_weekday - current_weekday

    # Always go to NEXT occurrence (even if today is that weekday)
    if days_ahead <= 0:
        days_ahead += 7

    return current_time + timedelta(days=days_ahead)


def parse_reminder(message: str, user_timezone: str = "Europe/Belgrade") -> Optional[Tuple[str, datetime]]:
    """
    Parse reminder message and extract text and scheduled time.

    Args:
        message: User's message (e.g., "Kafa sutra 14:00")
        user_timezone: User's timezone

    Returns:
        Tuple of (reminder_text, scheduled_datetime) or None if parsing fails
    """
    message = message.strip()

    if not message:
        return None

    # Get user's timezone
    try:
        tz = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")

    # Current time in user's timezone
    now = datetime.now(tz)

    # Try to parse the message
    # Strategy: Look for time at the end of the message

    # First, try to extract time from the end
    # Pattern: Look for time-like strings at the end

    # Try different time patterns from the end
    words = message.split()

    if len(words) < 2:
        # Need at least: "text time" or "text day time"
        return None

    # Try last 1-3 words as time/day+time
    time_part = None
    day_offset = 0  # Days to add
    target_weekday = None  # Target weekday if specified
    reminder_text = None

    # Try parsing last word as time
    last_word = words[-1].lower()
    parsed_time = parse_time_string(last_word)

    if parsed_time:
        # Last word is time
        time_part = parsed_time

        # Check if second-to-last word is a day keyword
        if len(words) >= 2:
            second_last = words[-2].lower()

            if second_last in DAY_KEYWORDS:
                day_offset = DAY_KEYWORDS[second_last]
                reminder_text = ' '.join(words[:-2])
            elif second_last in WEEKDAY_KEYWORDS:
                target_weekday = WEEKDAY_KEYWORDS[second_last]
                reminder_text = ' '.join(words[:-2])
            else:
                # No day keyword, just time
                reminder_text = ' '.join(words[:-1])
        else:
            reminder_text = ' '.join(words[:-1])
    else:
        # Try last 2 words as "day time" or "time am/pm"
        if len(words) >= 2:
            last_two = ' '.join(words[-2:]).lower()

            # Try parsing as "H AM" or "H PM"
            parsed_time = parse_time_string(last_two)
            if parsed_time:
                time_part = parsed_time
                reminder_text = ' '.join(words[:-2])
            else:
                # Try as "day time"
                day_word = words[-2].lower()
                time_word = words[-1].lower()

                parsed_time = parse_time_string(time_word)
                if parsed_time:
                    time_part = parsed_time

                    if day_word in DAY_KEYWORDS:
                        day_offset = DAY_KEYWORDS[day_word]
                        reminder_text = ' '.join(words[:-2])
                    elif day_word in WEEKDAY_KEYWORDS:
                        target_weekday = WEEKDAY_KEYWORDS[day_word]
                        reminder_text = ' '.join(words[:-2])
                    else:
                        # Not a recognized day, include it in reminder text
                        reminder_text = ' '.join(words[:-1])

    if not time_part or not reminder_text:
        return None

    hour, minute = time_part

    # Calculate scheduled datetime
    if target_weekday is not None:
        # Weekday specified - get next occurrence
        scheduled_dt = get_next_weekday(target_weekday, now)
        scheduled_dt = scheduled_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    else:
        # Day offset specified or today
        scheduled_dt = now + timedelta(days=day_offset)
        scheduled_dt = scheduled_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Rule: If time has passed today and no day was specified, assume tomorrow
        if day_offset == 0 and scheduled_dt <= now:
            scheduled_dt += timedelta(days=1)

    # Remove timezone info to store as local time in database
    # SQLite will convert timezone-aware datetimes to UTC, which we don't want
    scheduled_dt_naive = scheduled_dt.replace(tzinfo=None)

    logger.info(f"Parsed reminder: '{reminder_text}' at {scheduled_dt}")

    return (reminder_text.strip(), scheduled_dt_naive)


def format_datetime(dt: datetime, language: str = "en", time_format: str = "24h") -> str:
    """
    Format datetime for display to user.

    Args:
        dt: Datetime to format
        language: User's language (en, sr-lat)
        time_format: User's time format preference (12h, 24h)

    Returns:
        Formatted datetime string
    """
    # Format date
    date_str = dt.strftime("%d.%m.%Y.")

    # Format time
    if time_format == "12h":
        time_str = dt.strftime("%I:%M %p")
    else:
        time_str = dt.strftime("%H:%M")

    return f"{date_str} {time_str}"


if __name__ == "__main__":
    # Test the parser
    from config import setup_logging
    setup_logging()

    test_cases = [
        "Kafa sutra 14:00",
        "Sastanak pon 10:00",
        "Pozovi Jovana 18:30",
        "Coffee tomorrow 16:00",
        "Meeting mon 10:00",
        "Call John 6 PM",
        "Test 2100",
        "Something 7am",
        "Task prekosutra 9:00",
    ]

    print("Testing time parser:\n")
    for test in test_cases:
        result = parse_reminder(test)
        if result:
            text, dt = result
            print(f"✓ '{test}'")
            print(f"  → Text: '{text}'")
            print(f"  → Time: {dt}")
        else:
            print(f"✗ '{test}' - FAILED TO PARSE")
        print()
