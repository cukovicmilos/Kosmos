"""
Settings handler for Kosmos Telegram Bot.
Allows users to configure language, time format, and timezone preferences.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database import get_user, update_user_language, update_user_time_format, update_user_timezone
from i18n import get_text

logger = logging.getLogger(__name__)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /settings command.
    Shows main settings menu with current preferences.
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
    user_time_format = user.get("time_format", "24h")
    user_timezone = user.get("timezone", "Europe/Belgrade")

    # Format current settings for display
    lang_display = "Srpski" if user_lang == "sr-lat" else "English"
    time_format_display = "AM/PM" if user_time_format == "12h" else "24h"

    # Build settings message
    message_text = get_text("settings_menu", user_lang,
                           lang_name=lang_display,
                           time_format=time_format_display,
                           timezone=user_timezone)

    # Create inline keyboard
    keyboard = [
        [InlineKeyboardButton(
            get_text("settings_language", user_lang),
            callback_data="settings_language"
        )],
        [InlineKeyboardButton(
            get_text("settings_time_format", user_lang),
            callback_data="settings_time_format"
        )],
        [InlineKeyboardButton(
            get_text("settings_timezone", user_lang),
            callback_data="settings_timezone"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    logger.info(f"User {user_id} opened settings")


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle settings menu callbacks.
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_id = update.effective_user.id

    # Get user from database
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    if callback_data == "settings_language":
        await show_language_selection(query, user_lang)
    elif callback_data == "settings_time_format":
        await show_time_format_selection(query, user_lang)
    elif callback_data == "settings_timezone":
        await show_timezone_selection(query, user_lang)
    elif callback_data.startswith("set_language_"):
        await set_language(query, callback_data, user_id)
    elif callback_data.startswith("set_time_format_"):
        await set_time_format(query, callback_data, user_id)
    elif callback_data.startswith("set_timezone_"):
        await set_timezone(query, callback_data, user_id)
    elif callback_data == "settings_back":
        await settings_command_callback(query, user_id)


async def show_language_selection(query, user_lang):
    """
    Show language selection menu.
    """
    message_text = get_text("select_language", user_lang)

    keyboard = [
        [InlineKeyboardButton(
            get_text("language_english", user_lang),
            callback_data="set_language_en"
        )],
        [InlineKeyboardButton(
            get_text("language_serbian", user_lang),
            callback_data="set_language_sr-lat"
        )],
        [InlineKeyboardButton(
            get_text("settings_back", user_lang),
            callback_data="settings_back"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def show_time_format_selection(query, user_lang):
    """
    Show time format selection menu.
    """
    message_text = get_text("select_time_format", user_lang)

    keyboard = [
        [InlineKeyboardButton(
            get_text("time_format_12h", user_lang),
            callback_data="set_time_format_12h"
        )],
        [InlineKeyboardButton(
            get_text("time_format_24h", user_lang),
            callback_data="set_time_format_24h"
        )],
        [InlineKeyboardButton(
            get_text("settings_back", user_lang),
            callback_data="settings_back"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def show_timezone_selection(query, user_lang):
    """
    Show timezone selection menu.
    """
    message_text = get_text("select_timezone", user_lang)

    # Common timezones
    timezones = [
        ("🇷🇸 Europe/Belgrade", "Europe/Belgrade"),
        ("🇬🇧 Europe/London", "Europe/London"),
        ("🇩🇪 Europe/Berlin", "Europe/Berlin"),
        ("🇫🇷 Europe/Paris", "Europe/Paris"),
        ("🇮🇹 Europe/Rome", "Europe/Rome"),
        ("🇪🇸 Europe/Madrid", "Europe/Madrid"),
        ("🇷🇺 Europe/Moscow", "Europe/Moscow"),
        ("🇺🇸 America/New_York", "America/New_York"),
        ("🇺🇸 America/Chicago", "America/Chicago"),
        ("🇺🇸 America/Los_Angeles", "America/Los_Angeles"),
        ("🇨🇦 America/Toronto", "America/Toronto"),
        ("🇧🇷 America/Sao_Paulo", "America/Sao_Paulo"),
        ("🇨🇳 Asia/Shanghai", "Asia/Shanghai"),
        ("🇯🇵 Asia/Tokyo", "Asia/Tokyo"),
        ("🇮🇳 Asia/Kolkata", "Asia/Kolkata"),
        ("🇦🇪 Asia/Dubai", "Asia/Dubai"),
        ("🇦🇺 Australia/Sydney", "Australia/Sydney"),
    ]

    # Create keyboard (2 per row)
    keyboard = []
    for i in range(0, len(timezones), 2):
        row = []
        for j in range(2):
            if i + j < len(timezones):
                label, tz = timezones[i + j]
                row.append(InlineKeyboardButton(
                    label,
                    callback_data=f"set_timezone_{tz}"
                ))
        keyboard.append(row)

    # Add back button
    keyboard.append([InlineKeyboardButton(
        get_text("settings_back", user_lang),
        callback_data="settings_back"
    )])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def set_language(query, callback_data, user_id):
    """
    Set user's language preference.
    """
    language = callback_data.split("_")[2]  # set_language_en -> en

    success = update_user_language(user_id, language)

    if success:
        # Get new language preference
        user = get_user(user_id)
        new_lang = user.get("language", "en") if user else language

        await query.edit_message_text(
            get_text("language_changed", new_lang)
        )
        logger.info(f"User {user_id} changed language to {language}")
    else:
        await query.edit_message_text(
            get_text("error_occurred", "en")
        )


async def set_time_format(query, callback_data, user_id):
    """
    Set user's time format preference.
    """
    time_format = callback_data.split("_")[3]  # set_time_format_12h -> 12h

    success = update_user_time_format(user_id, time_format)

    if success:
        # Get user's language
        user = get_user(user_id)
        user_lang = user.get("language", "en") if user else "en"

        format_display = "AM/PM" if time_format == "12h" else "24h"

        await query.edit_message_text(
            get_text("time_format_changed", user_lang, format=format_display)
        )
        logger.info(f"User {user_id} changed time format to {time_format}")
    else:
        user = get_user(user_id)
        user_lang = user.get("language", "en") if user else "en"
        await query.edit_message_text(
            get_text("error_occurred", user_lang)
        )


async def set_timezone(query, callback_data, user_id):
    """
    Set user's timezone preference.
    """
    timezone = callback_data.replace("set_timezone_", "")  # set_timezone_Europe/Belgrade

    success = update_user_timezone(user_id, timezone)

    if success:
        # Get user's language
        user = get_user(user_id)
        user_lang = user.get("language", "en") if user else "en"

        await query.edit_message_text(
            get_text("timezone_changed", user_lang, timezone=timezone)
        )
        logger.info(f"User {user_id} changed timezone to {timezone}")
    else:
        user = get_user(user_id)
        user_lang = user.get("language", "en") if user else "en"
        await query.edit_message_text(
            get_text("error_occurred", user_lang)
        )


async def settings_command_callback(query, user_id):
    """
    Show settings menu from callback (back button).
    """
    # Get user from database
    user = get_user(user_id)
    if not user:
        await query.edit_message_text(
            get_text("error_occurred", "en")
        )
        return

    user_lang = user.get("language", "en")
    user_time_format = user.get("time_format", "24h")
    user_timezone = user.get("timezone", "Europe/Belgrade")

    # Format current settings
    lang_display = "Srpski" if user_lang == "sr-lat" else "English"
    time_format_display = "AM/PM" if user_time_format == "12h" else "24h"

    message_text = get_text("settings_menu", user_lang,
                           lang_name=lang_display,
                           time_format=time_format_display,
                           timezone=user_timezone)

    # Create keyboard
    keyboard = [
        [InlineKeyboardButton(
            get_text("settings_language", user_lang),
            callback_data="settings_language"
        )],
        [InlineKeyboardButton(
            get_text("settings_time_format", user_lang),
            callback_data="settings_time_format"
        )],
        [InlineKeyboardButton(
            get_text("settings_timezone", user_lang),
            callback_data="settings_timezone"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


def register_handlers(application):
    """
    Register settings handlers.
    """
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings_"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_language_"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_time_format_"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_timezone_"))
