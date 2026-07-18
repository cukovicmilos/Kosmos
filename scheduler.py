"""
Scheduler module for Kosmos Telegram Bot.
Background scheduler that checks and sends pending reminders.
"""

import logging
import json
import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from telegram.error import NetworkError, TimedOut, TelegramError, BadRequest, Forbidden
from telegram.helpers import escape_markdown

from database import get_pending_reminders, update_reminder_status, update_reminder_time, parse_db_datetime
from keyboards import build_notification_keyboard
from message_queue import process_pending_messages, cleanup_old_messages

logger = logging.getLogger(__name__)

# Import bot_stats functions (imported here to avoid circular dependencies)
try:
    from bot_stats import update_bot_short_description, update_bot_description
    BOT_STATS_AVAILABLE = True
except ImportError:
    logger.warning("bot_stats module not available")
    BOT_STATS_AVAILABLE = False

# Global scheduler instance
scheduler = None


def calculate_next_occurrence(reminder: dict) -> datetime:
    """
    Calculate the next occurrence time for a recurring reminder.

    Args:
        reminder: Reminder dict from database with recurrence info

    Returns:
        Next scheduled datetime
    """
    current_time = parse_db_datetime(reminder['scheduled_time'])
    recurrence_type = reminder['recurrence_type']

    if recurrence_type == 'daily':
        # Add 1 day
        next_time = current_time + timedelta(days=1)

    elif recurrence_type == 'interval':
        # Add N days
        interval = reminder['recurrence_interval'] or 1
        next_time = current_time + timedelta(days=interval)

    elif recurrence_type == 'weekly':
        # Get next day from the list of weekdays
        weekdays_json = reminder['recurrence_days']
        if not weekdays_json:
            logger.error(f"Weekly reminder {reminder['id']} has no recurrence_days")
            return current_time + timedelta(days=7)

        try:
            weekdays = json.loads(weekdays_json)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in recurrence_days for reminder {reminder['id']}")
            return current_time + timedelta(days=7)

        # Map day names to numbers (Monday=0, Sunday=6)
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        # Convert weekday names to numbers
        target_days = sorted([day_map[day.lower()] for day in weekdays if day.lower() in day_map])

        if not target_days:
            logger.error(f"No valid weekdays for reminder {reminder['id']}")
            return current_time + timedelta(days=7)

        # Find next occurrence
        current_weekday = current_time.weekday()
        days_ahead = None

        for target_day in target_days:
            diff = (target_day - current_weekday) % 7
            if diff > 0:  # Must be in the future
                days_ahead = diff
                break

        # If no day found in this week, use first day next week
        if days_ahead is None:
            days_ahead = (target_days[0] - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7

        next_time = current_time + timedelta(days=days_ahead)

    elif recurrence_type == 'monthly':
        # Same day next month
        day_of_month = reminder['recurrence_day_of_month'] or current_time.day

        # Calculate next month
        year = current_time.year
        month = current_time.month + 1
        if month > 12:
            month = 1
            year += 1

        # Handle day overflow (e.g., Jan 31 -> Feb 28)
        max_day = calendar.monthrange(year, month)[1]
        day = min(day_of_month, max_day)

        next_time = current_time.replace(year=year, month=month, day=day)

    else:
        logger.error(f"Unknown recurrence type '{recurrence_type}' for reminder {reminder['id']}")
        next_time = current_time + timedelta(days=1)

    logger.info(f"Calculated next occurrence for reminder {reminder['id']}: {next_time}")
    return next_time


def calculate_first_occurrence(
    recurrence_type: str,
    reminder_time,
    now: datetime,
    recurrence_interval: int = None,
    recurrence_days: list = None,
    recurrence_day_of_month: int = None
) -> datetime:
    """
    Calculate the first occurrence for a newly created recurring reminder.

    Args:
        recurrence_type: 'daily', 'interval', 'weekly' or 'monthly'
        reminder_time: datetime.time object - time of day for the reminder
        now: Current naive datetime in the user's timezone
        recurrence_interval: For 'interval' type - number of days between occurrences
        recurrence_days: For 'weekly' type - list of weekday names (e.g., ['monday'])
        recurrence_day_of_month: For 'monthly' type - day of month (1-31)

    Returns:
        First occurrence as naive datetime in the user's timezone
    """
    base_time = datetime.combine(now.date(), reminder_time)

    if recurrence_type == 'interval':
        # First occurrence is today if the time is still in the future,
        # otherwise one interval from today
        interval = recurrence_interval or 1
        if base_time > now:
            return base_time
        return base_time + timedelta(days=interval)

    if recurrence_type == 'weekly':
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        target_days = sorted({
            day_map[day.lower()] for day in (recurrence_days or [])
            if isinstance(day, str) and day.lower() in day_map
        })

        if not target_days:
            logger.error(f"Weekly reminder has no valid days: {recurrence_days}, falling back to daily")
            return base_time + timedelta(days=1) if base_time <= now else base_time

        # Pick the nearest selected weekday whose occurrence is still in the future
        candidates = []
        for target_day in target_days:
            days_ahead = (target_day - now.weekday()) % 7
            candidate = base_time + timedelta(days=days_ahead)
            if candidate <= now:
                candidate += timedelta(days=7)
            candidates.append(candidate)
        return min(candidates)

    if recurrence_type == 'monthly':
        day_of_month = recurrence_day_of_month or now.day

        # Try this month first
        max_day = calendar.monthrange(now.year, now.month)[1]
        candidate = base_time.replace(day=min(day_of_month, max_day))

        if candidate <= now:
            # Time has passed (or day already passed) - go to next month
            year, month = now.year, now.month + 1
            if month > 12:
                month = 1
                year += 1
            max_day = calendar.monthrange(year, month)[1]
            candidate = candidate.replace(year=year, month=month, day=min(day_of_month, max_day))

        return candidate

    # 'daily' (and fallback for unknown types): today if time is in the future, else tomorrow
    if recurrence_type != 'daily':
        logger.error(f"Unknown recurrence type '{recurrence_type}', falling back to daily")
    return base_time + timedelta(days=1) if base_time <= now else base_time


async def check_and_send_reminders(bot: Bot):
    """
    Background task that checks for pending reminders and sends them.
    Runs every minute.
    """
    try:
        # Get all pending reminders that are due
        pending_reminders = get_pending_reminders()

        if not pending_reminders:
            return

        logger.info(f"Found {len(pending_reminders)} pending reminders to send")

        for reminder in pending_reminders:
            try:
                await send_reminder(bot, reminder)
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder['id']}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in check_and_send_reminders: {e}", exc_info=True)


async def send_reminder(bot: Bot, reminder: dict):
    """
    Send a reminder to the user with postpone options.

    Args:
        bot: Telegram bot instance
        reminder: Reminder dict from database
    """
    user_id = reminder['user_id']
    reminder_id = reminder['id']
    message_text = reminder['message_text']

    # Get user's timezone and language from the reminder (joined from users table)
    user_timezone = reminder.get('timezone', 'Europe/Belgrade')
    user_lang = reminder.get('language', 'en')

    # Check if recurring (used for icon and delete button)
    is_recurring = reminder.get('is_recurring', 0)

    # Escape user text for Markdown to prevent Telegram parse errors
    # (unescaped _, *, [ etc. caused BadRequest and infinite pending retries)
    safe_message_text = escape_markdown(message_text, version=1)

    # Format reminder notification message (🔁 for recurring, 🔔 for one-time)
    if is_recurring:
        notification_text = f"🔁 {safe_message_text}"
    else:
        notification_text = f"🔔 {safe_message_text}"

    # Create inline keyboard with postpone options (localized)
    reply_markup = build_notification_keyboard(reminder_id, is_recurring, user_lang)

    try:
        # Send reminder message
        try:
            await bot.send_message(
                chat_id=user_id,
                text=notification_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except BadRequest as markdown_error:
            # Markdown parsing failed despite escaping - fall back to plain text
            logger.warning(
                f"Markdown parse failed for reminder {reminder_id}, "
                f"retrying without parse_mode: {markdown_error}"
            )
            plain_text = f"🔁 {message_text}" if is_recurring else f"🔔 {message_text}"
            await bot.send_message(
                chat_id=user_id,
                text=plain_text,
                reply_markup=reply_markup
            )

        if is_recurring:
            # Calculate next occurrence and reschedule
            next_time = calculate_next_occurrence(reminder)

            # Check if recurring period has expired (end_date set)
            end_date_str = reminder.get('recurrence_end_date')
            if end_date_str:
                try:
                    end_date = parse_db_datetime(end_date_str)
                except (ValueError, AttributeError):
                    end_date = None

                if end_date and next_time > end_date:
                    update_reminder_status(reminder_id, 'sent')
                    logger.info(f"Recurring reminder {reminder_id} completed - end date {end_date} reached")
                else:
                    update_reminder_time(reminder_id, next_time)
                    logger.info(f"Recurring reminder {reminder_id} rescheduled to {next_time}")
            else:
                update_reminder_time(reminder_id, next_time)
                logger.info(f"Recurring reminder {reminder_id} rescheduled to {next_time}")
        else:
            # Mark one-time reminder as sent
            update_reminder_status(reminder_id, 'sent')
            logger.info(f"One-time reminder {reminder_id} marked as sent")

        logger.info(f"Reminder {reminder_id} sent to user {user_id}")

    except Forbidden as e:
        # User blocked the bot - cancel the reminder to stop infinite retries
        update_reminder_status(reminder_id, 'cancelled')
        logger.warning(
            f"User {user_id} blocked the bot - reminder {reminder_id} cancelled: {e}"
        )

    except (NetworkError, TimedOut) as e:
        logger.warning(f"Network error sending reminder {reminder_id} to user {user_id}: {e}")
        # Don't update status - will retry next time

    except TelegramError as e:
        # Other Telegram error (user blocked bot, invalid chat, etc.)
        logger.error(f"Telegram error sending reminder {reminder_id} to user {user_id}: {e}")
        # Don't update status - will retry next time

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error sending reminder {reminder_id} to user {user_id}: {e}", exc_info=True)
        # Don't update status - will retry next time


def start_scheduler(bot: Bot):
    """
    Start the APScheduler background scheduler.

    Args:
        bot: Telegram bot instance
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    scheduler = AsyncIOScheduler()

    # Add job to check reminders every minute
    scheduler.add_job(
        check_and_send_reminders,
        trigger=IntervalTrigger(minutes=1),
        args=[bot],
        id='check_reminders',
        name='Check and send pending reminders',
        replace_existing=True
    )

    # Add job to process pending messages every 30 seconds
    scheduler.add_job(
        process_pending_messages,
        trigger=IntervalTrigger(seconds=30),
        args=[bot],
        id='process_pending_messages',
        name='Process pending confirmation messages',
        replace_existing=True
    )

    # Add job to cleanup old messages once per day
    scheduler.add_job(
        cleanup_old_messages,
        trigger=IntervalTrigger(hours=24),
        args=[7],  # Delete messages older than 7 days
        id='cleanup_old_messages',
        name='Cleanup old pending messages',
        replace_existing=True
    )

    # Add job to update bot short description every 6 hours
    if BOT_STATS_AVAILABLE:
        scheduler.add_job(
            update_bot_short_description,
            trigger=IntervalTrigger(hours=6),
            args=[bot],
            id='update_short_description',
            name='Update bot short description with active users',
            replace_existing=True
        )
        
        # Add job to update full description once per day
        scheduler.add_job(
            update_bot_description,
            trigger=IntervalTrigger(hours=24),
            args=[bot],
            id='update_full_description',
            name='Update bot full description',
            replace_existing=True
        )
        logger.info("Bot statistics update jobs scheduled")

    scheduler.start()
    logger.info("Scheduler started - checking reminders every minute, pending messages every 30 seconds")


def stop_scheduler():
    """
    Stop the scheduler.
    """
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
