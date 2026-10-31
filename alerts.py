"""
Admin alerts for Kosmos Telegram Bot.

Sends a message to ADMIN_CHAT_ID when Telegram polling keeps failing, and a
second message once the connection is quiet again. Startup is announced from
main.py. Process crashes are not covered here: systemd restarts the bot.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Bot
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import ContextTypes

from config import ADMIN_CHAT_ID, MAX_CONSECUTIVE_TIMEOUTS

logger = logging.getLogger(__name__)

# Failures further apart than this start a new streak
STREAK_GAP = timedelta(seconds=120)
# No polling failures for this long means the connection has recovered
RECOVERY_QUIET = timedelta(seconds=300)

_streak = 0
_last_failure: Optional[datetime] = None
_outage_alerted = False


def _now() -> datetime:
    return datetime.now()


async def notify_admin(bot: Bot, text: str) -> bool:
    """Send a message to the admin. Returns True if it was delivered."""
    if not ADMIN_CHAT_ID:
        return False
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
        logger.info("Admin alert sent")
        return True
    except Exception as e:
        logger.warning(f"Could not send admin alert: {e}")
        return False


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    """
    Application error handler. Polling failures arrive with update=None.
    Registering a handler disables PTB's default logging, so other errors are logged here.
    """
    global _streak, _last_failure, _outage_alerted

    error = context.error
    # BadRequest is a subclass of NetworkError in PTB, so exclude it explicitly
    is_polling_failure = (
        update is None
        and isinstance(error, (NetworkError, TimedOut))
        and not isinstance(error, BadRequest)
    )
    if not is_polling_failure:
        logger.error(f"Unhandled error: {error}", exc_info=error)
        return

    now = _now()
    if _last_failure is None or now - _last_failure > STREAK_GAP:
        _streak = 0
    _streak += 1
    _last_failure = now
    logger.warning(f"Telegram polling failure {_streak} in a row: {error}")

    if _streak >= MAX_CONSECUTIVE_TIMEOUTS and not _outage_alerted:
        sent = await notify_admin(
            context.bot,
            f"⚠️ Kosmos: {_streak} uzastopnih grešaka pri komunikaciji sa Telegramom.\n"
            f"Bot možda ne prima poruke.\nZadnja greška: {error}",
        )
        _outage_alerted = sent


async def check_polling_health(bot: Bot):
    """Periodic job: announce recovery once polling has been quiet long enough."""
    global _streak, _outage_alerted

    if not _outage_alerted or _last_failure is None:
        return
    if _now() - _last_failure < RECOVERY_QUIET:
        return

    if await notify_admin(bot, "✅ Kosmos: veza sa Telegramom je ponovo stabilna."):
        _streak = 0
        _outage_alerted = False
