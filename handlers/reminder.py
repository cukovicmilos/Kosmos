"""
Reminder handler for Kosmos Telegram Bot.
Processes user messages to create reminders.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from database import create_reminder, get_user
from parsers.time_parser import parse_reminder, format_datetime
from i18n import get_text

logger = logging.getLogger(__name__)


async def handle_reminder_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages and try to parse them as reminders.

    Expected format: [reminder text] [day] [time]
    Examples:
    - "Kafa sutra 14:00"
    - "Meeting mon 10:00"
    - "Call John 18:30"
    """
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

        # Create reminder in database
        reminder_id = create_reminder(
            user_id=user_id,
            message_text=reminder_text,
            scheduled_time=scheduled_time
        )

        if reminder_id:
            # Success - send confirmation
            await update.message.reply_text(
                get_text("reminder_created", user_lang)
            )
            logger.info(
                f"Reminder created: ID={reminder_id}, user={user_id}, "
                f"time={scheduled_time}, text='{reminder_text}'"
            )
        else:
            # Database error
            await update.message.reply_text(
                get_text("error_occurred", user_lang)
            )
            logger.error(f"Failed to create reminder in database for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling reminder message from user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            get_text("error_occurred", user.get("language", "en"))
        )


def register_handlers(application):
    """
    Register reminder message handlers.

    This handler catches all text messages that are not commands.
    """
    # Filter for text messages that are not commands
    text_filter = filters.TEXT & ~filters.COMMAND

    application.add_handler(MessageHandler(text_filter, handle_reminder_message))
