"""
Tests for alerts.py: admin notification on Telegram polling failures.

Run from project root:
    venv/bin/python -m unittest discover -s tests -v
"""

import asyncio
import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOT_TOKEN", "123456:test-token")

from telegram.error import BadRequest, NetworkError, TimedOut  # noqa: E402

import alerts  # noqa: E402

logging.disable(logging.CRITICAL)

ADMIN = 430937625
T0 = datetime(2026, 10, 31, 12, 0, 0)


class FakeBot:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise NetworkError("down")
        self.sent.append({"chat_id": chat_id, "text": text})


def run(coro):
    return asyncio.run(coro)


class AlertTestCase(unittest.TestCase):

    def setUp(self):
        self.clock = [T0]
        patchers = [
            mock.patch.object(alerts, "_now", lambda: self.clock[0]),
            mock.patch.object(alerts, "ADMIN_CHAT_ID", ADMIN),
            mock.patch.object(alerts, "MAX_CONSECUTIVE_TIMEOUTS", 3),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        alerts._streak = 0
        alerts._last_failure = None
        alerts._outage_alerted = False
        self.bot = FakeBot()

    def advance(self, seconds):
        self.clock[0] = self.clock[0] + timedelta(seconds=seconds)

    def polling_failure(self, error=None):
        context = SimpleNamespace(error=error or NetworkError("httpx.ConnectError"), bot=self.bot)
        run(alerts.on_error(None, context))

    def health_check(self):
        run(alerts.check_polling_health(self.bot))


class PollingFailureTests(AlertTestCase):

    def test_no_alert_below_threshold(self):
        self.polling_failure()
        self.advance(5)
        self.polling_failure()
        self.assertEqual(self.bot.sent, [])

    def test_alert_at_threshold_only_once(self):
        for _ in range(3):
            self.polling_failure()
            self.advance(5)
        self.assertEqual(len(self.bot.sent), 1)
        self.assertEqual(self.bot.sent[0]["chat_id"], ADMIN)
        self.assertIn("3", self.bot.sent[0]["text"])

        self.polling_failure()
        self.polling_failure()
        self.assertEqual(len(self.bot.sent), 1)

    def test_timeouts_count_as_polling_failures(self):
        for _ in range(3):
            self.polling_failure(TimedOut())
            self.advance(5)
        self.assertEqual(len(self.bot.sent), 1)

    def test_spaced_out_failures_do_not_alert(self):
        for _ in range(5):
            self.polling_failure()
            self.advance(600)
        self.assertEqual(self.bot.sent, [])

    def test_handler_errors_are_not_polling_failures(self):
        context = SimpleNamespace(error=NetworkError("x"), bot=self.bot)
        for _ in range(5):
            run(alerts.on_error(object(), context))
        self.assertEqual(self.bot.sent, [])
        self.assertEqual(alerts._streak, 0)

    def test_non_network_error_without_update_is_not_counted(self):
        for _ in range(5):
            self.polling_failure(BadRequest("oops"))
        self.assertEqual(self.bot.sent, [])

    def test_alert_retried_if_admin_message_fails(self):
        self.bot.fail = True
        for _ in range(3):
            self.polling_failure()
            self.advance(5)
        self.assertEqual(self.bot.sent, [])
        self.assertFalse(alerts._outage_alerted)

        self.bot.fail = False
        self.polling_failure()
        self.assertEqual(len(self.bot.sent), 1)

    def test_no_admin_configured_sends_nothing(self):
        with mock.patch.object(alerts, "ADMIN_CHAT_ID", None):
            for _ in range(3):
                self.polling_failure()
                self.advance(5)
        self.assertEqual(self.bot.sent, [])


class RecoveryTests(AlertTestCase):

    def test_recovery_message_after_quiet_period(self):
        for _ in range(3):
            self.polling_failure()
            self.advance(5)

        self.advance(60)
        self.health_check()
        self.assertEqual(len(self.bot.sent), 1, "still within quiet period")

        self.advance(300)
        self.health_check()
        self.assertEqual(len(self.bot.sent), 2)
        self.assertIn("stabilna", self.bot.sent[1]["text"])
        self.assertFalse(alerts._outage_alerted)

    def test_new_outage_alerts_again_after_recovery(self):
        for _ in range(3):
            self.polling_failure()
            self.advance(5)
        self.advance(600)
        self.health_check()

        for _ in range(3):
            self.polling_failure()
            self.advance(5)
        self.assertEqual(len(self.bot.sent), 3)

    def test_no_recovery_message_without_outage(self):
        self.polling_failure()
        self.advance(600)
        self.health_check()
        self.assertEqual(self.bot.sent, [])

    def test_recovery_retried_if_message_fails(self):
        for _ in range(3):
            self.polling_failure()
            self.advance(5)
        self.advance(600)

        self.bot.fail = True
        self.health_check()
        self.assertTrue(alerts._outage_alerted)

        self.bot.fail = False
        self.health_check()
        self.assertEqual(len(self.bot.sent), 2)
        self.assertFalse(alerts._outage_alerted)


if __name__ == "__main__":
    unittest.main()
