"""
Network statistics handler for Kosmos Telegram Bot.
Allows users to check network health and statistics.
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from network_monitor import get_network_stats, get_network_monitor

logger = logging.getLogger(__name__)


async def netstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /netstats command - show network statistics.
    """
    if not update.message:
        return

    # Get network statistics
    stats = get_network_stats()
    monitor = get_network_monitor()
    recent_history = monitor.get_recent_history(5)
    
    # Format statistics message
    message = "📊 **Network Statistics**\n\n"
    
    # Overall stats
    success_rate = stats['success_rate'] * 100
    message += f"**Success Rate:** {success_rate:.1f}%\n"
    message += f"**Total Successes:** {stats['total_successes']}\n"
    message += f"**Total Timeouts:** {stats['total_timeouts']}\n"
    message += f"**Consecutive Timeouts:** {stats['consecutive_timeouts']}\n"
    
    # Alert status
    if stats['alert_active']:
        message += f"\n⚠️ **ALERT ACTIVE** - {stats['consecutive_timeouts']} consecutive timeouts!\n"
    else:
        message += "\n✅ **Network Status:** OK\n"
    
    # Last timeout
    if stats['last_timeout_time']:
        message += f"**Last Timeout:** {stats['last_timeout_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    # Recent events
    if recent_history:
        message += "\n**Recent Events (last 5):**\n"
        for event in recent_history:
            event_type = "✅" if event['type'] == 'success' else "❌"
            timestamp = event['timestamp'].strftime('%H:%M:%S')
            operation = event.get('operation', 'unknown')
            message += f"{event_type} {timestamp} - {operation}\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")
    user_id = update.effective_user.id if update.effective_user else "unknown"
    logger.info(f"Network stats requested by user {user_id}")


def register_handlers(application: Application) -> None:
    """
    Register network statistics handlers with the application.
    
    Args:
        application: Telegram application instance
    """
    application.add_handler(CommandHandler("netstats", netstats_command))
    logger.info("Network statistics handlers registered")
