"""
Quick reminder handler for Kosmos Telegram Bot.
Allows users to quickly create reminders from their most frequent reminder texts.
"""

import logging
from datetime import datetime
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

from database import create_reminder, get_user, get_frequent_reminder_texts
from i18n import get_text
from parsers.time_parser import parse_reminder, format_reminder_confirmation

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

    await query.edit_message_text(
        get_text("quick_when", user_lang, text=selected_text),
        parse_mode="Markdown"
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
    time_input = update.message.text.strip()

    # Combine reminder text with time input for parsing
    combined = f"{quick_text} {time_input}"
    result = parse_reminder(combined, user_timezone)

    if not result:
        await update.message.reply_text(
            get_text("quick_when", user_lang, text=quick_text),
            parse_mode="Markdown"
        )
        return ENTERING_TIME

    reminder_text, scheduled_time = result

    # Validate not in the past
    try:
        tz = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)

    if scheduled_time <= now:
        await update.message.reply_text(
            get_text("reminder_in_past", user_lang)
        )
        return ENTERING_TIME

    # Create reminder
    reminder_id = create_reminder(
        user_id=user_id,
        message_text=reminder_text,
        scheduled_time=scheduled_time
    )

    if reminder_id:
        confirmation_msg = format_reminder_confirmation(
            reminder_text, scheduled_time, user_time_format, now=now
        )
        await update.message.reply_text(confirmation_msg)
        logger.info(
            f"Quick reminder created: ID={reminder_id}, user={user_id}, "
            f"time={scheduled_time}, text='{reminder_text}'"
        )
    else:
        await update.message.reply_text(get_text("error_occurred", user_lang))

    # Clean up
    context.user_data.pop('quick_text', None)
    context.user_data.pop('quick_templates', None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the quick reminder conversation."""
    context.user_data.pop('quick_text', None)
    context.user_data.pop('quick_templates', None)

    user_id = update.effective_user.id
    user = get_user(user_id)
    user_lang = user.get('language', 'en') if user else 'en'

    if user_lang == "sr-lat":
        await update.message.reply_text("❌ Otkazano.")
    else:
        await update.message.reply_text("❌ Cancelled.")

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
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_entered)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
