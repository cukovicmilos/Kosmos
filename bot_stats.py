"""
Bot statistics module for Kosmos Telegram Bot.
Handles dynamic bot description updates with active user statistics.
"""

import logging
from telegram import Bot
from database import get_monthly_active_users, get_peak_monthly_users, get_total_users

logger = logging.getLogger(__name__)


async def update_bot_short_description(bot: Bot):
    """
    Update bot's short description with current active user statistics.
    This runs periodically to show dynamic statistics.
    
    Args:
        bot: Telegram bot instance
    """
    try:
        # Get statistics
        monthly_active = get_monthly_active_users()
        peak_users = get_peak_monthly_users()
        total_users = get_total_users()
        
        # Choose which metric to display (prioritize monthly active, fallback to peak, then total)
        if monthly_active > 0:
            description = f"🤖 Aktivno korisnika (30 dana): {monthly_active}"
        elif peak_users > 0:
            description = f"🤖 Rekordni broj korisnika: {peak_users}"
        elif total_users > 0:
            description = f"🤖 Ukupno korisnika: {total_users}"
        else:
            description = "🤖 Telegram bot za podsetke i organizaciju"
        
        # Update short description
        await bot.set_my_short_description(short_description=description)
        
        logger.info(f"Bot short description updated: {description}")
        logger.debug(f"Stats - Monthly: {monthly_active}, Peak: {peak_users}, Total: {total_users}")
        
    except Exception as e:
        logger.error(f"Failed to update bot short description: {e}", exc_info=True)


async def update_bot_description(bot: Bot):
    """
    Update bot's full description with detailed statistics.
    This can be called less frequently than short description.
    
    Args:
        bot: Telegram bot instance
    """
    try:
        # Get statistics
        monthly_active = get_monthly_active_users()
        total_users = get_total_users()
        
        # Create full description with statistics
        description = f"""Dobrodošli u Kosmos Bot! 🚀

Organizujte svoje podsetke i zadatke sa lakoćom.

📊 Statistika:
• Aktivnih korisnika (30 dana): {monthly_active}
• Ukupno registrovanih: {total_users}

Komande:
/start - Započni korišćenje
/help - Pomoć i uputstva
/list - Pregled podseka
/recurring - Periodični podseci
/settings - Podešavanja

Napravljeno sa ❤️ za produktivnost"""
        
        await bot.set_my_description(description=description)
        
        logger.info(f"Bot full description updated with stats")
        
    except Exception as e:
        logger.error(f"Failed to update bot full description: {e}", exc_info=True)
