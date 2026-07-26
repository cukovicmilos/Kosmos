"""
Challenge handler for Kosmos Telegram Bot.
Handles /challenge command with conversation flow for creating challenges.

A challenge is a daily recurring reminder with a fixed duration that sends
a progress counter (total/elapsed) and a text progress bar every day.
"""

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
from i18n import get_text
from parsers.time_parser import parse_time
from scheduler import calculate_first_occurrence

logger = logging.getLogger(__name__)

# Conversation states
(
    NAME,
    DURATION_CHOICE,
    DURATION_INPUT,
    TIME_INPUT,
    CONFIRM
) = range(5)

# Max challenge name length
MAX_NAME_LENGTH = 100

# Max challenge duration in days
MAX_DURATION_DAYS = 365


def _get_user_language(user_id: int) -> str:
    """Get the user's language preference (defaults to English)."""
    user = get_user(user_id)
    return user.get("language", "en") if user else "en"


async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start the challenge creation conversation.
    """
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text(get_text("recurring_need_start", "en"))
        return ConversationHandler.END

    user_lang = user.get('language', 'en')

    # Initialize conversation data
    context.user_data['challenge'] = {}

    await update.message.reply_text(
        get_text("challenge_prompt_name", user_lang),
        parse_mode="Markdown"
    )

    return NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle challenge name input.
    """
    user_lang = _get_user_language(update.effective_user.id)
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(get_text("challenge_empty_name", user_lang))
        return NAME

    if len(name) > MAX_NAME_LENGTH:
        await update.message.reply_text(get_text("challenge_name_too_long", user_lang))
        return NAME

    # Save name to context
    context.user_data['challenge']['name'] = name

    # Show duration choice
    keyboard = [
        [
            InlineKeyboardButton(get_text("challenge_duration_days_button", user_lang, days=7), callback_data="ch_duration_7"),
            InlineKeyboardButton(get_text("challenge_duration_days_button", user_lang, days=14), callback_data="ch_duration_14"),
            InlineKeyboardButton(get_text("challenge_duration_days_button", user_lang, days=30), callback_data="ch_duration_30"),
        ],
        [
            InlineKeyboardButton(get_text("challenge_duration_custom_button", user_lang), callback_data="ch_duration_custom"),
        ],
        [
            InlineKeyboardButton(get_text("cancel_button", user_lang), callback_data="ch_duration_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    safe_name = escape_markdown(name, version=1)
    await update.message.reply_text(
        get_text("challenge_duration_prompt", user_lang, name=safe_name),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return DURATION_CHOICE


async def handle_duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle duration preset selection.
    """
    query = update.callback_query
    await query.answer()

    user_lang = _get_user_language(update.effective_user.id)
    choice = query.data.replace("ch_duration_", "")

    if choice == "cancel":
        await query.edit_message_text(get_text("challenge_cancelled", user_lang))
        context.user_data.pop('challenge', None)
        return ConversationHandler.END

    if choice == "custom":
        await query.edit_message_text(
            get_text("challenge_duration_custom_prompt", user_lang),
            parse_mode="Markdown"
        )
        return DURATION_INPUT

    context.user_data['challenge']['total_days'] = int(choice)

    await query.edit_message_text(
        get_text("challenge_time_prompt", user_lang, days=int(choice)),
        parse_mode="Markdown"
    )
    return TIME_INPUT


async def handle_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle custom duration input (number of days).
    """
    user_lang = _get_user_language(update.effective_user.id)

    try:
        days = int(update.message.text.strip())

        if days < 1 or days > MAX_DURATION_DAYS:
            await update.message.reply_text(get_text("recurring_interval_invalid", user_lang))
            return DURATION_INPUT

        context.user_data['challenge']['total_days'] = days

        await update.message.reply_text(
            get_text("challenge_time_prompt", user_lang, days=days),
            parse_mode="Markdown"
        )
        return TIME_INPUT

    except ValueError:
        await update.message.reply_text(get_text("recurring_invalid_number", user_lang))
        return DURATION_INPUT


async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle time input and show confirmation.
    """
    time_str = update.message.text.strip()
    user_lang = _get_user_language(update.effective_user.id)

    # Parse time
    parsed_time = parse_time(time_str)

    if not parsed_time:
        await update.message.reply_text(get_text("recurring_time_invalid", user_lang))
        return TIME_INPUT

    context.user_data['challenge']['time'] = parsed_time

    # Build confirmation summary
    ch_data = context.user_data['challenge']
    safe_name = escape_markdown(ch_data['name'], version=1)
    summary = '\n'.join([
        get_text("challenge_summary_title", user_lang),
        get_text("challenge_summary_name", user_lang, name=safe_name),
        get_text("challenge_summary_duration", user_lang, days=ch_data['total_days']),
        get_text("recurring_summary_time", user_lang, time=parsed_time.strftime('%H:%M')),
    ])

    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text("confirm_yes_button", user_lang), callback_data="ch_confirm_yes"),
            InlineKeyboardButton(get_text("cancel_button", user_lang), callback_data="ch_confirm_no"),
        ]
    ])

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return CONFIRM


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle confirmation and create the challenge.
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_lang = _get_user_language(user_id)

    if query.data == "ch_confirm_no":
        await query.edit_message_text(get_text("challenge_cancelled", user_lang))
        context.user_data.pop('challenge', None)
        return ConversationHandler.END

    # Create challenge
    user = get_user(user_id)
    user_tz = user.get('timezone', 'Europe/Belgrade') if user else 'Europe/Belgrade'

    ch_data = context.user_data['challenge']
    name = ch_data['name']
    total_days = ch_data['total_days']
    reminder_time = ch_data['time']

    try:
        tz = pytz.timezone(user_tz)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)  # Naive datetime in user's timezone

    # First occurrence: today if time is still in the future, otherwise tomorrow
    scheduled_datetime = calculate_first_occurrence('daily', reminder_time, now)

    # Challenge counter starts from creation date (creation day = day 1)
    start_date = datetime.combine(now.date(), datetime.min.time())

    # Last notification fires on start_date + (total_days - 1) days
    end_date = datetime.combine(now.date(), reminder_time) + timedelta(days=total_days - 1)

    # Create challenge as daily recurring reminder with challenge metadata
    reminder_id = create_reminder(
        user_id=user_id,
        message_text=name,
        scheduled_time=scheduled_datetime,
        is_recurring=True,
        recurrence_type='daily',
        recurrence_end_date=end_date,
        is_challenge=True,
        challenge_total_days=total_days,
        challenge_start_date=start_date
    )

    if reminder_id:
        next_time_str = scheduled_datetime.strftime('%d.%m.%Y u %H:%M')
        await query.edit_message_text(
            get_text(
                "challenge_created", user_lang,
                next_time=next_time_str,
                end_date=end_date.strftime('%d.%m.%Y.'),
                total=total_days
            ),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(get_text("challenge_create_error", user_lang))

    # Clean up
    context.user_data.pop('challenge', None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel the conversation.
    """
    user_lang = _get_user_language(update.effective_user.id)
    await update.message.reply_text(get_text("challenge_cancelled", user_lang))
    context.user_data.pop('challenge', None)
    return ConversationHandler.END


def register_handlers(application):
    """
    Register challenge handlers.
    """
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("challenge", challenge_command),
            MessageHandler(filters.Regex("^(🎯 Challenge|🎯 Izazov)$"), challenge_command)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            DURATION_CHOICE: [CallbackQueryHandler(handle_duration_choice, pattern="^ch_duration_")],
            DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duration_input)],
            TIME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input)],
            CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^ch_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
