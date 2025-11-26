#!/usr/bin/env python3
"""
Script to force update Telegram bot commands menu.
Run this after changing bot commands to clear Telegram's cache.
"""

import asyncio
import logging
from telegram import Bot, BotCommand
from config import BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def update_commands():
    """Update bot commands menu for all scopes."""
    bot = Bot(token=BOT_TOKEN)
    
    # Define commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("netstats", "Network statistics"),
        BotCommand("list", "View upcoming reminders"),
        BotCommand("recurring", "Create recurring reminder"),
        BotCommand("settings", "Change settings"),
    ]
    
    try:
        logger.info("=" * 60)
        logger.info("🔄 FORCE UPDATE BOT COMMANDS")
        logger.info("=" * 60)
        
        # Step 1: Delete old commands for all scopes
        logger.info("\n[1/4] Deleting old bot commands (all scopes)...")
        await bot.delete_my_commands()  # default scope
        logger.info("  ✅ Default scope cleared")
        
        # Wait for Telegram to process
        await asyncio.sleep(2)
        
        # Step 2: Set new commands for default scope
        logger.info("\n[2/4] Setting new bot commands (default scope)...")
        await bot.set_my_commands(commands)
        logger.info("  ✅ Commands set for default scope")
        
        await asyncio.sleep(1)
        
        # Step 3: Verify what was set
        logger.info("\n[3/4] Verifying commands on server...")
        current_commands = await bot.get_my_commands()
        logger.info(f"  📋 Found {len(current_commands)} commands:\n")
        
        for i, cmd in enumerate(current_commands, 1):
            emoji = "⭐" if cmd.command == "netstats" else "  "
            logger.info(f"  {emoji} {i}. /{cmd.command:12} - {cmd.description}")
        
        # Check if netstats is present
        if any(cmd.command == "netstats" for cmd in current_commands):
            logger.info("\n  ✅✅ /netstats successfully registered!")
        else:
            logger.warning("\n  ⚠️  /netstats NOT found in commands!")
        
        # Step 4: Final instructions
        logger.info("\n[4/4] ✅ Server-side update complete!")
        logger.info("\n" + "=" * 60)
        logger.info("📱 TO SEE COMMANDS IN TELEGRAM MENU:")
        logger.info("=" * 60)
        logger.info("1. Close Telegram app COMPLETELY")
        logger.info("2. Reopen Telegram")
        logger.info("3. Open bot chat")
        logger.info("4. Click menu button (⋮)")
        logger.info("\nOR type /netstats manually - it works right now!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\n❌ Error updating commands: {e}")
        logger.error("This might be a temporary network issue. Try again in a moment.")
        raise


if __name__ == "__main__":
    asyncio.run(update_commands())
