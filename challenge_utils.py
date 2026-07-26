"""
Challenge helpers for Kosmos Telegram Bot.
Pure functions for progress calculation and challenge message rendering.
"""

import logging
from datetime import datetime, date
from telegram.helpers import escape_markdown

from i18n import get_text
from database import parse_db_datetime

logger = logging.getLogger(__name__)

# Number of segments in the text progress bar
BAR_SEGMENTS = 10


def challenge_elapsed_days(start_date, now: datetime) -> int:
    """
    Calculate how many days of the challenge have elapsed.

    The creation date counts as day 1, so a challenge created today
    shows 1 elapsed day today, 2 tomorrow, etc.

    Args:
        start_date: Challenge start date (datetime, date, or DB string)
        now: Current naive datetime in the user's timezone

    Returns:
        Number of elapsed days (minimum 1)
    """
    if isinstance(start_date, datetime):
        start = start_date.date()
    elif isinstance(start_date, date):
        start = start_date
    else:
        start = parse_db_datetime(start_date).date()

    elapsed = (now.date() - start).days + 1
    return max(1, elapsed)


def build_progress_bar(elapsed: int, total: int) -> str:
    """
    Build a text progress bar from block characters.

    Args:
        elapsed: Days elapsed
        total: Total challenge days

    Returns:
        Progress bar string, e.g. '██░░░░░░░░'
    """
    if total <= 0:
        total = 1
    ratio = min(elapsed, total) / total
    filled = round(ratio * BAR_SEGMENTS)
    return "█" * filled + "░" * (BAR_SEGMENTS - filled)


def challenge_progress_percent(elapsed: int, total: int) -> int:
    """Calculate completion percentage (0-100)."""
    if total <= 0:
        total = 1
    return round(min(elapsed, total) / total * 100)


def build_challenge_message(name: str, elapsed: int, total: int, language: str = "en") -> str:
    """
    Build the daily challenge notification text with progress bar and counter.

    Args:
        name: Challenge name (raw user text - escaped internally)
        elapsed: Days elapsed
        total: Total challenge days
        language: User's language

    Returns:
        Formatted message (Markdown), completion variant when elapsed >= total
    """
    elapsed_clamped = min(elapsed, total)
    bar = build_progress_bar(elapsed, total)
    percent = challenge_progress_percent(elapsed, total)
    safe_name = escape_markdown(name, version=1)
    counter = f"{total}/{elapsed_clamped}"

    if elapsed >= total:
        return get_text(
            "challenge_completed", language,
            name=safe_name, bar=bar, percent=percent, counter=counter
        )

    return get_text(
        "challenge_notification", language,
        name=safe_name, bar=bar, percent=percent, counter=counter
    )
