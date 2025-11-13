"""
List handler for Kosmos Telegram Bot.
Displays all upcoming reminders with delete buttons.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import pytz

from database import get_user_reminders, delete_reminder, get_user
from parsers.time_parser import format_datetime
from i18n import get_text

logger = logging.getLogger(__name__)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /list command.
    Shows all upcoming (pending) reminders for the user.
    """
    user_id = update.effective_user.id

    # Get user from database
    user = get_user(user_id)
    if not user:
        await update.message.reply_text(
            get_text("error_occurred", "en")
        )
        return

    user_lang = user.get("language", "en")
    user_timezone = user.get("timezone", "Europe/Belgrade")
    user_time_format = user.get("time_format", "24h")

    # Get all pending reminders
    reminders = get_user_reminders(user_id, status="pending")

    if not reminders:
        # No upcoming reminders
        await update.message.reply_text(
            get_text("list_empty", user_lang),
            parse_mode="Markdown"
        )
        return

    # Build message with reminders
    message_text = get_text("list_header", user_lang) + "\n"

    # Timezone for formatting
    tz = pytz.timezone(user_timezone)

    for index, reminder in enumerate(reminders, 1):
        reminder_id = reminder['id']
        reminder_text = reminder['message_text']
        scheduled_time_str = reminder['scheduled_time']

        # Parse scheduled_time from database (stored as local time naive datetime)
        # SQLite stores datetime as string
        try:
            if isinstance(scheduled_time_str, str):
                # Parse as naive datetime (no timezone)
                try:
                    scheduled_dt = datetime.fromisoformat(scheduled_time_str)
                except:
                    scheduled_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                scheduled_dt = scheduled_time_str

            # If naive datetime, treat it as local time (already in correct timezone)
            if scheduled_dt.tzinfo is None:
                scheduled_dt_local = tz.localize(scheduled_dt)
            else:
                scheduled_dt_local = scheduled_dt.astimezone(tz)

            # Format date and time
            date_str = scheduled_dt_local.strftime("%d.%m.%Y.")
            if user_time_format == "12h":
                time_str = scheduled_dt_local.strftime("%I:%M %p")
            else:
                time_str = scheduled_dt_local.strftime("%H:%M")

            # Add to message - use index for display, but keep database ID for deletion
            separator = "u" if user_lang == "sr-lat" else "at"
            message_text += f"\n{index}. {reminder_text}\n"
            message_text += f"   {date_str} {separator} {time_str}\n"

        except Exception as e:
            logger.error(f"Error formatting reminder {reminder['id']}: {e}", exc_info=True)
            message_text += f"\n{index}. {reminder_text}\n"
            message_text += f"   {scheduled_time_str}\n"

    # Create inline keyboard with Delete buttons
    # Use index (1, 2, 3...) in button text, but database ID in callback_data
    keyboard = []
    for index, reminder in enumerate(reminders, 1):
        button = InlineKeyboardButton(
            f"🗑️ Obriši #{index}" if user_lang == "sr-lat" else f"🗑️ Delete #{index}",
            callback_data=f"delete_{reminder['id']}"
        )
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send message
    await update.message.reply_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    logger.info(f"User {user_id} listed {len(reminders)} reminders")


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle delete button callback.
    Deletes a reminder and refreshes the list.
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("delete_"):
        return

    # Extract reminder_id
    try:
        reminder_id = int(callback_data.split("_")[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid delete callback data: {callback_data}")
        return

    user_id = update.effective_user.id

    # Get user from database
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    # Delete reminder (mark as cancelled)
    success = delete_reminder(reminder_id)

    if success:
        # Show confirmation
        await query.answer(
            get_text("reminder_deleted", user_lang),
            show_alert=False
        )

        # Refresh the list
        # Get updated reminders
        reminders = get_user_reminders(user_id, status="pending")

        if not reminders:
            # No more reminders
            await query.edit_message_text(
                get_text("list_empty", user_lang),
                parse_mode="Markdown"
            )
            logger.info(f"User {user_id} deleted last reminder")
            return

        # Rebuild message
        user_timezone = user.get("timezone", "Europe/Belgrade")
        user_time_format = user.get("time_format", "24h")

        message_text = get_text("list_header", user_lang) + "\n"
        tz = pytz.timezone(user_timezone)

        for index, reminder in enumerate(reminders, 1):
            reminder_id = reminder['id']
            reminder_text = reminder['message_text']
            scheduled_time_str = reminder['scheduled_time']

            try:
                if isinstance(scheduled_time_str, str):
                    try:
                        scheduled_dt = datetime.fromisoformat(scheduled_time_str)
                    except:
                        scheduled_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M:%S")
                else:
                    scheduled_dt = scheduled_time_str

                # If naive datetime, treat it as local time (already in correct timezone)
                if scheduled_dt.tzinfo is None:
                    scheduled_dt_local = tz.localize(scheduled_dt)
                else:
                    scheduled_dt_local = scheduled_dt.astimezone(tz)

                date_str = scheduled_dt_local.strftime("%d.%m.%Y.")
                if user_time_format == "12h":
                    time_str = scheduled_dt_local.strftime("%I:%M %p")
                else:
                    time_str = scheduled_dt_local.strftime("%H:%M")

                separator = "u" if user_lang == "sr-lat" else "at"
                message_text += f"\n{index}. {reminder_text}\n"
                message_text += f"   {date_str} {separator} {time_str}\n"

            except Exception as e:
                logger.error(f"Error formatting reminder {reminder['id']}: {e}", exc_info=True)
                message_text += f"\n{index}. {reminder_text}\n"
                message_text += f"   {scheduled_time_str}\n"

        # Rebuild keyboard - use index for button text, database ID for callback
        keyboard = []
        for index, reminder in enumerate(reminders, 1):
            button = InlineKeyboardButton(
                f"🗑️ Obriši #{index}" if user_lang == "sr-lat" else f"🗑️ Delete #{index}",
                callback_data=f"delete_{reminder['id']}"
            )
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update message
        await query.edit_message_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        logger.info(f"User {user_id} deleted reminder {reminder_id}")

    else:
        await query.answer(
            get_text("error_occurred", user_lang),
            show_alert=True
        )


def register_handlers(application):
    """
    Register list and delete handlers.
    """
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete_"))
