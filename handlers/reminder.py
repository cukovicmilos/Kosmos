"""
Reminder handler for Kosmos Telegram Bot.
Processes user messages to create reminders.
"""

import logging
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import NetworkError, TimedOut

from database import create_reminder, get_user
from parsers.time_parser import parse_reminder, format_datetime, format_reminder_confirmation
from i18n import get_text
from message_queue import queue_message

logger = logging.getLogger(__name__)


async def handle_reminder_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle regular text messages and try to parse them as reminders.

    Expected format: [reminder text] [day] [time]
    Examples:
    - "Kafa sutra 14:00"
    - "Meeting mon 10:00"
    - "Call John 18:30"
    """
    # Guard clauses for None checks
    if not update.effective_user:
        logger.warning("Received update without effective_user")
        return
    
    if not update.message:
        logger.warning("Received update without message")
        return
    
    if not update.message.text:
        logger.warning("Received message without text")
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text

    # Get user from database
    user = get_user(user_id)
    if not user:
        # User doesn't exist - shouldn't happen, but handle gracefully
        await update.message.reply_text(
            get_text("error_occurred", "en")
        )
        logger.warning(f"User {user_id} sent message but doesn't exist in database")
        return

    user_lang = user.get("language", "en")
    user_timezone = user.get("timezone", "Europe/Belgrade")
    user_time_format = user.get("time_format", "24h")

    # Try to parse the message as a reminder
    try:
        result = parse_reminder(message_text, user_timezone)

        if not result:
            # Parsing failed - show error message with examples
            await update.message.reply_text(
                get_text("reminder_parse_error", user_lang),
                parse_mode="Markdown"
            )
            logger.info(f"Failed to parse reminder from user {user_id}: '{message_text}'")
            return

        reminder_text, scheduled_time = result

        # Validate that scheduled time is not in the past (using user's timezone)
        try:
            tz = pytz.timezone(user_timezone)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone("Europe/Belgrade")
        now = datetime.now(tz).replace(tzinfo=None)  # Naive datetime in user's timezone
        if scheduled_time <= now:
            await update.message.reply_text(
                get_text("reminder_in_past", user_lang)
            )
            logger.info(f"User {user_id} tried to create reminder in the past: {scheduled_time}")
            return

        # Create reminder in database
        reminder_id = create_reminder(
            user_id=user_id,
            message_text=reminder_text,
            scheduled_time=scheduled_time
        )

        if reminder_id:
            # Success - prepare confirmation message using helper function
            confirmation_msg = format_reminder_confirmation(
                reminder_text, scheduled_time, user_time_format, now=now
            )

            # Try to send confirmation immediately
            try:
                await update.message.reply_text(confirmation_msg)
                logger.info(
                    f"Reminder created: ID={reminder_id}, user={user_id}, "
                    f"time={scheduled_time}, text='{reminder_text}'"
                )
            except (NetworkError, TimedOut) as e:
                # Network error - queue the confirmation for retry
                logger.warning(f"Network error sending confirmation to user {user_id}, queuing for retry: {e}")
                queue_message(user_id, confirmation_msg, message_type='reminder_confirmation')
                logger.info(
                    f"Reminder created and confirmation queued: ID={reminder_id}, user={user_id}, "
                    f"time={scheduled_time}, text='{reminder_text}'"
                )
            except Exception as e:
                # Other error - still queue for retry
                logger.error(f"Error sending confirmation to user {user_id}, queuing for retry: {e}")
                queue_message(user_id, confirmation_msg, message_type='reminder_confirmation')
                logger.info(
                    f"Reminder created and confirmation queued: ID={reminder_id}, user={user_id}, "
                    f"time={scheduled_time}, text='{reminder_text}'"
                )
        else:
            # Database error
            try:
                await update.message.reply_text(
                    get_text("error_occurred", user_lang)
                )
            except Exception as reply_error:
                logger.error(f"Failed to send database error message to user {user_id}: {reply_error}")
            logger.error(f"Failed to create reminder in database for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling reminder message from user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                get_text("error_occurred", user.get("language", "en"))
            )
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")


def register_handlers(application):
    """
    Register reminder message handlers.

    This handler catches all text messages that are not commands.
    """
    # Filter for text messages that are not commands
    text_filter = filters.TEXT & ~filters.COMMAND

    application.add_handler(MessageHandler(text_filter, handle_reminder_message))
