"""
Main entry point for Kosmos Telegram Bot.
"""

import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, setup_logging
from database import init_database
from handlers import start, help as help_handler, reminder, postpone, list_handler, settings, recurring
from scheduler import start_scheduler

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """
    Post-initialization hook to set up bot menu and commands.
    """
    # Set bot commands (shown in Telegram UI)
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("list", "View upcoming reminders"),
        BotCommand("recurring", "Create recurring reminder"),
        BotCommand("settings", "Change settings"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered")

    # Start the scheduler for checking and sending reminders
    start_scheduler(application.bot)
    logger.info("Reminder scheduler started")


def main():
    """Start the bot."""
    logger.info("Starting Kosmos Telegram Bot...")

    # Initialize database
    init_database()

    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Register handlers from modules
    # Order matters! Commands should be registered before message handlers
    start.register_handlers(application)
    help_handler.register_handlers(application)
    list_handler.register_handlers(application)  # List and delete commands
    settings.register_handlers(application)  # Settings command and callbacks
    recurring.register_handlers(application)  # Recurring reminder conversation
    postpone.register_handlers(application)  # Register postpone callbacks
    reminder.register_handlers(application)  # Must be last (catches all text messages)

    logger.info("All handlers registered successfully!")

    # Start polling
    logger.info("Bot started successfully! Polling for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
