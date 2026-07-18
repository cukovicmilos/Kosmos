"""
Recurring reminder handler for Kosmos Telegram Bot.
Handles /recurring command with conversation flow for creating recurring reminders.
"""

import json
import logging
from datetime import datetime, timedelta
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
from telegram.helpers import escape_markdown

from database import create_reminder, get_user
from i18n import get_text, WEEKDAY_SHORT_KEYS, WEEKDAY_NAME_KEYS
from parsers.time_parser import parse_time
from scheduler import calculate_first_occurrence

logger = logging.getLogger(__name__)

# Conversation states
(
    MESSAGE,
    RECURRENCE_TYPE,
    INTERVAL_DAYS,
    WEEKLY_DAYS,
    MONTHLY_DAY,
    TIME_INPUT,
    DURATION_CHOICE,
    DURATION_INPUT,
    CONFIRM
) = range(9)

# Ordered weekday/i18n-key pairs for the selection keyboard
WEEKDAY_KEYS = [(day, WEEKDAY_SHORT_KEYS[day]) for day in (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
)]


def _get_user_language(user_id: int) -> str:
    """Get the user's language preference (defaults to English)."""
    user = get_user(user_id)
    return user.get("language", "en") if user else "en"


def _localize_days(day_names, language: str) -> str:
    """Convert internal weekday names to a localized comma-separated list."""
    return ', '.join(
        get_text(WEEKDAY_NAME_KEYS.get(day, "weekday_name_mon"), language)
        for day in day_names
    )


async def recurring_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start the recurring reminder creation conversation.
    """
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text(get_text("recurring_need_start", "en"))
        return ConversationHandler.END

    user_lang = user.get('language', 'en')

    # Initialize conversation data
    context.user_data['recurring'] = {}

    await update.message.reply_text(
        get_text("recurring_prompt_message", user_lang),
        parse_mode="Markdown"
    )

    return MESSAGE


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle reminder message text input.
    """
    user_lang = _get_user_language(update.effective_user.id)
    message_text = update.message.text.strip()

    if not message_text:
        await update.message.reply_text(get_text("recurring_empty_message", user_lang))
        return MESSAGE

    # Save message to context
    context.user_data['recurring']['message'] = message_text

    # Show recurrence type options with cancel button
    keyboard = [
        [
            InlineKeyboardButton(get_text("rec_type_daily_button", user_lang), callback_data="rec_type_daily"),
            InlineKeyboardButton(get_text("rec_type_interval_button", user_lang), callback_data="rec_type_interval"),
        ],
        [
            InlineKeyboardButton(get_text("rec_type_weekly_button", user_lang), callback_data="rec_type_weekly"),
            InlineKeyboardButton(get_text("rec_type_monthly_button", user_lang), callback_data="rec_type_monthly"),
        ],
        [
            InlineKeyboardButton(get_text("cancel_button", user_lang), callback_data="rec_type_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    safe_text = escape_markdown(message_text, version=1)
    await update.message.reply_text(
        get_text("recurring_choose_type", user_lang, message_text=safe_text),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return RECURRENCE_TYPE


async def handle_recurrence_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle recurrence type selection.
    """
    query = update.callback_query
    await query.answer()

    user_lang = _get_user_language(update.effective_user.id)
    rec_type = query.data.replace("rec_type_", "")

    if rec_type == "cancel":
        await query.edit_message_text(get_text("recurring_cancelled", user_lang))
        context.user_data.pop('recurring', None)
        return ConversationHandler.END

    context.user_data['recurring']['type'] = rec_type

    type_set_text = get_text(
        "recurring_type_set", user_lang,
        type_label=get_text(f"rec_type_label_{rec_type}", user_lang)
    )

    if rec_type == "daily":
        # Go directly to time input
        await query.edit_message_text(
            type_set_text + get_text("recurring_time_prompt", user_lang),
            parse_mode="Markdown"
        )
        return TIME_INPUT

    elif rec_type == "interval":
        # Ask for number of days
        await query.edit_message_text(
            type_set_text + get_text("recurring_interval_prompt", user_lang),
            parse_mode="Markdown"
        )
        return INTERVAL_DAYS

    elif rec_type == "weekly":
        # Show day selection
        context.user_data['recurring']['selected_days'] = []
        reply_markup = InlineKeyboardMarkup(create_weekday_keyboard([], user_lang))

        await query.edit_message_text(
            type_set_text + get_text("recurring_select_days", user_lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return WEEKLY_DAYS

    elif rec_type == "monthly":
        # Ask for day of month
        await query.edit_message_text(
            type_set_text + get_text("recurring_monthly_prompt", user_lang),
            parse_mode="Markdown"
        )
        return MONTHLY_DAY


def create_weekday_keyboard(selected_days, language: str = "en"):
    """
    Create inline keyboard for weekday selection with checkmarks.
    """
    keyboard = []
    row = []

    for day, label_key in WEEKDAY_KEYS:
        checkmark = "✓ " if day in selected_days else ""
        button = InlineKeyboardButton(
            f"{checkmark}{get_text(label_key, language)}",
            callback_data=f"weekday_{day}"
        )
        row.append(button)

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Add "Done" and "Cancel" buttons
    keyboard.append([
        InlineKeyboardButton(get_text("done_button", language), callback_data="weekday_done"),
        InlineKeyboardButton(get_text("cancel_button", language), callback_data="weekday_cancel"),
    ])

    return keyboard


async def handle_weekday_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle weekday toggle selection.
    """
    query = update.callback_query
    await query.answer()

    user_lang = _get_user_language(update.effective_user.id)

    if query.data == "weekday_cancel":
        await query.edit_message_text(get_text("recurring_cancelled", user_lang))
        context.user_data.pop('recurring', None)
        return ConversationHandler.END

    if query.data == "weekday_done":
        selected_days = context.user_data['recurring'].get('selected_days', [])

        if not selected_days:
            await query.answer(get_text("recurring_select_one_day", user_lang), show_alert=True)
            return WEEKLY_DAYS

        # Save and proceed to time input
        await query.edit_message_text(
            get_text("recurring_days_set", user_lang, days=_localize_days(selected_days, user_lang)),
            parse_mode="Markdown"
        )
        return TIME_INPUT

    # Toggle day selection
    day = query.data.replace("weekday_", "")
    selected_days = context.user_data['recurring'].get('selected_days', [])

    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.append(day)

    context.user_data['recurring']['selected_days'] = selected_days

    # Update keyboard
    reply_markup = InlineKeyboardMarkup(create_weekday_keyboard(selected_days, user_lang))

    await query.edit_message_reply_markup(reply_markup=reply_markup)

    return WEEKLY_DAYS


async def handle_interval_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle interval days input.
    """
    user_lang = _get_user_language(update.effective_user.id)

    try:
        days = int(update.message.text.strip())

        if days < 1 or days > 365:
            await update.message.reply_text(get_text("recurring_interval_invalid", user_lang))
            return INTERVAL_DAYS

        context.user_data['recurring']['interval'] = days

        interval_label = get_text("recurring_interval_set", user_lang, days=days)
        await update.message.reply_text(
            f"✅ *{interval_label}*\n\n"
            + get_text("recurring_time_prompt", user_lang),
            parse_mode="Markdown"
        )
        return TIME_INPUT

    except ValueError:
        await update.message.reply_text(get_text("recurring_invalid_number", user_lang))
        return INTERVAL_DAYS


async def handle_monthly_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle monthly day input.
    """
    user_lang = _get_user_language(update.effective_user.id)

    try:
        day = int(update.message.text.strip())

        if day < 1 or day > 31:
            await update.message.reply_text(get_text("recurring_day_invalid", user_lang))
            return MONTHLY_DAY

        context.user_data['recurring']['day_of_month'] = day

        day_label = get_text("recurring_monthday_set", user_lang, day=day)
        await update.message.reply_text(
            f"✅ *{day_label}*\n\n"
            + get_text("recurring_time_prompt", user_lang),
            parse_mode="Markdown"
        )
        return TIME_INPUT

    except ValueError:
        await update.message.reply_text(get_text("recurring_invalid_number", user_lang))
        return MONTHLY_DAY


async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle time input and show duration choice.
    """
    time_str = update.message.text.strip()
    user_lang = _get_user_language(update.effective_user.id)

    # Parse time
    parsed_time = parse_time(time_str)

    if not parsed_time:
        await update.message.reply_text(get_text("recurring_time_invalid", user_lang))
        return TIME_INPUT

    context.user_data['recurring']['time'] = parsed_time

    # Show duration choice
    keyboard = [
        [
            InlineKeyboardButton(get_text("duration_forever_button", user_lang), callback_data="duration_forever"),
        ],
        [
            InlineKeyboardButton(get_text("duration_days_button", user_lang, days=7), callback_data="duration_7"),
            InlineKeyboardButton(get_text("duration_days_button", user_lang, days=14), callback_data="duration_14"),
        ],
        [
            InlineKeyboardButton(get_text("duration_days_button", user_lang, days=30), callback_data="duration_30"),
            InlineKeyboardButton(get_text("duration_custom_button", user_lang), callback_data="duration_custom"),
        ],
        [
            InlineKeyboardButton(get_text("cancel_button", user_lang), callback_data="duration_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    time_label = get_text("recurring_summary_time", user_lang, time=parsed_time.strftime('%H:%M'))
    await update.message.reply_text(
        f"✅ {time_label}\n\n" + get_text("recurring_duration_prompt", user_lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return DURATION_CHOICE


async def handle_duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle duration selection for recurring reminder.
    """
    query = update.callback_query
    await query.answer()

    user_lang = _get_user_language(update.effective_user.id)
    choice = query.data.replace("duration_", "")

    if choice == "cancel":
        await query.edit_message_text(get_text("recurring_cancelled", user_lang))
        context.user_data.pop('recurring', None)
        return ConversationHandler.END

    if choice == "custom":
        await query.edit_message_text(
            get_text("recurring_duration_custom_prompt", user_lang),
            parse_mode="Markdown"
        )
        return DURATION_INPUT

    if choice == "forever":
        context.user_data['recurring']['duration_days'] = None
    else:
        context.user_data['recurring']['duration_days'] = int(choice)

    return await _show_confirmation(query, context, user_lang)


async def handle_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle custom duration input (number of days).
    """
    user_lang = _get_user_language(update.effective_user.id)

    try:
        days = int(update.message.text.strip())

        if days < 1 or days > 365:
            await update.message.reply_text(get_text("recurring_interval_invalid", user_lang))
            return DURATION_INPUT

        context.user_data['recurring']['duration_days'] = days

        # Build and send confirmation summary
        rec_data = context.user_data['recurring']
        summary = _build_summary(rec_data, user_lang)

        reply_markup = _build_confirm_keyboard(user_lang)

        await update.message.reply_text(
            summary,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        return CONFIRM

    except ValueError:
        await update.message.reply_text(get_text("recurring_invalid_number", user_lang))
        return DURATION_INPUT


def _build_confirm_keyboard(language: str) -> InlineKeyboardMarkup:
    """Build the confirm/cancel keyboard for the final confirmation step."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text("confirm_yes_button", language), callback_data="confirm_yes"),
            InlineKeyboardButton(get_text("cancel_button", language), callback_data="confirm_no"),
        ]
    ])


def _build_summary(rec_data, language: str = "en"):
    """Build confirmation summary text from recurring data."""
    rec_type = rec_data['type']
    parsed_time = rec_data['time']

    summary_lines = [
        get_text("recurring_summary_title", language),
        get_text("recurring_summary_message", language, message=rec_data['message']),
        get_text("recurring_summary_time", language, time=parsed_time.strftime('%H:%M')),
    ]

    if rec_type == "daily":
        recurrence_desc = get_text("recurring_every_day", language)
    elif rec_type == "interval":
        recurrence_desc = get_text("recurring_every_x_days", language, days=rec_data['interval'])
    elif rec_type == "weekly":
        recurrence_desc = _localize_days(rec_data['selected_days'], language)
    elif rec_type == "monthly":
        recurrence_desc = get_text("recurring_monthly_desc", language, day=rec_data['day_of_month'])
    else:
        recurrence_desc = ""

    if recurrence_desc:
        summary_lines.append(
            get_text("recurring_summary_recurrence", language, recurrence=recurrence_desc)
        )

    duration_days = rec_data.get('duration_days')
    if duration_days:
        duration_desc = get_text("recurring_duration_days", language, days=duration_days)
    else:
        duration_desc = get_text("recurring_duration_forever", language)
    summary_lines.append(
        get_text("recurring_summary_duration", language, duration=duration_desc)
    )

    return '\n'.join(summary_lines)


async def _show_confirmation(query, context, user_lang: str):
    """Show confirmation summary after duration choice."""
    rec_data = context.user_data['recurring']
    summary = _build_summary(rec_data, user_lang)
    reply_markup = _build_confirm_keyboard(user_lang)

    await query.edit_message_text(
        summary,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return CONFIRM


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle confirmation and create the recurring reminder.
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_lang = _get_user_language(user_id)

    if query.data == "confirm_no":
        await query.edit_message_text(get_text("recurring_cancelled", user_lang))
        context.user_data.pop('recurring', None)
        return ConversationHandler.END

    # Create recurring reminder
    user = get_user(user_id)
    user_tz = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    rec_data = context.user_data['recurring']
    rec_type = rec_data['type']
    message = rec_data['message']
    reminder_time = rec_data['time']

    # Calculate first occurrence (using user's timezone)
    try:
        tz = pytz.timezone(user_tz)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)  # Naive datetime in user's timezone

    # First occurrence respects the recurrence configuration:
    # - interval: today if time is still in the future, otherwise +N days
    # - weekly: first selected weekday at the given time
    # - monthly: first date with the configured day of month
    # - daily: today or tomorrow
    scheduled_datetime = calculate_first_occurrence(
        rec_type,
        reminder_time,
        now,
        recurrence_interval=rec_data.get('interval'),
        recurrence_days=rec_data.get('selected_days'),
        recurrence_day_of_month=rec_data.get('day_of_month')
    )

    # Calculate end date if duration specified
    duration_days = rec_data.get('duration_days')
    recurrence_end_date = None
    if duration_days:
        recurrence_end_date = scheduled_datetime + timedelta(days=duration_days)

    # Prepare recurrence parameters
    recurrence_interval = None
    recurrence_days = None
    recurrence_day_of_month = None

    if rec_type == "interval":
        recurrence_interval = rec_data['interval']
    elif rec_type == "weekly":
        recurrence_days = json.dumps(rec_data['selected_days'])
    elif rec_type == "monthly":
        recurrence_day_of_month = rec_data['day_of_month']

    # Create reminder
    reminder_id = create_reminder(
        user_id=user_id,
        message_text=message,
        scheduled_time=scheduled_datetime,
        is_recurring=True,
        recurrence_type=rec_type,
        recurrence_interval=recurrence_interval,
        recurrence_days=recurrence_days,
        recurrence_day_of_month=recurrence_day_of_month,
        recurrence_end_date=recurrence_end_date
    )

    if reminder_id:
        next_time_str = scheduled_datetime.strftime('%d.%m.%Y u %H:%M')
        end_info = ""
        if recurrence_end_date:
            end_info = get_text(
                "recurring_created_end_info", user_lang,
                end_date=recurrence_end_date.strftime('%d.%m.%Y.')
            )
        await query.edit_message_text(
            get_text("recurring_created", user_lang, next_time=next_time_str, end_info=end_info),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(get_text("recurring_create_error", user_lang))

    # Clean up
    context.user_data.pop('recurring', None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel the conversation.
    """
    user_lang = _get_user_language(update.effective_user.id)
    await update.message.reply_text(get_text("recurring_cancelled", user_lang))
    context.user_data.pop('recurring', None)
    return ConversationHandler.END


def register_handlers(application):
    """
    Register recurring reminder handlers.
    """
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("recurring", recurring_command),
            MessageHandler(filters.Regex("^(🔁 Recurring|🔁 Ponavljajući)$"), recurring_command)
        ],
        states={
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            RECURRENCE_TYPE: [CallbackQueryHandler(handle_recurrence_type, pattern="^rec_type_")],
            INTERVAL_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interval_days)],
            WEEKLY_DAYS: [CallbackQueryHandler(handle_weekday_selection, pattern="^weekday_")],
            MONTHLY_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_monthly_day)],
            TIME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input)],
            DURATION_CHOICE: [CallbackQueryHandler(handle_duration_choice, pattern="^duration_")],
            DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duration_input)],
            CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
