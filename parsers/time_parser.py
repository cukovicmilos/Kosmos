"""
Time parser for Kosmos Telegram Bot.
Parses natural language time expressions in Serbian and English.

Supported formats:
- Days: sutra/tomorrow, prekosutra/dat, pon-ned/mon-sun
- Dates: DD.MM.YYYY., DD.MM.YYYY, DD.MM., DD.MM, DD/MM/YYYY, DD/MM
- Times: HH:MM, H, HAM/PM, HHMM military time

Rules:
1. Time must be at the end of the message
2. If time has passed today, assume tomorrow
3. Weekdays always mean next occurrence
4. Dates without year assume current year (or next year if date has passed)
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


def parse_date_string(date_str: str, current_time: datetime) -> Optional[datetime]:
    """
    Parse date string into datetime object.

    Supported formats:
    - DD.MM.YYYY. (Serbian format with trailing dot)
    - DD.MM.YYYY (Serbian format without trailing dot)
    - DD.MM. (day and month with trailing dot, assumes current/next year)
    - DD.MM (day and month, assumes current/next year)
    - DD/MM/YYYY (slash format)
    - DD/MM (slash format, assumes current/next year)

    Args:
        date_str: Date string to parse
        current_time: Current datetime for year inference

    Returns:
        Datetime object or None if parsing fails
    """
    date_str = date_str.strip().rstrip('.')  # Remove trailing dot if present

    # Format: DD.MM.YYYY or DD/MM/YYYY
    match = re.match(r'^(\d{1,2})[./](\d{1,2})[./](\d{4})$', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        try:
            return current_time.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            return None

    # Format: DD.MM or DD/MM (without year)
    match = re.match(r'^(\d{1,2})[./](\d{1,2})$', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = current_time.year
        
        try:
            target_date = current_time.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
            # If the date has already passed this year, assume next year
            if target_date.date() < current_time.date():
                target_date = target_date.replace(year=year + 1)
            return target_date
        except ValueError:
            return None

    return None


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

    # Try last 1-3 words as time/day+time/date+time
    time_part = None
    day_offset = 0  # Days to add
    target_weekday = None  # Target weekday if specified
    target_date = None  # Specific date if specified
    reminder_text = None

    # Try parsing last word as time
    last_word = words[-1].lower()
    parsed_time = parse_time_string(last_word)

    if parsed_time:
        # Last word is time
        time_part = parsed_time

        # Check if second-to-last word is a day keyword or date
        if len(words) >= 2:
            second_last = words[-2]  # Keep original case for date parsing
            second_last_lower = second_last.lower()

            if second_last_lower in DAY_KEYWORDS:
                day_offset = DAY_KEYWORDS[second_last_lower]
                reminder_text = ' '.join(words[:-2])
            elif second_last_lower in WEEKDAY_KEYWORDS:
                target_weekday = WEEKDAY_KEYWORDS[second_last_lower]
                reminder_text = ' '.join(words[:-2])
            else:
                # Try parsing as a date (e.g., 23.12.2025, 23.12., 23/12)
                parsed_date = parse_date_string(second_last, now)
                if parsed_date:
                    target_date = parsed_date
                    reminder_text = ' '.join(words[:-2])
                else:
                    # No day keyword or date, just time
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
                # Try as "day time" or "date time"
                day_word = words[-2]  # Keep original case for date parsing
                day_word_lower = day_word.lower()
                time_word = words[-1].lower()

                parsed_time = parse_time_string(time_word)
                if parsed_time:
                    time_part = parsed_time

                    if day_word_lower in DAY_KEYWORDS:
                        day_offset = DAY_KEYWORDS[day_word_lower]
                        reminder_text = ' '.join(words[:-2])
                    elif day_word_lower in WEEKDAY_KEYWORDS:
                        target_weekday = WEEKDAY_KEYWORDS[day_word_lower]
                        reminder_text = ' '.join(words[:-2])
                    else:
                        # Try parsing as a date
                        parsed_date = parse_date_string(day_word, now)
                        if parsed_date:
                            target_date = parsed_date
                            reminder_text = ' '.join(words[:-2])
                        else:
                            # Not a recognized day or date, include it in reminder text
                            reminder_text = ' '.join(words[:-1])

    if not time_part or not reminder_text:
        return None

    hour, minute = time_part

    # Calculate scheduled datetime
    if target_date is not None:
        # Specific date specified
        scheduled_dt = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Make it timezone-aware
        scheduled_dt = tz.localize(scheduled_dt) if scheduled_dt.tzinfo is None else scheduled_dt
    elif target_weekday is not None:
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


def format_reminder_confirmation(
    reminder_text: str,
    scheduled_time: datetime,
    time_format: str = "24h",
    now: datetime = None,
    prefix: str = "✓"
) -> str:
    """
    Format reminder confirmation message.

    Shows only time if scheduled for today, otherwise shows full date.

    Args:
        reminder_text: The reminder message text
        scheduled_time: When the reminder is scheduled (naive datetime in user's timezone)
        time_format: User's time format preference (12h, 24h)
        now: Current time for comparison (defaults to datetime.now())
        prefix: Prefix character/emoji (default "✓", use "⏰" for postpone)

    Returns:
        Formatted confirmation string like "✓ reminder > 15:00" or "✓ reminder > Mon 15.01.2024. 15:00"
    """
    if now is None:
        now = datetime.now()

    now_date = now.date()
    scheduled_date = scheduled_time.date()

    # Format time based on user preference
    if time_format == "12h":
        time_str = scheduled_time.strftime("%I:%M %p")
    else:
        time_str = scheduled_time.strftime("%H:%M")

    if now_date == scheduled_date:
        # Today - show only time
        return f"{prefix} {reminder_text} > {time_str}"
    else:
        # Another day - show day abbreviation, date and time
        day_abbr = scheduled_time.strftime("%a")
        date_str = scheduled_time.strftime("%d.%m.%Y.")
        return f"{prefix} {reminder_text} > {day_abbr} {date_str} {time_str}"


def parse_time(time_str: str) -> Optional['datetime.time']:
    """
    Parse time string into datetime.time object.

    Args:
        time_str: Time string (e.g., "14:30", "9am", "21")

    Returns:
        datetime.time object or None if parsing fails
    """
    from datetime import time as dt_time

    parsed = parse_time_string(time_str)
    if parsed:
        hour, minute = parsed
        return dt_time(hour, minute)

    return None


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
        # Date format tests
        "Sastanak 23.12.2025. 9:00",
        "Rodjendan 15.01.2026 14:30",
        "Meeting 25.12. 10:00",
        "Event 31.12 18:00",
        "Party 01/01/2026 20:00",
        "Dinner 24/12 19:30",
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
