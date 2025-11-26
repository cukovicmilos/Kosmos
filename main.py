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

from config import (
    BOT_TOKEN, 
    setup_logging,
    TELEGRAM_CONNECT_TIMEOUT,
    TELEGRAM_READ_TIMEOUT,
    TELEGRAM_WRITE_TIMEOUT,
    TELEGRAM_POOL_TIMEOUT
)
from database import init_database
from handlers import start, help as help_handler, reminder, postpone, list_handler, settings, recurring, netstats
from scheduler import start_scheduler

# Try to import bot_stats for initial description update
try:
    from bot_stats import update_bot_short_description, update_bot_description
    BOT_STATS_AVAILABLE = True
except ImportError:
    BOT_STATS_AVAILABLE = False

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
        BotCommand("netstats", "Network statistics"),
        BotCommand("list", "View upcoming reminders"),
        BotCommand("recurring", "Create recurring reminder"),
        BotCommand("settings", "Change settings"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered")

    # Update bot descriptions with statistics on startup
    if BOT_STATS_AVAILABLE:
        try:
            await update_bot_short_description(application.bot)
            await update_bot_description(application.bot)
            logger.info("Bot descriptions updated with statistics")
        except Exception as e:
            logger.error(f"Failed to update bot descriptions: {e}")

    # Start the scheduler for checking and sending reminders
    start_scheduler(application.bot)
    logger.info("Reminder scheduler started")


def main():
    """Start the bot."""
    logger.info("Starting Kosmos Telegram Bot...")

    # Initialize database
    init_database()

    # Create application with custom timeout settings
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(TELEGRAM_CONNECT_TIMEOUT)
        .read_timeout(TELEGRAM_READ_TIMEOUT)
        .write_timeout(TELEGRAM_WRITE_TIMEOUT)
        .pool_timeout(TELEGRAM_POOL_TIMEOUT)
        .build()
    )
    
    logger.info(f"Bot configured with timeouts: connect={TELEGRAM_CONNECT_TIMEOUT}s, "
                f"read={TELEGRAM_READ_TIMEOUT}s, write={TELEGRAM_WRITE_TIMEOUT}s, "
                f"pool={TELEGRAM_POOL_TIMEOUT}s")

    # Register handlers from modules
    # Order matters! Commands should be registered before message handlers
    start.register_handlers(application)
    help_handler.register_handlers(application)
    netstats.register_handlers(application)  # Network statistics command
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
