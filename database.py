"""
Database module for Kosmos Telegram Bot.
Handles SQLite database connection and operations.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config import DB_FULL_PATH

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically commits and closes the connection.
    """
    conn = sqlite3.connect(DB_FULL_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_database():
    """
    Initialize database and create tables if they don't exist.
    """
    logger.info("Initializing database...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                time_format TEXT DEFAULT '24h',
                timezone TEXT DEFAULT 'Europe/Belgrade',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_user_status
            ON reminders(user_id, status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_scheduled_time
            ON reminders(scheduled_time, status)
        """)

        logger.info("Database initialized successfully")


# ==================== USER OPERATIONS ====================

def create_user(telegram_id: int, username: Optional[str] = None,
                language: str = "en", timezone: str = "Europe/Belgrade") -> bool:
    """
    Create a new user or update existing user.

    Args:
        telegram_id: Telegram user ID
        username: Telegram username
        language: User's preferred language (en, sr-lat)
        timezone: User's timezone

    Returns:
        True if user was created/updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (telegram_id, username, language, timezone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    language = excluded.language,
                    timezone = excluded.timezone
            """, (telegram_id, username, language, timezone))

            logger.info(f"User created/updated: {telegram_id} (@{username})")
            return True
    except Exception as e:
        logger.error(f"Error creating user {telegram_id}: {e}")
        return False


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user by Telegram ID.

    Args:
        telegram_id: Telegram user ID

    Returns:
        User data as dictionary or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting user {telegram_id}: {e}")
        return None


def update_user_language(telegram_id: int, language: str) -> bool:
    """Update user's language preference."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET language = ? WHERE telegram_id = ?",
                (language, telegram_id)
            )
            logger.info(f"User {telegram_id} language updated to {language}")
            return True
    except Exception as e:
        logger.error(f"Error updating language for user {telegram_id}: {e}")
        return False


def update_user_time_format(telegram_id: int, time_format: str) -> bool:
    """Update user's time format preference."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET time_format = ? WHERE telegram_id = ?",
                (time_format, telegram_id)
            )
            logger.info(f"User {telegram_id} time format updated to {time_format}")
            return True
    except Exception as e:
        logger.error(f"Error updating time format for user {telegram_id}: {e}")
        return False


def update_user_timezone(telegram_id: int, timezone: str) -> bool:
    """Update user's timezone."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET timezone = ? WHERE telegram_id = ?",
                (timezone, telegram_id)
            )
            logger.info(f"User {telegram_id} timezone updated to {timezone}")
            return True
    except Exception as e:
        logger.error(f"Error updating timezone for user {telegram_id}: {e}")
        return False


# ==================== REMINDER OPERATIONS ====================

def create_reminder(user_id: int, message_text: str, scheduled_time: datetime) -> Optional[int]:
    """
    Create a new reminder.

    Args:
        user_id: Telegram user ID
        message_text: The reminder message
        scheduled_time: When to send the reminder (datetime object)

    Returns:
        Reminder ID if created successfully, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (user_id, message_text, scheduled_time, status)
                VALUES (?, ?, ?, 'pending')
            """, (user_id, message_text, scheduled_time))

            reminder_id = cursor.lastrowid
            logger.info(f"Reminder created: ID={reminder_id}, user={user_id}, time={scheduled_time}")
            return reminder_id
    except Exception as e:
        logger.error(f"Error creating reminder for user {user_id}: {e}")
        return None


def get_user_reminders(user_id: int, status: str = "pending") -> List[Dict[str, Any]]:
    """
    Get all reminders for a user with specific status.

    Args:
        user_id: Telegram user ID
        status: Reminder status (pending, sent, cancelled)

    Returns:
        List of reminders as dictionaries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reminders
                WHERE user_id = ? AND status = ?
                ORDER BY scheduled_time ASC
            """, (user_id, status))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting reminders for user {user_id}: {e}")
        return []


def get_pending_reminders() -> List[Dict[str, Any]]:
    """
    Get all pending reminders that are due (scheduled_time <= now).

    Returns:
        List of reminders as dictionaries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, u.timezone
                FROM reminders r
                JOIN users u ON r.user_id = u.telegram_id
                WHERE r.status = 'pending' AND r.scheduled_time <= ?
                ORDER BY r.scheduled_time ASC
            """, (datetime.utcnow(),))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting pending reminders: {e}")
        return []


def update_reminder_status(reminder_id: int, status: str) -> bool:
    """
    Update reminder status.

    Args:
        reminder_id: Reminder ID
        status: New status (pending, sent, cancelled)

    Returns:
        True if updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id)
            )
            logger.info(f"Reminder {reminder_id} status updated to {status}")
            return True
    except Exception as e:
        logger.error(f"Error updating reminder {reminder_id}: {e}")
        return False


def update_reminder_time(reminder_id: int, new_scheduled_time: datetime) -> bool:
    """
    Update reminder scheduled time (for postpone feature).

    Args:
        reminder_id: Reminder ID
        new_scheduled_time: New scheduled time

    Returns:
        True if updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE reminders
                SET scheduled_time = ?, status = 'pending'
                WHERE id = ?
            """, (new_scheduled_time, reminder_id))
            logger.info(f"Reminder {reminder_id} rescheduled to {new_scheduled_time}")
            return True
    except Exception as e:
        logger.error(f"Error rescheduling reminder {reminder_id}: {e}")
        return False


def delete_reminder(reminder_id: int) -> bool:
    """
    Delete a reminder (mark as cancelled).

    Args:
        reminder_id: Reminder ID

    Returns:
        True if deleted successfully
    """
    return update_reminder_status(reminder_id, "cancelled")


def get_reminder_by_id(reminder_id: int) -> Optional[Dict[str, Any]]:
    """
    Get reminder by ID.

    Args:
        reminder_id: Reminder ID

    Returns:
        Reminder data as dictionary or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting reminder {reminder_id}: {e}")
        return None


# Initialize database on module import
if __name__ == "__main__":
    # When run directly, initialize the database
    from config import setup_logging
    setup_logging()
    init_database()
    logger.info("Database module initialized")
