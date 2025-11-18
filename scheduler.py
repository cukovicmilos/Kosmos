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
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from database import get_pending_reminders, update_reminder_status, update_reminder_time
from i18n import get_text

logger = logging.getLogger(__name__)

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
    current_time = datetime.strptime(reminder['scheduled_time'], '%Y-%m-%d %H:%M:%S')
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

    # Get user's timezone from the reminder (joined from users table)
    user_timezone = reminder.get('timezone', 'Europe/Belgrade')

    # For now, we'll use English for the notification
    # In a future enhancement, we could join with users table to get language preference
    # But the database query already includes timezone from the JOIN

    # Format reminder notification message
    notification_text = f"🔔 {message_text}"

    # Create inline keyboard with postpone options
    keyboard = [
        [
            InlineKeyboardButton("15 min", callback_data=f"postpone_{reminder_id}_15m"),
            InlineKeyboardButton("30 min", callback_data=f"postpone_{reminder_id}_30m"),
            InlineKeyboardButton("1h", callback_data=f"postpone_{reminder_id}_1h"),
        ],
        [
            InlineKeyboardButton("3h", callback_data=f"postpone_{reminder_id}_3h"),
            InlineKeyboardButton("1 dan", callback_data=f"postpone_{reminder_id}_1d"),
            InlineKeyboardButton("Drugo vreme", callback_data=f"postpone_{reminder_id}_custom"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Send reminder message
        await bot.send_message(
            chat_id=user_id,
            text=notification_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        # Check if this is a recurring reminder
        is_recurring = reminder.get('is_recurring', 0)

        if is_recurring:
            # Calculate next occurrence and reschedule
            next_time = calculate_next_occurrence(reminder)
            update_reminder_time(reminder_id, next_time)
            logger.info(f"Recurring reminder {reminder_id} rescheduled to {next_time}")
        else:
            # Mark one-time reminder as sent
            update_reminder_status(reminder_id, 'sent')
            logger.info(f"One-time reminder {reminder_id} marked as sent")

        logger.info(f"Reminder {reminder_id} sent to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send reminder {reminder_id} to user {user_id}: {e}", exc_info=True)
        # Don't update status if sending failed - will retry next time


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

    scheduler.start()
    logger.info("Scheduler started - checking reminders every minute")


def stop_scheduler():
    """
    Stop the scheduler.
    """
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
