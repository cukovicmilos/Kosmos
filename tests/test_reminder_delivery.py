"""
Tests for reminder delivery: retry limit, give-up path and notification.

Uses a temporary SQLite database and a fake bot, so no Telegram or real
kosmos.db is touched.

Run from project root:
    venv/bin/python -m unittest discover -s tests -v
"""

import asyncio
import logging
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOT_TOKEN", "123456:test-token")

import pytz  # noqa: E402
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut  # noqa: E402

import database  # noqa: E402
from database import (  # noqa: E402
    create_reminder,
    create_user,
    get_pending_reminders,
    get_reminder_by_id,
    init_database,
    update_reminder,
    update_reminder_time,
)
from scheduler import send_reminder  # noqa: E402

logging.disable(logging.CRITICAL)

BELGRADE = pytz.timezone("Europe/Belgrade")
USER_ID = 42


class FakeBot:
    """Records sent messages. Raises queued exceptions on successive calls."""

    def __init__(self):
        self.calls = 0
        self.raise_next = []
        self.always_raise = None
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.calls += 1
        if self.always_raise is not None:
            raise self.always_raise
        if self.raise_next:
            raise self.raise_next.pop(0)
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


def run(coro):
    return asyncio.run(coro)


class DeliveryTestCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="kosmos_test_")
        self.db_file = Path(tmp) / "test.db"
        patcher = mock.patch.object(database, "DB_FULL_PATH", self.db_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        init_database()
        create_user(USER_ID, "tester", language="en", timezone="Europe/Belgrade")
        self.bot = FakeBot()

    def make_due_reminder(self, **kwargs):
        due_at = datetime.now(BELGRADE).replace(tzinfo=None) - timedelta(hours=1)
        return create_reminder(USER_ID, "Take meds", due_at, **kwargs)

    def due(self, reminder_id):
        for reminder in get_pending_reminders():
            if reminder["id"] == reminder_id:
                return reminder
        return None

    def attempt(self, reminder_id):
        reminder = self.due(reminder_id)
        self.assertIsNotNone(reminder, "reminder should be due for a send attempt")
        run(send_reminder(self.bot, reminder))


class ReminderRetryTests(DeliveryTestCase):

    def test_successful_one_time_reminder_is_marked_sent(self):
        rid = self.make_due_reminder()
        self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "sent")
        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("Take meds", self.bot.sent[0]["text"])

    def test_network_error_increments_retry_count_and_keeps_pending(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = NetworkError("down")

        self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["retry_count"], 1)

    def test_gives_up_after_limit_and_notifies_user(self):
        rid = self.make_due_reminder()
        with mock.patch("scheduler.REMINDER_MAX_RETRIES", 3):
            self.bot.always_raise = NetworkError("down")
            self.attempt(rid)
            self.attempt(rid)
            self.assertEqual(get_reminder_by_id(rid)["status"], "pending")

            # Third failed attempt reaches the limit; the notification goes through
            self.bot.always_raise = None
            self.bot.raise_next = [NetworkError("down")]
            self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["retry_count"], 3)
        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("couldn't deliver", self.bot.sent[0]["text"])
        self.assertIn("Take meds", self.bot.sent[0]["text"])
        self.assertIsNone(self.bot.sent[0]["parse_mode"])

    def test_failed_reminder_is_not_retried_again(self):
        rid = self.make_due_reminder()
        with mock.patch("scheduler.REMINDER_MAX_RETRIES", 1):
            self.bot.always_raise = NetworkError("down")
            self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "failed")
        self.assertIsNone(self.due(rid))

    def test_recovery_before_limit_delivers_and_closes(self):
        rid = self.make_due_reminder()
        with mock.patch("scheduler.REMINDER_MAX_RETRIES", 5):
            self.bot.always_raise = NetworkError("down")
            self.attempt(rid)
            self.bot.always_raise = None
            self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "sent")
        self.assertEqual(len(self.bot.sent), 1)

    def test_bad_request_gives_up_immediately(self):
        rid = self.make_due_reminder()
        # Markdown attempt and plain-text fallback both rejected (e.g. chat not found)
        self.bot.raise_next = [BadRequest("Chat not found"), BadRequest("Chat not found")]

        self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "failed")
        # 2 rejected sends + 1 notification attempt; no retry on later cycles
        self.assertEqual(self.bot.calls, 3)

    def test_forbidden_cancels_without_notification(self):
        rid = self.make_due_reminder()
        self.bot.raise_next = [Forbidden("bot was blocked by the user")]

        self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "cancelled")
        self.assertEqual(self.bot.sent, [])
        self.assertEqual(self.bot.calls, 1)

    def test_recurring_reminder_skips_occurrence_and_keeps_schedule(self):
        rid = self.make_due_reminder(is_recurring=True, recurrence_type="daily")
        original = get_reminder_by_id(rid)["scheduled_time"]
        with mock.patch("scheduler.REMINDER_MAX_RETRIES", 1):
            self.bot.always_raise = NetworkError("down")
            self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["retry_count"], 0)
        new_time = database.parse_db_datetime(row["scheduled_time"])
        self.assertEqual(new_time, database.parse_db_datetime(original) + timedelta(days=1))

    def test_recurring_give_up_sends_skipped_notification(self):
        rid = self.make_due_reminder(is_recurring=True, recurrence_type="daily")
        self.bot.raise_next = [NetworkError("down")]
        with mock.patch("scheduler.REMINDER_MAX_RETRIES", 1):
            self.attempt(rid)

        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("skipped", self.bot.sent[0]["text"])
        self.assertIn("Take meds", self.bot.sent[0]["text"])

    def test_delivered_reminder_is_closed_even_if_rescheduling_fails(self):
        rid = self.make_due_reminder(is_recurring=True, recurrence_type="daily")
        with mock.patch("scheduler.calculate_next_occurrence", side_effect=ValueError("bad data")):
            self.attempt(rid)

        self.assertEqual(len(self.bot.sent), 1)
        self.assertEqual(get_reminder_by_id(rid)["status"], "sent")
        self.assertIsNone(self.due(rid), "delivered reminder must not be sent again")

    def test_postpone_resets_retry_count(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = NetworkError("down")
        self.attempt(rid)
        self.attempt(rid)
        self.assertEqual(get_reminder_by_id(rid)["retry_count"], 2)

        future = datetime.now(BELGRADE).replace(tzinfo=None) + timedelta(hours=1)
        update_reminder_time(rid, future)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["retry_count"], 0)
        self.assertEqual(row["status"], "pending")

    def test_edit_time_resets_retry_count(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = NetworkError("down")
        self.attempt(rid)
        self.assertEqual(get_reminder_by_id(rid)["retry_count"], 1)

        future = datetime.now(BELGRADE).replace(tzinfo=None) + timedelta(hours=1)
        update_reminder(rid, scheduled_time=future)

        self.assertEqual(get_reminder_by_id(rid)["retry_count"], 0)

    def test_edit_text_only_keeps_retry_count(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = NetworkError("down")
        self.attempt(rid)

        update_reminder(rid, message_text="Take meds with food")

        self.assertEqual(get_reminder_by_id(rid)["retry_count"], 1)

    def expire_retry_hold(self, rid):
        import sqlite3

        conn = sqlite3.connect(self.db_file)
        conn.execute(
            "UPDATE reminders SET retry_after = ? WHERE id = ?",
            (datetime.now() - timedelta(minutes=1), rid),
        )
        conn.commit()
        conn.close()

    def test_timeout_holds_reminder_then_retries_once(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = TimedOut("timed out")
        self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["timeout_count"], 1)
        self.assertIsNone(self.due(rid), "timed-out send must wait before retrying")

        self.expire_retry_hold(rid)
        self.bot.always_raise = None
        self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "sent")
        self.assertEqual(len(self.bot.sent), 1)

    def test_second_timeout_gives_up_and_notifies(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = TimedOut("timed out")
        self.attempt(rid)
        self.expire_retry_hold(rid)
        self.bot.always_raise = None
        self.bot.raise_next = [TimedOut("timed out")]
        self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "failed")
        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("couldn't deliver", self.bot.sent[0]["text"])

    def test_network_error_after_timeout_gives_up(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = TimedOut("timed out")
        self.attempt(rid)
        self.expire_retry_hold(rid)
        self.bot.always_raise = NetworkError("Bad Gateway")
        self.attempt(rid)

        self.assertEqual(get_reminder_by_id(rid)["status"], "failed")

    def test_network_error_without_timeout_keeps_retrying(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = NetworkError("Bad Gateway")
        self.attempt(rid)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["retry_after"])
        self.assertIsNotNone(self.due(rid))

    def test_postpone_clears_timeout_hold(self):
        rid = self.make_due_reminder()
        self.bot.always_raise = TimedOut("timed out")
        self.attempt(rid)

        future = datetime.now(BELGRADE).replace(tzinfo=None) + timedelta(hours=1)
        update_reminder_time(rid, future)

        row = get_reminder_by_id(rid)
        self.assertEqual(row["timeout_count"], 0)
        self.assertIsNone(row["retry_after"])


class MigrationTests(DeliveryTestCase):

    def test_existing_database_without_column_is_migrated(self):
        import sqlite3

        # Simulate a database created before retry_count existed
        conn = sqlite3.connect(self.db_file)
        conn.execute("DROP TABLE reminders")
        conn.execute("""
            CREATE TABLE reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
        conn.close()

        init_database()
        init_database()  # idempotent

        conn = sqlite3.connect(self.db_file)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reminders)")}
        conn.close()
        self.assertIn("retry_count", columns)


if __name__ == "__main__":
    unittest.main()
