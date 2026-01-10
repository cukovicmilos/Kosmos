"""
Start handler for Kosmos Telegram Bot.
Handles /start command and user initialization.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pytz

from database import create_user, get_user
from i18n import get_text
from config import TIMEZONE_OPTIONS

logger = logging.getLogger(__name__)


def get_main_keyboard(language: str = "en"):
    """
    Get the main reply keyboard with quick access buttons.

    Args:
        language: User's language preference

    Returns:
        ReplyKeyboardMarkup with persistent buttons
    """
    if language == "sr-lat":
        keyboard = [
            [KeyboardButton("🔁 Ponavljajući"), KeyboardButton("📋 Lista")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🔁 Recurring"), KeyboardButton("📋 List")],
        ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


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
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_lang)
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
    # Create inline keyboard with timezone options (2 per row) using TIMEZONE_OPTIONS from config
    keyboard = []
    for i in range(0, len(TIMEZONE_OPTIONS), 2):
        row = []
        for j in range(2):
            if i + j < len(TIMEZONE_OPTIONS):
                label, tz = TIMEZONE_OPTIONS[i + j]
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

        # Send main keyboard
        await query.message.reply_text(
            get_text("ready_to_use", user_lang),
            reply_markup=get_main_keyboard(user_lang)
        )

        logger.info(f"User {user_id} selected timezone: {timezone}")
    else:
        await query.edit_message_text(
            get_text("error_occurred", "en")
        )


async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle keyboard button presses (List).
    Note: Recurring button is handled by ConversationHandler in recurring.py
    """
    text = update.message.text
    user_id = update.effective_user.id

    # Get user language
    user = get_user(user_id)
    if not user:
        return

    user_lang = user.get("language", "en")

    # Route to appropriate handler based on button text
    if text in ["📋 List", "📋 Lista"]:
        # Import list handler to avoid circular import
        from . import list as list_handler
        await list_handler.list_command(update, context)


def register_handlers(application):
    """
    Register start command handlers.
    """
    from telegram.ext import CommandHandler, CallbackQueryHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(timezone_callback, pattern="^tz_"))

    # Handler for keyboard buttons - must be before generic text handler
    # Note: Recurring button is handled by ConversationHandler in recurring.py
    keyboard_filter = filters.Regex("^(📋 List|📋 Lista)$")
    application.add_handler(MessageHandler(keyboard_filter, handle_keyboard_buttons))
