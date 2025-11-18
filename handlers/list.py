"""
List handler for Kosmos Telegram Bot.
Displays all upcoming reminders with delete buttons.
"""

import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import pytz

from database import get_user_reminders, delete_reminder, get_user
from parsers.time_parser import format_datetime
from i18n import get_text

logger = logging.getLogger(__name__)


def format_recurrence_description(reminder: dict, language: str = "en") -> str:
    """
    Format recurrence description for a recurring reminder.

    Args:
        reminder: Reminder dict with recurrence info
        language: User language (en, sr-lat)

    Returns:
        Formatted recurrence description or empty string if not recurring
    """
    if not reminder.get('is_recurring'):
        return ""

    rec_type = reminder.get('recurrence_type')

    if rec_type == 'daily':
        return "svaki dan" if language == "sr-lat" else "every day"

    elif rec_type == 'interval':
        days = reminder.get('recurrence_interval', 1)
        if language == "sr-lat":
            return f"svaka {days} dana" if days > 1 else "svaki dan"
        else:
            return f"every {days} days" if days > 1 else "every day"

    elif rec_type == 'weekly':
        days_json = reminder.get('recurrence_days')
        if not days_json:
            return ""

        try:
            days_list = json.loads(days_json)
        except (json.JSONDecodeError, TypeError):
            return ""

        # Map day names to localized versions
        if language == "sr-lat":
            day_map = {
                'monday': 'Pon', 'tuesday': 'Uto', 'wednesday': 'Sre',
                'thursday': 'Čet', 'friday': 'Pet', 'saturday': 'Sub', 'sunday': 'Ned'
            }
        else:
            day_map = {
                'monday': 'Mon', 'tuesday': 'Tue', 'wednesday': 'Wed',
                'thursday': 'Thu', 'friday': 'Fri', 'saturday': 'Sat', 'sunday': 'Sun'
            }

        day_names = [day_map.get(day.lower(), day) for day in days_list if day.lower() in day_map]
        days_str = ', '.join(day_names)

        return days_str if days_str else ""

    elif rec_type == 'monthly':
        day_of_month = reminder.get('recurrence_day_of_month', 1)
        if language == "sr-lat":
            return f"svakog {day_of_month}. u mesecu"
        else:
            suffix = 'th'
            if day_of_month % 10 == 1 and day_of_month != 11:
                suffix = 'st'
            elif day_of_month % 10 == 2 and day_of_month != 12:
                suffix = 'nd'
            elif day_of_month % 10 == 3 and day_of_month != 13:
                suffix = 'rd'
            return f"every {day_of_month}{suffix} of month"

    return ""


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

            # Check if recurring and add icon + description
            is_recurring = reminder.get('is_recurring', 0)
            if is_recurring:
                recurrence_desc = format_recurrence_description(reminder, user_lang)
                recurring_icon = "🔁 "
                recurrence_info = f" ({recurrence_desc})" if recurrence_desc else ""
            else:
                recurring_icon = ""
                recurrence_info = ""

            message_text += f"\n{index}. {recurring_icon}{reminder_text}{recurrence_info}\n"
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
    For recurring reminders, shows confirmation dialog.
    For one-time reminders, deletes immediately.
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

    # Get reminder to check if it's recurring
    from database import get_reminder_by_id
    reminder = get_reminder_by_id(reminder_id)

    if not reminder:
        await query.answer(get_text("error_occurred", user_lang), show_alert=True)
        return

    # Check if recurring
    is_recurring = reminder.get('is_recurring', 0)

    if is_recurring:
        # Show confirmation dialog for recurring reminders
        confirmation_text = (
            "🔁 *Ponavljajući podsetnik*\n\n"
            "Želiš li da trajno obrišeš ovaj ponavljajući podsetnik?"
            if user_lang == "sr-lat" else
            "🔁 *Recurring Reminder*\n\n"
            "Do you want to permanently delete this recurring reminder?"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🗑️ Obriši zauvek" if user_lang == "sr-lat" else "🗑️ Delete Forever",
                    callback_data=f"delete_confirm_{reminder_id}"
                ),
                InlineKeyboardButton(
                    "❌ Otkaži" if user_lang == "sr-lat" else "❌ Cancel",
                    callback_data=f"delete_cancel_{reminder_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            confirmation_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # For one-time reminders, delete immediately
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

                # Check if recurring and add icon + description
                is_recurring = reminder.get('is_recurring', 0)
                if is_recurring:
                    recurrence_desc = format_recurrence_description(reminder, user_lang)
                    recurring_icon = "🔁 "
                    recurrence_info = f" ({recurrence_desc})" if recurrence_desc else ""
                else:
                    recurring_icon = ""
                    recurrence_info = ""

                message_text += f"\n{index}. {recurring_icon}{reminder_text}{recurrence_info}\n"
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


async def delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle delete confirmation for recurring reminders.
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("delete_confirm_"):
        return

    # Extract reminder_id
    try:
        reminder_id = int(callback_data.replace("delete_confirm_", ""))
    except (IndexError, ValueError):
        logger.error(f"Invalid delete_confirm callback data: {callback_data}")
        return

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    # Delete the recurring reminder
    success = delete_reminder(reminder_id)

    if success:
        await query.answer(
            "Ponavljajući podsetnik obrisan" if user_lang == "sr-lat" else "Recurring reminder deleted",
            show_alert=False
        )

        # Refresh the list
        reminders = get_user_reminders(user_id, status="pending")

        if not reminders:
            await query.edit_message_text(
                get_text("list_empty", user_lang),
                parse_mode="Markdown"
            )
            logger.info(f"User {user_id} deleted last recurring reminder")
            return

        # Rebuild the list (same code as in delete_callback)
        user_timezone = user.get("timezone", "Europe/Belgrade")
        user_time_format = user.get("time_format", "24h")
        message_text = get_text("list_header", user_lang) + "\n"
        tz = pytz.timezone(user_timezone)

        for index, reminder in enumerate(reminders, 1):
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

                is_recurring = reminder.get('is_recurring', 0)
                if is_recurring:
                    recurrence_desc = format_recurrence_description(reminder, user_lang)
                    recurring_icon = "🔁 "
                    recurrence_info = f" ({recurrence_desc})" if recurrence_desc else ""
                else:
                    recurring_icon = ""
                    recurrence_info = ""

                message_text += f"\n{index}. {recurring_icon}{reminder_text}{recurrence_info}\n"
                message_text += f"   {date_str} {separator} {time_str}\n"

            except Exception as e:
                logger.error(f"Error formatting reminder {reminder['id']}: {e}", exc_info=True)
                message_text += f"\n{index}. {reminder_text}\n"
                message_text += f"   {scheduled_time_str}\n"

        keyboard = []
        for index, reminder in enumerate(reminders, 1):
            button = InlineKeyboardButton(
                f"🗑️ Obriši #{index}" if user_lang == "sr-lat" else f"🗑️ Delete #{index}",
                callback_data=f"delete_{reminder['id']}"
            )
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        logger.info(f"User {user_id} confirmed deletion of recurring reminder {reminder_id}")
    else:
        await query.answer(get_text("error_occurred", user_lang), show_alert=True)


async def delete_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle delete cancellation - go back to the list.
    """
    query = update.callback_query
    await query.answer("Otkazano" if query.from_user.language_code == "sr" else "Cancelled")

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"
    user_timezone = user.get("timezone", "Europe/Belgrade")
    user_time_format = user.get("time_format", "24h")

    # Rebuild the list
    reminders = get_user_reminders(user_id, status="pending")

    if not reminders:
        await query.edit_message_text(
            get_text("list_empty", user_lang),
            parse_mode="Markdown"
        )
        return

    message_text = get_text("list_header", user_lang) + "\n"
    tz = pytz.timezone(user_timezone)

    for index, reminder in enumerate(reminders, 1):
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

            is_recurring = reminder.get('is_recurring', 0)
            if is_recurring:
                recurrence_desc = format_recurrence_description(reminder, user_lang)
                recurring_icon = "🔁 "
                recurrence_info = f" ({recurrence_desc})" if recurrence_desc else ""
            else:
                recurring_icon = ""
                recurrence_info = ""

            message_text += f"\n{index}. {recurring_icon}{reminder_text}{recurrence_info}\n"
            message_text += f"   {date_str} {separator} {time_str}\n"

        except Exception as e:
            logger.error(f"Error formatting reminder {reminder['id']}: {e}", exc_info=True)
            message_text += f"\n{index}. {reminder_text}\n"
            message_text += f"   {scheduled_time_str}\n"

    keyboard = []
    for index, reminder in enumerate(reminders, 1):
        button = InlineKeyboardButton(
            f"🗑️ Obriši #{index}" if user_lang == "sr-lat" else f"🗑️ Delete #{index}",
            callback_data=f"delete_{reminder['id']}"
        )
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


def register_handlers(application):
    """
    Register list and delete handlers.
    """
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CallbackQueryHandler(delete_confirm_callback, pattern="^delete_confirm_"))
    application.add_handler(CallbackQueryHandler(delete_cancel_callback, pattern="^delete_cancel_"))
    application.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete_[0-9]+$"))
