"""
Message queue module for Kosmos Telegram Bot.
Handles retry logic for failed message deliveries.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from telegram import Bot
from telegram.error import TelegramError, NetworkError, TimedOut

from database import get_db_connection
from network_monitor import record_network_timeout, record_network_success

logger = logging.getLogger(__name__)

# Exponential backoff delays in seconds: 30s, 1m, 2m, 5m, 10m
BACKOFF_DELAYS = [30, 60, 120, 300, 600]


def get_backoff_delay(retry_count: int) -> int:
    """
    Get the backoff delay for a given retry count.

    Args:
        retry_count: Current retry count (0-indexed)

    Returns:
        Delay in seconds before next retry
    """
    if retry_count >= len(BACKOFF_DELAYS):
        return BACKOFF_DELAYS[-1]  # Use max delay for retries beyond the list
    return BACKOFF_DELAYS[retry_count]


def should_retry_now(last_retry_at: Optional[str], retry_count: int) -> bool:
    """
    Check if enough time has passed since last retry based on exponential backoff.

    Args:
        last_retry_at: Timestamp of last retry (string or None)
        retry_count: Current retry count

    Returns:
        True if the message should be retried now
    """
    if last_retry_at is None:
        # Never retried, should try now
        return True

    try:
        last_retry = datetime.strptime(last_retry_at, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        # Invalid timestamp, retry now
        return True

    required_delay = get_backoff_delay(retry_count)
    elapsed = (datetime.now() - last_retry).total_seconds()

    return elapsed >= required_delay


def create_pending_message_table():
    """
    Create pending_messages table if it doesn't exist.
    Call this during database initialization.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    message_type TEXT DEFAULT 'reminder_confirmation',
                    parse_mode TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_retry_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_messages_user
                ON pending_messages(user_id, created_at)
            """)
            
            logger.info("Pending messages table created/verified")
            return True
    except Exception as e:
        logger.error(f"Error creating pending_messages table: {e}")
        return False


def queue_message(user_id: int, message_text: str, 
                  message_type: str = 'reminder_confirmation',
                  parse_mode: Optional[str] = None) -> Optional[int]:
    """
    Queue a message for retry delivery.
    
    Args:
        user_id: Telegram user ID
        message_text: Message text to send
        message_type: Type of message (reminder_confirmation, etc.)
        parse_mode: Telegram parse mode (Markdown, HTML, None)
    
    Returns:
        Message ID if queued successfully, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pending_messages (user_id, message_text, message_type, parse_mode)
                VALUES (?, ?, ?, ?)
            """, (user_id, message_text, message_type, parse_mode))
            
            message_id = cursor.lastrowid
            logger.info(f"Message queued for retry: ID={message_id}, user={user_id}")
            return message_id
    except Exception as e:
        logger.error(f"Error queuing message for user {user_id}: {e}")
        return None


def get_pending_messages(max_retries: int = 5) -> List[Dict[str, Any]]:
    """
    Get all pending messages that need to be sent.
    
    Args:
        max_retries: Maximum number of retry attempts
    
    Returns:
        List of pending messages as dictionaries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pending_messages
                WHERE retry_count < ?
                ORDER BY created_at ASC
            """, (max_retries,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting pending messages: {e}")
        return []


def update_retry_attempt(message_id: int) -> bool:
    """
    Update retry count and timestamp for a message.
    
    Args:
        message_id: Message ID
    
    Returns:
        True if updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pending_messages
                SET retry_count = retry_count + 1,
                    last_retry_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (message_id,))
            logger.debug(f"Message {message_id} retry count updated")
            return True
    except Exception as e:
        logger.error(f"Error updating retry attempt for message {message_id}: {e}")
        return False


def delete_pending_message(message_id: int) -> bool:
    """
    Delete a pending message after successful delivery.
    
    Args:
        message_id: Message ID
    
    Returns:
        True if deleted successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_messages WHERE id = ?", (message_id,))
            logger.info(f"Pending message {message_id} deleted after successful delivery")
            return True
    except Exception as e:
        logger.error(f"Error deleting pending message {message_id}: {e}")
        return False


async def process_pending_messages(bot: Bot):
    """
    Background task that processes pending messages and retries failed deliveries.
    Should be called periodically by the scheduler.
    """
    try:
        pending_messages = get_pending_messages()
        
        if not pending_messages:
            return
        
        logger.info(f"Found {len(pending_messages)} pending messages to process")
        
        for message in pending_messages:
            try:
                await send_pending_message(bot, message)
            except Exception as e:
                logger.error(f"Failed to process pending message {message['id']}: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error in process_pending_messages: {e}", exc_info=True)


async def send_pending_message(bot: Bot, message: Dict[str, Any]):
    """
    Attempt to send a pending message with exponential backoff.

    Args:
        bot: Telegram bot instance
        message: Message dict from database
    """
    message_id = message['id']
    user_id = message['user_id']
    message_text = message['message_text']
    parse_mode = message.get('parse_mode')
    retry_count = message['retry_count']
    last_retry_at = message.get('last_retry_at')

    # Check if enough time has passed since last retry (exponential backoff)
    if not should_retry_now(last_retry_at, retry_count):
        delay = get_backoff_delay(retry_count)
        logger.debug(f"Message {message_id} not ready for retry (backoff {delay}s, retry #{retry_count})")
        return  # Skip this message, will retry later

    try:
        # Attempt to send the message
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode=parse_mode
        )
        
        # Success - record and delete from queue
        record_network_success(f"pending_message_{message_id}")
        delete_pending_message(message_id)
        logger.info(f"Pending message {message_id} sent successfully to user {user_id} after {retry_count} retries")
    
    except (NetworkError, TimedOut) as e:
        # Network error - record timeout, update retry count and try again later
        record_network_timeout(f"pending_message_{message_id}", str(e))
        update_retry_attempt(message_id)
        logger.warning(f"Network error sending pending message {message_id} (retry {retry_count + 1}): {e}")
    
    except TelegramError as e:
        # Other Telegram error - might be user blocked bot, invalid chat, etc.
        # Still update retry count, but log as error
        update_retry_attempt(message_id)
        logger.error(f"Telegram error sending pending message {message_id} (retry {retry_count + 1}): {e}")
    
    except Exception as e:
        # Unexpected error
        update_retry_attempt(message_id)
        logger.error(f"Unexpected error sending pending message {message_id}: {e}", exc_info=True)


def cleanup_old_messages(days: int = 7):
    """
    Clean up old pending messages that failed after max retries.
    
    Args:
        days: Delete messages older than this many days
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                DELETE FROM pending_messages
                WHERE created_at < ? AND retry_count >= 5
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old pending messages")
            return True
    except Exception as e:
        logger.error(f"Error cleaning up old messages: {e}")
        return False
