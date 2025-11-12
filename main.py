"""
Main entry point for Kosmos Telegram Bot.
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, setup_logging
from database import init_database

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🚀 Kosmos Bot is running!\n\n"
        "This is a test version. Full functionality coming soon!"
    )
    logger.info(f"User {update.effective_user.id} started the bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📖 *Kosmos Help*\n\n"
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "More features coming soon!",
        parse_mode="Markdown"
    )


def main():
    """Start the bot."""
    logger.info("Starting Kosmos Telegram Bot...")

    # Initialize database
    init_database()

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Bot started successfully!")

    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
