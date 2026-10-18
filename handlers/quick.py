"""
Quick reminder handler for Kosmos Telegram Bot.
Allows users to quickly create reminders from their most frequent reminder texts.
"""

import logging
from datetime import datetime, date
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from database import create_reminder, delete_reminder, get_user, get_frequent_reminder_texts
from i18n import get_text
from parsers.time_parser import parse_reminders, format_reminder_confirmation
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
SELECTING_TEMPLATE, ENTERING_TIME = range(2)


async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the quick reminder flow by showing top frequent reminders."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Please start the bot first with /start")
        return ConversationHandler.END

    user_lang = user.get('language', 'en')

    # Get frequent reminder texts
    frequent_texts = get_frequent_reminder_texts(user_id)

    if not frequent_texts:
        await update.message.reply_text(
            get_text("quick_no_history", user_lang)
        )
        return ConversationHandler.END

    # Store texts in context for later reference
    context.user_data['quick_templates'] = frequent_texts

    # Build inline keyboard with frequent reminders
    keyboard = []
    for i, text in enumerate(frequent_texts):
        # Truncate long texts for button display
        display_text = text if len(text) <= 40 else text[:37] + "..."
        keyboard.append([
            InlineKeyboardButton(display_text, callback_data=f"quick_select_{i}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_text("quick_title", user_lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return SELECTING_TEMPLATE


async def template_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle template selection from inline keyboard."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    # Extract index from callback data
    index = int(query.data.replace("quick_select_", ""))
    templates = context.user_data.get('quick_templates', [])

    if index >= len(templates):
        await query.edit_message_text(get_text("error_occurred", user_lang))
        return ConversationHandler.END

    selected_text = templates[index]
    context.user_data['quick_text'] = selected_text
    context.user_data.pop('quick_cal_date', None)

    user_timezone = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    # Typing the time stays the parallel path - the calendar is an option
    await query.edit_message_text(
        get_text("quick_when", user_lang, text=selected_text),
        parse_mode="Markdown",
        reply_markup=build_calendar_markup("quick", user_lang, user_timezone)
    )

    return ENTERING_TIME


async def time_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse entered time and create the reminder."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text(get_text("error_occurred", "en"))
        return ConversationHandler.END

    user_lang = user.get('language', 'en')
    user_timezone = user.get('timezone', 'Europe/Belgrade')
    user_time_format = user.get('time_format', '24h')

    quick_text = context.user_data.get('quick_text', '')
    cal_date = context.user_data.get('quick_cal_date')
    time_input = update.message.text.strip()

    # Combine reminder text with (selected date +) time input for parsing
    if cal_date:
        selected_date = date(*cal_date)
        combined = f"{quick_text} {selected_date.day}.{selected_date.month}. {time_input}"
        date_display = format_date_display(selected_date, user_lang)
    else:
        combined = f"{quick_text} {time_input}"
        date_display = ""

    results = parse_reminders(combined, user_timezone)

    if not results:
        if cal_date:
            # Date was picked from the calendar, only the time was wrong
            await update.message.reply_text(
                get_text("calendar_time_prompt", user_lang, date=date_display),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                get_text("quick_when", user_lang, text=quick_text),
                parse_mode="Markdown"
            )
        return ENTERING_TIME

    # Validate not in the past
    try:
        tz = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)

    if any(scheduled_time <= now for _, scheduled_time in results):
        await update.message.reply_text(
            get_text("reminder_in_past", user_lang)
        )
        return ENTERING_TIME

    created_ids = []
    for reminder_text, scheduled_time in results:
        reminder_id = create_reminder(
            user_id=user_id,
            message_text=reminder_text,
            scheduled_time=scheduled_time
        )
        if not reminder_id:
            for old_id in created_ids:
                delete_reminder(old_id)
            await update.message.reply_text(get_text("error_occurred", user_lang))
            context.user_data.pop('quick_text', None)
            context.user_data.pop('quick_templates', None)
            context.user_data.pop('quick_cal_date', None)
            return ConversationHandler.END
        created_ids.append(reminder_id)

    confirmation_msg = "\n".join(
        format_reminder_confirmation(text, scheduled, user_time_format, now=now)
        for text, scheduled in results
    )
    await update.message.reply_text(confirmation_msg)
    logger.info(
        f"Quick reminders created: IDs={created_ids}, user={user_id}, "
        f"times={[scheduled for _, scheduled in results]}, text='{results[0][0]}'"
    )

    # Clean up
    context.user_data.pop('quick_text', None)
    context.user_data.pop('quick_templates', None)
    context.user_data.pop('quick_cal_date', None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the quick reminder conversation."""
    context.user_data.pop('quick_text', None)
    context.user_data.pop('quick_templates', None)
    context.user_data.pop('quick_cal_date', None)

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    if user_lang == "sr-lat":
        await update.message.reply_text("❌ Otkazano.")
    else:
        await update.message.reply_text("❌ Cancelled.")

    return ConversationHandler.END


async def calendar_date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection from the inline calendar - ask only for the time."""
    query = update.callback_query
    parsed = parse_date_callback(query.data)
    if not parsed or parsed[0] != "quick":
        await query.answer()
        return ENTERING_TIME

    _, selected_date = parsed
    await query.answer()

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    context.user_data['quick_cal_date'] = (selected_date.year, selected_date.month, selected_date.day)
    quick_text = context.user_data.get('quick_text', '')

    await query.edit_message_text(
        f"⚡ {quick_text}\n\n"
        f"{get_text('calendar_time_prompt', user_lang, date=format_date_display(selected_date, user_lang))}"
    )
    return ENTERING_TIME


async def calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ◀▶ month navigation - re-render the calendar in place."""
    query = update.callback_query
    parsed = parse_nav_callback(query.data)
    if not parsed or parsed[0] != "quick":
        await query.answer()
        return ENTERING_TIME

    _, year, month = parsed

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'
    user_timezone = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    if not nav_in_range(year, month, user_timezone):
        await query.answer()
        return ENTERING_TIME

    await query.answer()
    await query.edit_message_reply_markup(
        reply_markup=build_calendar_markup("quick", user_lang, user_timezone, year, month)
    )
    return ENTERING_TIME


async def calendar_dead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toast for dead buttons (past days)."""
    query = update.callback_query
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'
    await query.answer(text=get_text("calendar_dead", user_lang), show_alert=False)
    return ENTERING_TIME


async def calendar_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silently acknowledge decoration buttons (header, weekdays, padding)."""
    await update.callback_query.answer()
    return ENTERING_TIME


async def calendar_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the quick reminder flow via the inline calendar cancel button."""
    await update.callback_query.answer()
    user = get_user(update.effective_user.id)
    user_lang = user.get('language', 'en') if user else 'en'

    context.user_data.pop('quick_text', None)
    context.user_data.pop('quick_templates', None)
    context.user_data.pop('quick_cal_date', None)

    await update.callback_query.edit_message_text(get_text("calendar_cancelled", user_lang))
    return ConversationHandler.END


def register_handlers(application):
    """Register quick reminder handlers."""
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("quick", quick_command),
            MessageHandler(
                filters.Regex("^(⚡ Quick|⚡ Brzi)$"), quick_command
            )
        ],
        states={
            SELECTING_TEMPLATE: [
                CallbackQueryHandler(template_selected, pattern="^quick_select_")
            ],
            ENTERING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_entered),
                CallbackQueryHandler(calendar_date_selected, pattern=DATE_PATTERN),
                CallbackQueryHandler(calendar_nav, pattern=NAV_PATTERN),
                CallbackQueryHandler(calendar_cancel, pattern=CANCEL_PATTERN),
                CallbackQueryHandler(calendar_dead, pattern=DEAD_PATTERN),
                CallbackQueryHandler(calendar_noop, pattern=NOOP_PATTERN),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
