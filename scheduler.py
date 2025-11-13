"""
Scheduler module for Kosmos Telegram Bot.
Background scheduler that checks and sends pending reminders.
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from database import get_pending_reminders, update_reminder_status
from i18n import get_text

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


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

        # Update reminder status to 'sent'
        update_reminder_status(reminder_id, 'sent')

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
