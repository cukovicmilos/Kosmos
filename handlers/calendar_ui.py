"""
Shared inline calendar UI for Kosmos Telegram Bot.

Telegram has no native date picker, so this renders the standard
inline-keyboard calendar: a month grid with ◀▶ navigation via
callback_data, re-rendered in place with editMessageText.

Past days are dead buttons (caldead callback -> toast, no action).
After a date is picked, the flow only needs to ask for the time.

Shared by two flows (typing a time stays the parallel path everywhere):
  - new      -> /kalendar flow (handlers/calendar.py)
  - quick    -> Quick reminder (handlers/quick.py)

(Postpone "Custom time" does not use the picker - the reminder has already
fired, so a bare text prompt is enough.)

Callback data formats (kept well under Telegram's 64-byte limit):
  cal_{flow}_{y}_{m}_{d}   - a day was clicked
  calnav_{flow}_{y}_{m}    - ◀/▶ navigation to month m / year y
  calcancel_{flow}         - cancel the picker
  caldead                  - dead button (day in the past)
  calnoop                  - dead button (decoration / nav out of range)
"""

import calendar as calendar_lib
import re
import logging
from datetime import datetime, date
from typing import Optional, Tuple

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import get_text

logger = logging.getLogger(__name__)

FLOWS = ("new", "quick")

# Regex patterns for CallbackQueryHandler registration
DATE_PATTERN = rf"^cal_({'|'.join(FLOWS)})_(\d{{4}})_(\d{{1,2}})_(\d{{1,2}})$"
NAV_PATTERN = rf"^calnav_({'|'.join(FLOWS)})_(\d{{4}})_(\d{{1,2}})$"
CANCEL_PATTERN = rf"^calcancel_({'|'.join(FLOWS)})$"
DEAD_PATTERN = r"^caldead$"
NOOP_PATTERN = r"^calnoop$"

# How many months ahead navigation is allowed
MAX_MONTHS_AHEAD = 12

# Weekday msgid suffixes, Monday-first (matches python weekday() indexing)
_WEEKDAY_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _user_today(timezone: str) -> date:
    """Today's date in the user's timezone."""
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    return datetime.now(tz).date()


def get_month_name(month: int, language: str) -> str:
    """Translated month name (month_1 .. month_12 msgids)."""
    return get_text(f"month_{month}", language)


def format_date_display(d: date, language: str) -> str:
    """Human-readable date for prompts, e.g. 'Sre 21.10.2026.'"""
    msgid = f"weekday_short_{_WEEKDAY_ORDER[d.weekday()]}"
    return f"{get_text(msgid, language)} {d.strftime('%d.%m.%Y.')}"


def build_calendar_markup(
    flow: str,
    language: str = "en",
    timezone: str = "Europe/Belgrade",
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """
    Build the inline calendar keyboard for a month.

    Args:
        flow: Which flow is picking a date ('new' or 'quick'),
              embedded in callback_data so the right conversation handles it
        language: User's language for month/weekday/cancel labels
        timezone: User's timezone (defines which days are 'past')
        year, month: Month to render (defaults to current month)

    Returns:
        InlineKeyboardMarkup with the month grid
    """
    if flow not in FLOWS:
        flow = "new"

    today = _user_today(timezone)
    if year is None or month is None:
        year, month = today.year, today.month

    # Clamp navigation to [current month, current month + MAX_MONTHS_AHEAD]
    min_ym = (today.year, today.month)
    max_total = today.year * 12 + (today.month - 1) + MAX_MONTHS_AHEAD
    max_ym = (max_total // 12, max_total % 12 + 1)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    header = [
        InlineKeyboardButton(
            "◀",
            callback_data=(
                f"calnav_{flow}_{prev_year}_{prev_month}"
                if (prev_year, prev_month) >= min_ym else "calnoop"
            )
        ),
        InlineKeyboardButton(
            f"{get_month_name(month, language)} {year}",
            callback_data="calnoop"
        ),
        InlineKeyboardButton(
            "▶",
            callback_data=(
                f"calnav_{flow}_{next_year}_{next_month}"
                if (next_year, next_month) <= max_ym else "calnoop"
            )
        ),
    ]

    weekday_row = [
        InlineKeyboardButton(get_text(f"weekday_short_{name}", language), callback_data="calnoop")
        for name in _WEEKDAY_ORDER
    ]

    day_rows = []
    for week in calendar_lib.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                # Padding day outside the month
                row.append(InlineKeyboardButton(" ", callback_data="calnoop"))
                continue
            d = date(year, month, day)
            if d < today:
                # Dead button for past days
                row.append(InlineKeyboardButton(str(day), callback_data="caldead"))
            elif d == today:
                # Today is still clickable (marked with brackets)
                row.append(InlineKeyboardButton(f"[{day}]", callback_data=f"cal_{flow}_{year}_{month}_{day}"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal_{flow}_{year}_{month}_{day}"))
        day_rows.append(row)

    keyboard = [header, weekday_row] + day_rows
    keyboard.append([
        InlineKeyboardButton(get_text("cancel_button", language), callback_data=f"calcancel_{flow}")
    ])

    return InlineKeyboardMarkup(keyboard)


def parse_date_callback(data: str) -> Optional[Tuple[str, date]]:
    """
    Parse a day-selection callback.

    Returns:
        (flow, date) tuple or None if the callback data is invalid
    """
    match = re.match(DATE_PATTERN, data)
    if not match:
        return None
    flow, year, month, day = match.group(1), *map(int, match.groups()[1:])
    try:
        return flow, date(year, month, day)
    except ValueError:
        return None


def parse_nav_callback(data: str) -> Optional[Tuple[str, int, int]]:
    """
    Parse a month-navigation callback.

    Returns:
        (flow, year, month) tuple or None if the callback data is invalid
    """
    match = re.match(NAV_PATTERN, data)
    if not match:
        return None
    flow = match.group(1)
    year, month = int(match.group(2)), int(match.group(3))
    if not 1 <= month <= 12:
        return None
    return flow, year, month


def nav_in_range(year: int, month: int, timezone: str) -> bool:
    """Whether navigation to the given month is allowed (guards stale ◀▶ buttons)."""
    today = _user_today(timezone)
    current = today.year * 12 + (today.month - 1)
    target = year * 12 + (month - 1)
    return current <= target <= current + MAX_MONTHS_AHEAD
