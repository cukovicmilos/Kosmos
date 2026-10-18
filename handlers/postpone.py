"""
Postpone handler for Kosmos Telegram Bot.
Handles postponing reminders when user clicks postpone buttons.
"""

import logging
from datetime import datetime, timedelta, date
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram.error import TelegramError
import pytz

from database import get_reminder_by_id, update_reminder_time, get_user, create_reminder, delete_reminder
from parsers.time_parser import parse_reminder, format_datetime, format_reminder_confirmation
from i18n import get_text
from keyboards import build_notification_keyboard, build_delete_recurring_confirm_keyboard, build_challenge_notification_keyboard
from challenge_utils import challenge_elapsed_days, build_challenge_message
from telegram.helpers import escape_markdown
from .calendar_ui import (
    build_calendar_markup,
    format_date_display,
    parse_date_callback,
    parse_nav_callback,
    nav_in_range,
    DATE_PATTERN,
    NAV_PATTERN,
    CANCEL_PATTERN,
    DEAD_PATTERN,
    NOOP_PATTERN,
)

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
        context.user_data.pop('postpone_cal_date', None)

        # Custom time opens the calendar instead of a bare text prompt -
        # typing the time stays the parallel path
        await query.edit_message_text(
            get_text("custom_time_prompt", user_lang),
            reply_markup=build_calendar_markup("postpone", user_lang, user_timezone)
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
    cal_date = context.user_data.get('postpone_cal_date')
    if cal_date:
        # Date was picked from the calendar, only the time is typed
        selected_date = date(*cal_date)
        dummy_message = f"reminder {selected_date.day}.{selected_date.month}. {time_input}"
        date_display = format_date_display(selected_date, user_lang)
    else:
        dummy_message = f"reminder {time_input}"
        date_display = ""

    try:
        result = parse_reminder(dummy_message, user_timezone)

        if not result:
            # Parsing failed
            if cal_date:
                await update.message.reply_text(
                    get_text("calendar_time_prompt", user_lang, date=date_display),
                    parse_mode="Markdown"
                )
            else:
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
    context.user_data.pop('postpone_cal_date', None)
    return ConversationHandler.END


async def cancel_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel custom time input conversation.
    """
    context.user_data.pop('postpone_reminder_id', None)
    context.user_data.pop('postpone_cal_date', None)
    return ConversationHandler.END


async def calendar_date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection from the inline calendar - ask only for the time."""
    query = update.callback_query
    parsed = parse_date_callback(query.data)
    if not parsed or parsed[0] != "postpone":
        await query.answer()
        return WAITING_CUSTOM_TIME

    if not context.user_data.get('postpone_reminder_id'):
        await query.answer()
        return ConversationHandler.END

    _, selected_date = parsed
    await query.answer()

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    context.user_data['postpone_cal_date'] = (selected_date.year, selected_date.month, selected_date.day)

    await query.edit_message_text(
        get_text("calendar_time_prompt", user_lang, date=format_date_display(selected_date, user_lang)),
        parse_mode="Markdown"
    )
    return WAITING_CUSTOM_TIME


async def calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ◀▶ month navigation - re-render the calendar in place."""
    query = update.callback_query
    parsed = parse_nav_callback(query.data)
    if not parsed or parsed[0] != "postpone":
        await query.answer()
        return WAITING_CUSTOM_TIME

    _, year, month = parsed

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'
    user_timezone = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    if not nav_in_range(year, month, user_timezone):
        await query.answer()
        return WAITING_CUSTOM_TIME

    await query.answer()
    await query.edit_message_reply_markup(
        reply_markup=build_calendar_markup("postpone", user_lang, user_timezone, year, month)
    )
    return WAITING_CUSTOM_TIME


async def calendar_dead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toast for dead buttons (past days)."""
    query = update.callback_query
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'
    await query.answer(text=get_text("calendar_dead", user_lang), show_alert=False)
    return WAITING_CUSTOM_TIME


async def calendar_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silently acknowledge decoration buttons (header, weekdays, padding)."""
    await update.callback_query.answer()
    return WAITING_CUSTOM_TIME


async def calendar_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the custom postpone flow via the inline calendar cancel button."""
    await update.callback_query.answer()
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'

    context.user_data.pop('postpone_reminder_id', None)
    context.user_data.pop('postpone_cal_date', None)

    await update.callback_query.edit_message_text(get_text("calendar_cancelled", user_lang))
    return ConversationHandler.END


def _get_user_language(user_id: int) -> str:
    """Get the user's language preference (defaults to English)."""
    user = get_user(user_id)
    return user.get("language", "en") if user else "en"


async def stop_recurring_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'Delete recurrence' button on fired recurring reminder."""
    query = update.callback_query
    await query.answer()

    reminder_id = int(query.data.replace("stop_recurring_", ""))
    user_id = update.effective_user.id
    user_lang = _get_user_language(user_id)

    reminder = get_reminder_by_id(reminder_id)
    if not reminder or reminder['user_id'] != user_id:
        await query.edit_message_text(get_text("reminder_not_found", user_lang))
        return

    reply_markup = build_delete_recurring_confirm_keyboard(
        reminder_id,
        user_lang,
        confirm_callback=f"stop_recurring_confirm_{reminder_id}",
        cancel_callback=f"stop_recurring_cancel_{reminder_id}"
    )

    safe_text = escape_markdown(reminder['message_text'], version=1)
    if reminder.get('is_challenge', 0):
        confirm_text = get_text("stop_challenge_confirm", user_lang, message_text=safe_text)
    else:
        confirm_text = get_text("stop_recurring_confirm", user_lang, message_text=safe_text)

    await query.edit_message_text(
        confirm_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def stop_recurring_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm deletion of recurring reminder from notification."""
    query = update.callback_query
    await query.answer()

    reminder_id = int(query.data.replace("stop_recurring_confirm_", ""))
    user_id = update.effective_user.id
    user_lang = _get_user_language(user_id)

    reminder = get_reminder_by_id(reminder_id)
    if not reminder or reminder['user_id'] != user_id:
        await query.edit_message_text(get_text("reminder_not_found", user_lang))
        return

    success = delete_reminder(reminder_id)
    if success:
        if reminder.get('is_challenge', 0):
            await query.edit_message_text(get_text("challenge_deleted", user_lang))
        else:
            await query.edit_message_text(get_text("recurring_deleted", user_lang))
        logger.info(f"User {user_id} stopped recurring reminder {reminder_id} from notification")
    else:
        await query.edit_message_text(get_text("delete_error", user_lang))


async def stop_recurring_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel deletion - restore original notification with buttons."""
    query = update.callback_query
    await query.answer()

    reminder_id = int(query.data.replace("stop_recurring_cancel_", ""))
    user_id = update.effective_user.id
    user_lang = _get_user_language(user_id)

    reminder = get_reminder_by_id(reminder_id)
    if not reminder or reminder['user_id'] != user_id:
        await query.edit_message_text(get_text("reminder_not_found", user_lang))
        return

    # Restore original notification with buttons
    if reminder.get('is_challenge', 0):
        # Restore challenge notification with current progress
        user = get_user(user_id)
        user_timezone = user.get("timezone", "Europe/Belgrade") if user else "Europe/Belgrade"
        try:
            tz = pytz.timezone(user_timezone)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone("Europe/Belgrade")
        now = datetime.now(tz).replace(tzinfo=None)

        total_days = reminder.get('challenge_total_days') or 1
        elapsed = challenge_elapsed_days(reminder.get('challenge_start_date') or now, now)
        notification_text = build_challenge_message(reminder['message_text'], elapsed, total_days, user_lang)
        reply_markup = build_challenge_notification_keyboard(reminder_id, user_lang)

        await query.edit_message_text(
            notification_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    safe_text = escape_markdown(reminder['message_text'], version=1)
    notification_text = f"🔁 {safe_text}"
    reply_markup = build_notification_keyboard(reminder_id, is_recurring=True, language=user_lang)

    await query.edit_message_text(
        notification_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


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
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_time_message),
                CallbackQueryHandler(calendar_date_selected, pattern=DATE_PATTERN),
                CallbackQueryHandler(calendar_nav, pattern=NAV_PATTERN),
                CallbackQueryHandler(calendar_cancel, pattern=CANCEL_PATTERN),
                CallbackQueryHandler(calendar_dead, pattern=DEAD_PATTERN),
                CallbackQueryHandler(calendar_noop, pattern=NOOP_PATTERN),
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

    # Register stop recurring handlers (delete recurring from notification)
    application.add_handler(
        CallbackQueryHandler(stop_recurring_callback, pattern=r"^stop_recurring_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(stop_recurring_confirm_callback, pattern=r"^stop_recurring_confirm_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(stop_recurring_cancel_callback, pattern=r"^stop_recurring_cancel_\d+$")
    )
