"""
List handler for Kosmos Telegram Bot.
Displays all upcoming reminders with delete buttons.
"""

import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import pytz

from database import get_user_reminders, delete_reminder, get_user, get_reminder_by_id, update_reminder, parse_db_datetime
from parsers.time_parser import format_datetime, parse_reminder, format_reminder_confirmation
from i18n import get_text, WEEKDAY_SHORT_KEYS
from keyboards import build_delete_recurring_confirm_keyboard
from challenge_utils import challenge_elapsed_days
from telegram.helpers import escape_markdown
from telegram import ForceReply

logger = logging.getLogger(__name__)

# Conversation states for edit flow
AWAITING_EDIT_INPUT = 0


async def _cleanup_edit_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up edit-related state and delete the edit prompt message if present."""
    edit_prompt_message_id = context.user_data.get('edit_prompt_message_id')
    edit_prompt_chat_id = context.user_data.get('edit_prompt_chat_id')

    if edit_prompt_message_id and edit_prompt_chat_id:
        try:
            await context.bot.delete_message(
                chat_id=edit_prompt_chat_id,
                message_id=edit_prompt_message_id
            )
        except Exception as e:
            logger.debug(f"Could not delete edit prompt message: {e}")

    # Clear all edit-related state
    context.user_data.pop('editing_reminder_id', None)
    context.user_data.pop('edit_prompt_message_id', None)
    context.user_data.pop('edit_prompt_chat_id', None)


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
        return get_text("recurring_every_day", language)

    elif rec_type == 'interval':
        days = reminder.get('recurrence_interval', 1) or 1
        if days > 1:
            return get_text("recurring_every_x_days", language, days=days)
        return get_text("recurring_every_day", language)

    elif rec_type == 'weekly':
        days_json = reminder.get('recurrence_days')
        if not days_json:
            return ""

        try:
            days_list = json.loads(days_json)
        except (json.JSONDecodeError, TypeError):
            return ""

        day_names = [
            get_text(WEEKDAY_SHORT_KEYS[day.lower()], language)
            for day in days_list
            if isinstance(day, str) and day.lower() in WEEKDAY_SHORT_KEYS
        ]

        return ', '.join(day_names)

    elif rec_type == 'monthly':
        day_of_month = reminder.get('recurrence_day_of_month', 1)
        return get_text("recurring_monthly_desc", language, day=day_of_month)

    return ""


def build_reminder_list_message(
    reminders: list,
    user_lang: str,
    user_timezone: str,
    user_time_format: str
) -> tuple:
    """
    Build the reminder list message text and inline keyboard.

    Args:
        reminders: List of reminder dicts from database
        user_lang: User's language (en, sr-lat)
        user_timezone: User's timezone
        user_time_format: User's time format (12h, 24h)

    Returns:
        Tuple of (message_text, reply_markup)
    """
    message_text = get_text("list_header", user_lang) + "\n"

    # Timezone for formatting
    tz = pytz.timezone(user_timezone)

    for index, reminder in enumerate(reminders, 1):
        reminder_id = reminder['id']
        reminder_text = reminder['message_text']
        scheduled_time_str = reminder['scheduled_time']

        # Parse scheduled_time from database (stored as local time naive datetime)
        try:
            scheduled_dt = parse_db_datetime(scheduled_time_str)

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

            # Add to message
            separator = "u" if user_lang == "sr-lat" else "at"

            # Check if challenge / recurring and add icon + description
            is_challenge = reminder.get('is_challenge', 0)
            is_recurring = reminder.get('is_recurring', 0)
            if is_challenge:
                # Challenge: show 🎯 icon and progress counter (total/elapsed)
                total_days = reminder.get('challenge_total_days') or 1
                start_date = reminder.get('challenge_start_date')
                if start_date:
                    now = datetime.now(tz).replace(tzinfo=None)
                    elapsed = challenge_elapsed_days(start_date, now)
                    counter_info = f" ({total_days}/{min(elapsed, total_days)})"
                else:
                    counter_info = ""
                recurring_icon = "🎯 "
                recurrence_info = counter_info
            elif is_recurring:
                recurrence_desc = format_recurrence_description(reminder, user_lang)
                recurring_icon = "🔁 "
                recurrence_info = f" ({recurrence_desc})" if recurrence_desc else ""
            else:
                recurring_icon = ""
                recurrence_info = ""

            # Escape markdown characters in user text
            safe_reminder_text = escape_markdown(reminder_text, version=1)
            message_text += f"\n{index}. {recurring_icon}{safe_reminder_text}{recurrence_info}\n"
            message_text += f"   {date_str} {separator} {time_str}\n"

        except Exception as e:
            logger.error(f"Error formatting reminder {reminder['id']}: {e}", exc_info=True)
            safe_reminder_text = escape_markdown(reminder_text, version=1)
            message_text += f"\n{index}. {safe_reminder_text}\n"
            message_text += f"   {scheduled_time_str}\n"

    # Create compact inline keyboard with Delete and Edit buttons
    # Pack pairs [🗑️1] [✏️1] [🗑️2] [✏️2] per row (2 reminders per row = 4 buttons)
    keyboard = []
    row = []
    for index, reminder in enumerate(reminders, 1):
        row.append(InlineKeyboardButton(
            f"🗑️{index}",
            callback_data=f"delete_{reminder['id']}"
        ))
        row.append(InlineKeyboardButton(
            f"✏️{index}",
            callback_data=f"edit_{reminder['id']}"
        ))
        if len(row) >= 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    return message_text, reply_markup


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

    # Build message with reminders using helper function
    message_text, reply_markup = build_reminder_list_message(
        reminders, user_lang, user_timezone, user_time_format
    )

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
    reminder = get_reminder_by_id(reminder_id)

    if not reminder:
        await query.answer(get_text("error_occurred", user_lang), show_alert=True)
        return

    # Check if recurring
    is_recurring = reminder.get('is_recurring', 0)

    if is_recurring:
        # Show confirmation dialog for recurring reminders / challenges
        safe_text = escape_markdown(reminder['message_text'], version=1)
        reply_markup = build_delete_recurring_confirm_keyboard(reminder_id, user_lang)

        if reminder.get('is_challenge', 0):
            confirm_text = get_text("stop_challenge_confirm", user_lang, message_text=safe_text)
        else:
            confirm_text = get_text("stop_recurring_confirm", user_lang, message_text=safe_text)

        await query.edit_message_text(
            confirm_text,
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

        # Rebuild message using helper function
        user_timezone = user.get("timezone", "Europe/Belgrade")
        user_time_format = user.get("time_format", "24h")

        message_text, reply_markup = build_reminder_list_message(
            reminders, user_lang, user_timezone, user_time_format
        )

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

    # Check if it's a challenge for the appropriate confirmation message
    reminder = get_reminder_by_id(reminder_id)
    is_challenge = reminder.get('is_challenge', 0) if reminder else 0

    # Delete the recurring reminder
    success = delete_reminder(reminder_id)

    if success:
        await query.answer(
            get_text("challenge_deleted" if is_challenge else "recurring_deleted", user_lang),
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

        # Rebuild the list using helper function
        user_timezone = user.get("timezone", "Europe/Belgrade")
        user_time_format = user.get("time_format", "24h")

        message_text, reply_markup = build_reminder_list_message(
            reminders, user_lang, user_timezone, user_time_format
        )

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

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"
    user_timezone = user.get("timezone", "Europe/Belgrade")
    user_time_format = user.get("time_format", "24h")

    await query.answer(get_text("action_cancelled", user_lang))

    # Rebuild the list
    reminders = get_user_reminders(user_id, status="pending")

    if not reminders:
        await query.edit_message_text(
            get_text("list_empty", user_lang),
            parse_mode="Markdown"
        )
        return

    message_text, reply_markup = build_reminder_list_message(
        reminders, user_lang, user_timezone, user_time_format
    )

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle edit button callback (ConversationHandler entry point).
    Shows edit prompt with ForceReply to capture user's new text/time.
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("edit_"):
        return ConversationHandler.END

    # Extract reminder_id
    try:
        reminder_id = int(callback_data.split("_")[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid edit callback data: {callback_data}")
        return ConversationHandler.END

    user_id = update.effective_user.id

    # Get user from database
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    # Get reminder
    reminder = get_reminder_by_id(reminder_id)

    if not reminder:
        await query.answer(get_text("edit_not_found", user_lang), show_alert=True)
        return ConversationHandler.END

    # Check if reminder belongs to this user
    if reminder['user_id'] != user_id:
        logger.warning(f"User {user_id} tried to edit reminder {reminder_id} that doesn't belong to them")
        return ConversationHandler.END

    # Store reminder_id in user_data for the message handler
    context.user_data['editing_reminder_id'] = reminder_id

    # Send edit prompt with ForceReply
    reminder_text = reminder['message_text']
    prompt = get_text("edit_prompt", user_lang).format(reminder_text=reminder_text)

    edit_prompt_message = await query.message.reply_text(
        prompt,
        parse_mode="Markdown",
        reply_markup=ForceReply(selective=True)
    )

    # Store the edit prompt message ID so we can delete it after edit is complete
    context.user_data['edit_prompt_message_id'] = edit_prompt_message.message_id
    context.user_data['edit_prompt_chat_id'] = edit_prompt_message.chat_id

    logger.info(f"User {user_id} started editing reminder {reminder_id}")
    return AWAITING_EDIT_INPUT


async def edit_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle user's reply with new reminder text/time (ConversationHandler state handler).
    Parses input to determine if user wants to change text, time, or both.
    """
    import re

    user_id = update.effective_user.id

    # Get reminder_id from conversation state
    reminder_id = context.user_data.get('editing_reminder_id')
    if not reminder_id:
        await _cleanup_edit_state(context)
        return ConversationHandler.END

    # Get user settings
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"
    user_timezone = user.get("timezone", "Europe/Belgrade") if user else "Europe/Belgrade"
    user_time_format = user.get("time_format", "24h") if user else "24h"

    # Get reminder
    reminder = get_reminder_by_id(reminder_id)
    if not reminder or reminder['user_id'] != user_id:
        await update.message.reply_text(get_text("edit_not_found", user_lang))
        await _cleanup_edit_state(context)
        return ConversationHandler.END

    user_input = update.message.text.strip()

    # Try to parse input
    # Strategy:
    # 1. If input looks like only time (e.g., "15:00", "3pm", "tue 15:00"), update only time
    # 2. If input has text + time, update both
    # 3. If input has no recognizable time, update only text

    # Check if input is ONLY a time pattern (no other text)
    time_only_patterns = [
        r'^(\d{1,2}:\d{2})$',  # 15:00
        r'^(\d{1,2})\s*(am|pm)$',  # 3pm, 3 pm
        r'^(next|sl)\s+(pon|uto|sre|cet|čet|pet|sub|ned|mon|tue|wed|thu|fri|sat|sun)\s+\d{1,2}:\d{2}$',  # next tue 15:00
        r'^(pon|uto|sre|cet|čet|pet|sub|ned|mon|tue|wed|thu|fri|sat|sun)\s+\d{1,2}:\d{2}$',  # tue 15:00
        r'^(sutra|prekosutra|tomorrow|dat)\s+\d{1,2}:\d{2}$',  # tomorrow 15:00
    ]

    is_time_only = any(re.match(pattern, user_input, re.IGNORECASE) for pattern in time_only_patterns)

    new_text = None
    new_time = None

    if is_time_only:
        # User only provided time - keep original text, update time
        dummy_message = f"placeholder {user_input}"
        result = parse_reminder(dummy_message, user_timezone)
        if result:
            _, new_time = result
        else:
            await update.message.reply_text(get_text("edit_parse_error", user_lang))
            return AWAITING_EDIT_INPUT  # Keep in edit mode, let user retry
    else:
        # Try to parse as full reminder (text + time)
        result = parse_reminder(user_input, user_timezone)
        if result:
            new_text, new_time = result
        else:
            # No time found - treat entire input as new text only
            new_text = user_input
            new_time = None

    # Update reminder
    success = update_reminder(reminder_id, message_text=new_text, scheduled_time=new_time)

    if success:
        # Build confirmation message
        final_text = new_text if new_text else reminder['message_text']

        if new_time:
            # Use helper function for consistent confirmation formatting
            tz = pytz.timezone(user_timezone)
            now = datetime.now(tz).replace(tzinfo=None)
            confirmation = format_reminder_confirmation(
                final_text, new_time, user_time_format, now=now
            )
        else:
            # Only text was updated
            confirmation = f"✓ {final_text}"

        await update.message.reply_text(confirmation)
        logger.info(f"User {user_id} updated reminder {reminder_id}: text={new_text is not None}, time={new_time is not None}")
    else:
        await update.message.reply_text(get_text("error_occurred", user_lang))

    # Clean up edit state
    await _cleanup_edit_state(context)
    return ConversationHandler.END


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the edit operation."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    await update.message.reply_text(get_text("edit_cancelled", user_lang))
    await _cleanup_edit_state(context)
    logger.info(f"User {user_id} cancelled edit operation")
    return ConversationHandler.END


def register_handlers(application):
    """
    Register list, delete, and edit handlers.
    """
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CallbackQueryHandler(delete_confirm_callback, pattern="^delete_confirm_"))
    application.add_handler(CallbackQueryHandler(delete_cancel_callback, pattern="^delete_cancel_"))
    application.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete_[0-9]+$"))

    # ConversationHandler for edit flow
    edit_conversation_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_callback, pattern="^edit_[0-9]+$")
        ],
        states={
            AWAITING_EDIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_message_handler)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_edit),
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    application.add_handler(edit_conversation_handler)
