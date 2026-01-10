"""
Postpone handler for Kosmos Telegram Bot.
Handles postponing reminders when user clicks postpone buttons.
"""

import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram.error import TelegramError
import pytz

from database import get_reminder_by_id, update_reminder_time, get_user, create_reminder
from parsers.time_parser import parse_reminder, format_datetime, format_reminder_confirmation
from i18n import get_text

logger = logging.getLogger(__name__)

# Conversation states
WAITING_CUSTOM_TIME = 1


async def postpone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle postpone button clicks.

    Callback data format: postpone_{reminder_id}_{duration}
    Duration options: 15m, 30m, 1h, 3h, 1d, custom
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("postpone_"):
        return

    # Parse callback data
    parts = callback_data.split("_")
    if len(parts) != 3:
        logger.error(f"Invalid postpone callback data: {callback_data}")
        return

    reminder_id = int(parts[1])
    duration = parts[2]

    user_id = update.effective_user.id

    # Get user from database
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"
    user_timezone = user.get("timezone", "Europe/Belgrade") if user else "Europe/Belgrade"
    user_time_format = user.get("time_format", "24h") if user else "24h"

    # Get reminder from database
    reminder = get_reminder_by_id(reminder_id)
    if not reminder:
        await query.edit_message_text(
            get_text("error_occurred", user_lang)
        )
        return

    # Check if reminder belongs to this user
    if reminder['user_id'] != user_id:
        logger.warning(f"User {user_id} tried to postpone reminder {reminder_id} that doesn't belong to them")
        return

    # Handle custom time separately
    if duration == "custom":
        # Store reminder_id in user_data for the conversation handler
        context.user_data['postpone_reminder_id'] = reminder_id

        await query.edit_message_text(
            get_text("custom_time_prompt", user_lang)
        )
        return WAITING_CUSTOM_TIME

    # Calculate new scheduled time based on duration
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)

    duration_map = {
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '3h': timedelta(hours=3),
        '1d': timedelta(days=1),
    }

    if duration not in duration_map:
        logger.error(f"Invalid postpone duration: {duration}")
        await query.edit_message_text(
            get_text("error_occurred", user_lang)
        )
        return

    new_time = now + duration_map[duration]

    # Remove timezone info to store as local time in database
    new_time_naive = new_time.replace(tzinfo=None)

    # Check if this is a recurring reminder
    is_recurring = reminder.get('is_recurring', 0)

    if is_recurring:
        # For recurring reminders, create a NEW one-time instance
        # The original recurring reminder continues on its schedule
        new_reminder_id = create_reminder(
            user_id=user_id,
            message_text=reminder['message_text'],
            scheduled_time=new_time_naive,
            is_recurring=False  # One-time instance
        )
        success = new_reminder_id is not None
        logger.info(f"Created postponed one-time instance {new_reminder_id} from recurring reminder {reminder_id}")
    else:
        # For one-time reminders, update the existing reminder
        success = update_reminder_time(reminder_id, new_time_naive)
        logger.info(f"Updated one-time reminder {reminder_id} to {new_time_naive}")

    if success:
        # Remove keyboard from original message (keep reminder visible but remove buttons)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError as e:
            # Expected - message may have been deleted or is too old to edit
            logger.debug(f"Could not remove keyboard from message: {e}")

        # Format the new time for display
        reminder_text = reminder['message_text']

        # Format postpone confirmation using helper function
        postpone_msg = format_reminder_confirmation(
            reminder_text, new_time_naive, user_time_format, now=now, prefix="⏰"
        )

        # Send confirmation as a new message (don't edit the original)
        await query.message.reply_text(postpone_msg)
        logger.info(f"Reminder {reminder_id} postponed by {duration} to {new_time}")
    else:
        await query.edit_message_text(
            get_text("error_occurred", user_lang)
        )


async def custom_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle custom time input from user.
    User sends a message with time (e.g., "19:00" or "uto 19:00").
    """
    user_id = update.effective_user.id
    time_input = update.message.text

    # Get reminder_id from context
    reminder_id = context.user_data.get('postpone_reminder_id')
    if not reminder_id:
        logger.error(f"No postpone_reminder_id in user_data for user {user_id}")
        return ConversationHandler.END

    # Get user from database
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"
    user_timezone = user.get("timezone", "Europe/Belgrade") if user else "Europe/Belgrade"
    user_time_format = user.get("time_format", "24h") if user else "24h"

    # Get reminder to get the original text
    reminder = get_reminder_by_id(reminder_id)
    if not reminder or reminder['user_id'] != user_id:
        await update.message.reply_text(
            get_text("error_occurred", user_lang)
        )
        return ConversationHandler.END

    # Parse the time input
    # We need to add some dummy text since the parser expects "text time" format
    # User is only providing the time part
    dummy_message = f"reminder {time_input}"

    try:
        result = parse_reminder(dummy_message, user_timezone)

        if not result:
            # Parsing failed
            await update.message.reply_text(
                get_text("custom_time_parse_error", user_lang),
                parse_mode="Markdown"
            )
            return WAITING_CUSTOM_TIME

        _, new_time = result

        # Check if this is a recurring reminder
        is_recurring = reminder.get('is_recurring', 0)

        if is_recurring:
            # For recurring reminders, create a NEW one-time instance
            new_reminder_id = create_reminder(
                user_id=user_id,
                message_text=reminder['message_text'],
                scheduled_time=new_time,
                is_recurring=False  # One-time instance
            )
            success = new_reminder_id is not None
            logger.info(f"Created postponed one-time instance {new_reminder_id} from recurring reminder {reminder_id}")
        else:
            # For one-time reminders, update the existing reminder
            success = update_reminder_time(reminder_id, new_time)
            logger.info(f"Updated one-time reminder {reminder_id} to custom time {new_time}")

        if success:
            # Format the new time for display using helper function
            reminder_text = reminder['message_text']
            tz = pytz.timezone(user_timezone)
            now = datetime.now(tz).replace(tzinfo=None)
            postpone_msg = format_reminder_confirmation(
                reminder_text, new_time, user_time_format, now=now, prefix="⏰"
            )

            await update.message.reply_text(postpone_msg)
            logger.info(f"Reminder {reminder_id} postponed to custom time {new_time}")
        else:
            await update.message.reply_text(
                get_text("error_occurred", user_lang)
            )

    except Exception as e:
        logger.error(f"Error parsing custom time from user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            get_text("error_occurred", user_lang)
        )

    # Clear user_data
    context.user_data.pop('postpone_reminder_id', None)
    return ConversationHandler.END


async def cancel_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel custom time input conversation.
    """
    context.user_data.pop('postpone_reminder_id', None)
    return ConversationHandler.END


def register_handlers(application):
    """
    Register postpone handlers.
    """
    from telegram.ext import CallbackQueryHandler, ConversationHandler, MessageHandler, filters

    # Register callback query handler for postpone buttons (non-custom durations)
    application.add_handler(
        CallbackQueryHandler(postpone_callback, pattern="^postpone_.*(?<!custom)$")
    )

    # Register ConversationHandler for custom time postpone
    custom_time_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(postpone_callback, pattern="^postpone_.*_custom$")
        ],
        states={
            WAITING_CUSTOM_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_time_message)
            ]
        },
        fallbacks=[
            # If user sends a command or cancels, end conversation
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    application.add_handler(custom_time_handler)
