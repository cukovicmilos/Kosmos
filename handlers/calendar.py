"""
Calendar reminder handler for Kosmos Telegram Bot.
Handles /kalendar command and the 📅 main keyboard button.

Flow: "Šta?" (text) -> calendar (date) -> time -> confirmation.
Typing a reminder as a normal message remains the parallel path -
the calendar is an option, not a replacement.
"""

import logging
from datetime import datetime, date
import pytz
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from database import create_reminder, delete_reminder, get_user
from i18n import get_text
from parsers.time_parser import parse_reminders, format_reminder_confirmation
from message_queue import queue_message
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
from .start import get_main_keyboard

logger = logging.getLogger(__name__)

# Conversation states
ENTERING_TEXT, SHOWING_CALENDAR, WAITING_TIME = range(3)


def _cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear calendar flow data from user_data."""
    context.user_data.pop('cal_text', None)
    context.user_data.pop('cal_date', None)


async def kalendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the calendar reminder flow by asking for the reminder text."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Please start the bot first with /start")
        return ConversationHandler.END

    user_lang = user.get('language', 'en')
    await update.message.reply_text(get_text("calendar_what", user_lang))
    return ENTERING_TEXT


async def text_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the reminder text and show the calendar."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text(get_text("error_occurred", "en"))
        return ConversationHandler.END

    user_lang = user.get('language', 'en')
    user_timezone = user.get('timezone', 'Europe/Belgrade')

    reminder_text = update.message.text.strip()
    if not reminder_text:
        await update.message.reply_text(get_text("calendar_what", user_lang))
        return ENTERING_TEXT

    context.user_data['cal_text'] = reminder_text
    context.user_data.pop('cal_date', None)

    await update.message.reply_text(
        get_text("calendar_choose_date", user_lang),
        reply_markup=build_calendar_markup("new", user_lang, user_timezone)
    )
    return SHOWING_CALENDAR


async def calendar_date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection - ask for the time."""
    query = update.callback_query
    parsed = parse_date_callback(query.data)
    if not parsed or parsed[0] != "new":
        await query.answer()
        return SHOWING_CALENDAR

    _, selected_date = parsed
    await query.answer()

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    context.user_data['cal_date'] = (selected_date.year, selected_date.month, selected_date.day)
    reminder_text = context.user_data.get('cal_text', '')

    await query.edit_message_text(
        f"✏️ {reminder_text}\n\n"
        f"{get_text('calendar_time_prompt', user_lang, date=format_date_display(selected_date, user_lang))}"
    )
    return WAITING_TIME


async def calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ◀▶ month navigation - re-render the calendar in place."""
    query = update.callback_query
    parsed = parse_nav_callback(query.data)
    if not parsed or parsed[0] != "new":
        await query.answer()
        return SHOWING_CALENDAR

    _, year, month = parsed

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'
    user_timezone = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    if not nav_in_range(year, month, user_timezone):
        await query.answer()
        return SHOWING_CALENDAR

    await query.answer()
    await query.edit_message_reply_markup(
        reply_markup=build_calendar_markup("new", user_lang, user_timezone, year, month)
    )
    return SHOWING_CALENDAR


async def calendar_dead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toast for dead buttons (past days)."""
    query = update.callback_query
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'
    await query.answer(text=get_text("calendar_dead", user_lang), show_alert=False)
    return SHOWING_CALENDAR


async def calendar_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silently acknowledge decoration buttons (header, weekdays, padding)."""
    await update.callback_query.answer()
    return SHOWING_CALENDAR


async def calendar_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the calendar flow via the inline cancel button."""
    await update.callback_query.answer()
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'

    _cleanup(context)
    await update.callback_query.edit_message_text(get_text("calendar_cancelled", user_lang))
    return ConversationHandler.END


async def time_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse the entered time together with the selected date and create the reminder."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text(get_text("error_occurred", "en"))
        return ConversationHandler.END

    user_lang = user.get('language', 'en')
    user_timezone = user.get('timezone', 'Europe/Belgrade')
    user_time_format = user.get('time_format', '24h')

    reminder_text = context.user_data.get('cal_text', '')
    cal_date = context.user_data.get('cal_date')
    time_input = update.message.text.strip()

    # Combine text + selected date + typed time for the parser
    if cal_date:
        selected_date = date(*cal_date)
        combined = f"{reminder_text} {selected_date.day}.{selected_date.month}. {time_input}"
        date_display = format_date_display(selected_date, user_lang)
    else:
        combined = f"{reminder_text} {time_input}"
        date_display = ""

    results = parse_reminders(combined, user_timezone)

    if not results:
        await update.message.reply_text(
            get_text("calendar_time_prompt", user_lang, date=date_display)
        )
        return WAITING_TIME

    # Validate that scheduled times are not in the past (using user's timezone)
    try:
        tz = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)

    if any(scheduled_time <= now for _, scheduled_time in results):
        await update.message.reply_text(
            get_text("reminder_in_past", user_lang)
        )
        return WAITING_TIME

    created_ids = []
    for text, scheduled_time in results:
        reminder_id = create_reminder(
            user_id=user_id,
            message_text=text,
            scheduled_time=scheduled_time
        )
        if not reminder_id:
            for old_id in created_ids:
                delete_reminder(old_id)
            await update.message.reply_text(get_text("error_occurred", user_lang))
            _cleanup(context)
            return ConversationHandler.END
        created_ids.append(reminder_id)

    confirmation_msg = "\n".join(
        format_reminder_confirmation(text, scheduled, user_time_format, now=now)
        for text, scheduled in results
    )

    try:
        # Attach main keyboard so the persistent buttons self-heal
        await update.message.reply_text(
            confirmation_msg,
            reply_markup=get_main_keyboard(user_lang)
        )
        logger.info(
            f"Calendar reminders created: IDs={created_ids}, user={user_id}, "
            f"times={[scheduled for _, scheduled in results]}, text='{results[0][0]}'"
        )
    except Exception as e:
        logger.error(f"Error sending confirmation to user {user_id}, queuing for retry: {e}")
        queue_message(user_id, confirmation_msg, message_type='reminder_confirmation')

    _cleanup(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the calendar reminder conversation."""
    _cleanup(context)

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    await update.message.reply_text(get_text("calendar_cancelled", user_lang))
    return ConversationHandler.END


def register_handlers(application):
    """Register the /kalendar conversation handlers."""
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("kalendar", kalendar_command),
            MessageHandler(
                filters.Regex("^(📅 Kalendar|📅 Calendar|📅)$"), kalendar_command
            )
        ],
        states={
            ENTERING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_entered)
            ],
            SHOWING_CALENDAR: [
                CallbackQueryHandler(calendar_date_selected, pattern=DATE_PATTERN),
                CallbackQueryHandler(calendar_nav, pattern=NAV_PATTERN),
                CallbackQueryHandler(calendar_cancel, pattern=CANCEL_PATTERN),
                CallbackQueryHandler(calendar_dead, pattern=DEAD_PATTERN),
                CallbackQueryHandler(calendar_noop, pattern=NOOP_PATTERN),
            ],
            WAITING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_entered)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
