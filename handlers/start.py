"""
Start handler for Kosmos Telegram Bot.
Handles /start command and user initialization.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import pytz

from database import create_user, get_user
from i18n import get_text

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command.
    Creates user in database if new, or welcomes back existing user.
    """
    user = update.effective_user
    telegram_id = user.id
    username = user.username

    logger.info(f"User {telegram_id} (@{username}) started the bot")

    # Check if user already exists
    existing_user = get_user(telegram_id)

    if existing_user:
        # Existing user - welcome back
        user_lang = existing_user.get("language", "en")
        await update.message.reply_text(
            get_text("welcome_back", user_lang),
            parse_mode="Markdown"
        )
        logger.info(f"Existing user {telegram_id} returned")
    else:
        # New user - create and ask for timezone
        # Try to get timezone from Telegram (if available)
        user_timezone = None

        # Note: Telegram doesn't always provide timezone info
        # We'll ask the user to select one

        # For now, create user with default settings
        # Timezone will be selected in the next step
        create_user(
            telegram_id=telegram_id,
            username=username,
            language="en",  # Default language
            timezone="Europe/Belgrade"  # Will be updated if user selects different
        )

        # Send welcome message
        await update.message.reply_text(
            get_text("welcome_message", "en"),
            parse_mode="Markdown"
        )

        # Ask for timezone selection
        await ask_timezone_selection(update, context, "en")

        logger.info(f"New user {telegram_id} created")


async def ask_timezone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, language: str = "en"):
    """
    Ask user to select their timezone.
    Displays a list of common timezones.
    """
    # Common timezones organized by region
    timezones = [
        # Europe
        ("🇷🇸 Europe/Belgrade", "Europe/Belgrade"),
        ("🇬🇧 Europe/London", "Europe/London"),
        ("🇩🇪 Europe/Berlin", "Europe/Berlin"),
        ("🇫🇷 Europe/Paris", "Europe/Paris"),
        ("🇮🇹 Europe/Rome", "Europe/Rome"),
        ("🇪🇸 Europe/Madrid", "Europe/Madrid"),
        ("🇷🇺 Europe/Moscow", "Europe/Moscow"),
        # Americas
        ("🇺🇸 America/New_York", "America/New_York"),
        ("🇺🇸 America/Chicago", "America/Chicago"),
        ("🇺🇸 America/Denver", "America/Denver"),
        ("🇺🇸 America/Los_Angeles", "America/Los_Angeles"),
        ("🇨🇦 America/Toronto", "America/Toronto"),
        ("🇧🇷 America/Sao_Paulo", "America/Sao_Paulo"),
        # Asia
        ("🇨🇳 Asia/Shanghai", "Asia/Shanghai"),
        ("🇯🇵 Asia/Tokyo", "Asia/Tokyo"),
        ("🇮🇳 Asia/Kolkata", "Asia/Kolkata"),
        ("🇦🇪 Asia/Dubai", "Asia/Dubai"),
        # Australia
        ("🇦🇺 Australia/Sydney", "Australia/Sydney"),
        ("🇦🇺 Australia/Melbourne", "Australia/Melbourne"),
    ]

    # Create inline keyboard with timezone options (2 per row)
    keyboard = []
    for i in range(0, len(timezones), 2):
        row = []
        for j in range(2):
            if i + j < len(timezones):
                label, tz = timezones[i + j]
                row.append(InlineKeyboardButton(
                    label,
                    callback_data=f"tz_{tz}"
                ))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_text("timezone_question", language),
        reply_markup=reply_markup
    )


async def timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle timezone selection callback.
    """
    query = update.callback_query
    await query.answer()

    # Extract timezone from callback data
    callback_data = query.data
    if not callback_data.startswith("tz_"):
        return

    timezone = callback_data[3:]  # Remove "tz_" prefix
    user_id = update.effective_user.id

    # Update user's timezone in database
    from database import update_user_timezone
    success = update_user_timezone(user_id, timezone)

    if success:
        # Get user's language
        user = get_user(user_id)
        user_lang = user.get("language", "en") if user else "en"

        # Confirm timezone selection
        await query.edit_message_text(
            get_text("timezone_selected", user_lang, timezone=timezone)
        )
        logger.info(f"User {user_id} selected timezone: {timezone}")
    else:
        await query.edit_message_text(
            get_text("error_occurred", "en")
        )


def register_handlers(application):
    """
    Register start command handlers.
    """
    from telegram.ext import CommandHandler, CallbackQueryHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(timezone_callback, pattern="^tz_"))
