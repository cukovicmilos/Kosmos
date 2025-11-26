#!/usr/bin/env python3
"""
Check bot information and commands from Telegram API.
Use this to verify what Telegram sees.
"""

import asyncio
import logging
from telegram import Bot
from config import BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


async def check_bot():
    """Check bot information."""
    bot = Bot(token=BOT_TOKEN)
    
    try:
        print("╔══════════════════════════════════════════════════════════╗")
        print("║           BOT INFORMATION & COMMANDS CHECK              ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        
        # Get bot info
        print("📱 Bot Info:")
        me = await bot.get_me()
        print(f"   Name: {me.first_name}")
        print(f"   Username: @{me.username}")
        print(f"   ID: {me.id}")
        print()
        
        # Get commands
        print("📋 Registered Commands:")
        commands = await bot.get_my_commands()
        
        if not commands:
            print("   ⚠️  No commands found!")
        else:
            print(f"   Total: {len(commands)} commands\n")
            
            for i, cmd in enumerate(commands, 1):
                is_netstats = cmd.command == "netstats"
                emoji = "⭐" if is_netstats else "  "
                status = "← NEW!" if is_netstats else ""
                print(f"   {emoji} {i}. /{cmd.command:12} - {cmd.description} {status}")
        
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Check if netstats is present
        if any(cmd.command == "netstats" for cmd in commands):
            print("✅ /netstats IS REGISTERED on Telegram server!")
            print()
            print("If you don't see it in menu:")
            print("  1. Close Telegram app completely")
            print("  2. Reopen Telegram")
            print("  3. Clear app cache (Settings → Data and Storage → Clear Cache)")
            print("  4. Or just type /netstats manually - it works!")
        else:
            print("❌ /netstats NOT found in commands!")
            print("   Run: python update_bot_commands.py")
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(check_bot())
