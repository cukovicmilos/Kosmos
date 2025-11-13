"""
Help handler for Kosmos Telegram Bot.
Handles /help command and displays usage instructions.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from database import get_user
from i18n import get_text

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /help command.
    Shows comprehensive help message with examples and available commands.
    """
    user_id = update.effective_user.id

    # Get user's language preference
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    # Send help message
    await update.message.reply_text(
        get_text("help_message", user_lang),
        parse_mode="Markdown"
    )

    logger.info(f"User {user_id} requested help")


async def new_reminder_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle 'New Reminder' menu button.
    Displays instructions for creating a new reminder.
    """
    user_id = update.effective_user.id

    # Get user's language preference
    user = get_user(user_id)
    user_lang = user.get("language", "en") if user else "en"

    # Send reminder creation prompt
    await update.message.reply_text(
        get_text("new_reminder_prompt", user_lang),
        parse_mode="Markdown"
    )

    logger.info(f"User {user_id} requested new reminder prompt")


def register_handlers(application):
    """
    Register help command handlers.
    """
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("help", help_command))
