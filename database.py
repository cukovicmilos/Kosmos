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


def migrate_recurring_columns(cursor):
    """
    Migration function to add recurring reminder columns to existing reminders table.
    Checks if columns exist before adding them to prevent errors.
    """
    logger.info("Checking for recurring columns migration...")

    # Get existing columns
    cursor.execute("PRAGMA table_info(reminders)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = {
        'is_recurring': 'INTEGER DEFAULT 0',
        'recurrence_type': 'TEXT',
        'recurrence_interval': 'INTEGER',
        'recurrence_days': 'TEXT',
        'recurrence_day_of_month': 'INTEGER'
    }

    # Add missing columns
    for column_name, column_def in new_columns.items():
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE reminders ADD COLUMN {column_name} {column_def}")
                logger.info(f"Added column '{column_name}' to reminders table")
            except Exception as e:
                logger.error(f"Error adding column '{column_name}': {e}")
                raise
        else:
            logger.debug(f"Column '{column_name}' already exists, skipping")

    logger.info("Recurring columns migration completed")


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
                is_recurring INTEGER DEFAULT 0,
                recurrence_type TEXT,
                recurrence_interval INTEGER,
                recurrence_days TEXT,
                recurrence_day_of_month INTEGER,
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

        # Run migrations for recurring reminders feature
        migrate_recurring_columns(cursor)

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

def create_reminder(
    user_id: int,
    message_text: str,
    scheduled_time: datetime,
    is_recurring: bool = False,
    recurrence_type: Optional[str] = None,
    recurrence_interval: Optional[int] = None,
    recurrence_days: Optional[str] = None,
    recurrence_day_of_month: Optional[int] = None
) -> Optional[int]:
    """
    Create a new reminder (one-time or recurring).

    Args:
        user_id: Telegram user ID
        message_text: The reminder message
        scheduled_time: When to send the reminder (datetime object)
        is_recurring: Whether this is a recurring reminder
        recurrence_type: Type of recurrence ('daily', 'interval', 'weekly', 'monthly')
        recurrence_interval: For 'interval' type - number of days between occurrences
        recurrence_days: For 'weekly' type - JSON array of days (e.g., '["monday", "wednesday"]')
        recurrence_day_of_month: For 'monthly' type - day of month (1-31)

    Returns:
        Reminder ID if created successfully, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (
                    user_id, message_text, scheduled_time, status,
                    is_recurring, recurrence_type, recurrence_interval,
                    recurrence_days, recurrence_day_of_month
                )
                VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """, (
                user_id, message_text, scheduled_time,
                1 if is_recurring else 0, recurrence_type, recurrence_interval,
                recurrence_days, recurrence_day_of_month
            ))

            reminder_id = cursor.lastrowid
            recurring_info = f", recurring={recurrence_type}" if is_recurring else ""
            logger.info(f"Reminder created: ID={reminder_id}, user={user_id}, time={scheduled_time}{recurring_info}")
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
            # Use datetime.now() to get local time, which matches how scheduled_time is stored
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT r.*, u.timezone
                FROM reminders r
                JOIN users u ON r.user_id = u.telegram_id
                WHERE r.status = 'pending' AND datetime(r.scheduled_time) <= datetime(?)
                ORDER BY r.scheduled_time ASC
            """, (current_time,))

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


# ==================== STATISTICS OPERATIONS ====================

def get_monthly_active_users() -> int:
    """
    Get count of users who created at least one reminder in the last 30 days.

    Returns:
        Number of active users in the last month
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM reminders
                WHERE created_at >= datetime('now', '-30 days')
            """)
            row = cursor.fetchone()
            return row['active_users'] if row else 0
    except Exception as e:
        logger.error(f"Error getting monthly active users: {e}")
        return 0


def get_peak_monthly_users() -> int:
    """
    Get the highest number of unique users who created reminders in any single month.

    Returns:
        Peak number of users in a month
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(monthly_users) as peak_users
                FROM (
                    SELECT COUNT(DISTINCT user_id) as monthly_users
                    FROM reminders
                    WHERE created_at IS NOT NULL
                    GROUP BY strftime('%Y-%m', created_at)
                )
            """)
            row = cursor.fetchone()
            return row['peak_users'] if row and row['peak_users'] else 0
    except Exception as e:
        logger.error(f"Error getting peak monthly users: {e}")
        return 0


def get_total_users() -> int:
    """
    Get total number of registered users.

    Returns:
        Total number of users
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM users")
            row = cursor.fetchone()
            return row['total'] if row else 0
    except Exception as e:
        logger.error(f"Error getting total users: {e}")
        return 0


# Initialize database on module import
if __name__ == "__main__":
    # When run directly, initialize the database
    from config import setup_logging
    setup_logging()
    init_database()
    logger.info("Database module initialized")
