"""
Tests for parsers/time_parser.py.

Run from project root:
    venv/bin/python -m unittest discover -s tests -v

All tests use a fixed "now" (Saturday 2026-10-31 10:00, Europe/Belgrade)
so results do not depend on the wall clock.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.time_parser import (  # noqa: E402
    parse_reminder,
    parse_reminders,
    parse_time,
    parse_time_string,
)

BELGRADE = "Europe/Belgrade"
BELGRADE_TZ = pytz.timezone(BELGRADE)
NOW = datetime(2026, 10, 31, 10, 0)  # Saturday, local Belgrade time


def single(message, tz=BELGRADE, now=NOW):
    result = parse_reminder(message, tz, now=now)
    return result


def dual(message, tz=BELGRADE, now=NOW):
    return parse_reminders(message, tz, now=now)


class ParseTimeStringTests(unittest.TestCase):

    def test_hh_mm(self):
        self.assertEqual(parse_time_string("21:00"), (21, 0))
        self.assertEqual(parse_time_string("6:30"), (6, 30))

    def test_bare_hour(self):
        self.assertEqual(parse_time_string("8"), (8, 0))
        self.assertEqual(parse_time_string("0"), (0, 0))

    def test_am_pm(self):
        self.assertEqual(parse_time_string("7am"), (7, 0))
        self.assertEqual(parse_time_string("6 PM"), (18, 0))
        self.assertEqual(parse_time_string("12am"), (0, 0))
        self.assertEqual(parse_time_string("12pm"), (12, 0))

    def test_military(self):
        self.assertEqual(parse_time_string("2100"), (21, 0))
        self.assertEqual(parse_time_string("0700"), (7, 0))

    def test_invalid(self):
        self.assertIsNone(parse_time_string("24:00"))
        self.assertIsNone(parse_time_string("12:60"))
        self.assertIsNone(parse_time_string("13pm"))
        self.assertIsNone(parse_time_string("0am"))
        self.assertIsNone(parse_time_string("25"))
        self.assertIsNone(parse_time_string("2560"))
        self.assertIsNone(parse_time_string("abc"))
        self.assertIsNone(parse_time_string(""))

    def test_parse_time_returns_time_object(self):
        self.assertEqual(parse_time("14:30").hour, 14)
        self.assertIsNone(parse_time("nope"))


class SingleReminderTests(unittest.TestCase):

    def test_serbian_day_keyword(self):
        self.assertEqual(single("Kafa sutra 14:00"),
                         ("Kafa", datetime(2026, 11, 1, 14, 0)))

    def test_serbian_day_after_tomorrow(self):
        self.assertEqual(single("Kafa prekosutra 9:00"),
                         ("Kafa", datetime(2026, 11, 2, 9, 0)))

    def test_english_tomorrow(self):
        self.assertEqual(single("Coffee tomorrow 16:00"),
                         ("Coffee", datetime(2026, 11, 1, 16, 0)))

    def test_weekday_short_english(self):
        # Saturday -> next Monday is 2026-11-02
        self.assertEqual(single("Meeting mon 10:00"),
                         ("Meeting", datetime(2026, 11, 2, 10, 0)))

    def test_weekday_serbian(self):
        self.assertEqual(single("Sastanak pon 10:00"),
                         ("Sastanak", datetime(2026, 11, 2, 10, 0)))

    def test_weekday_never_means_today(self):
        # Today is Saturday; "sat" must mean next Saturday
        self.assertEqual(single("Ručak sub 13:00"),
                         ("Ručak", datetime(2026, 11, 7, 13, 0)))

    def test_next_week_english(self):
        # Next Thursday is 2026-11-05; "next" adds one week
        self.assertEqual(single("Meeting next thu 14:00"),
                         ("Meeting", datetime(2026, 11, 12, 14, 0)))

    def test_next_week_serbian(self):
        self.assertEqual(single("Sastanak sl pon 10:00"),
                         ("Sastanak", datetime(2026, 11, 9, 10, 0)))

    def test_time_passed_today_moves_to_tomorrow(self):
        self.assertEqual(single("Something 7am"),
                         ("Something", datetime(2026, 11, 1, 7, 0)))

    def test_future_time_today(self):
        self.assertEqual(single("Call John 6 PM"),
                         ("Call John", datetime(2026, 10, 31, 18, 0)))

    def test_military_time(self):
        self.assertEqual(single("Test 2100"),
                         ("Test", datetime(2026, 10, 31, 21, 0)))

    def test_date_dd_mm_with_dot(self):
        self.assertEqual(single("Meeting 25.12. 10:00"),
                         ("Meeting", datetime(2026, 12, 25, 10, 0)))

    def test_date_dd_mm_without_dot(self):
        self.assertEqual(single("Event 31.12 18:00"),
                         ("Event", datetime(2026, 12, 31, 18, 0)))

    def test_date_slash_format(self):
        self.assertEqual(single("Dinner 24/12 19:30"),
                         ("Dinner", datetime(2026, 12, 24, 19, 30)))

    def test_date_full_year(self):
        self.assertEqual(single("Rođendan 15.01.2027. 14:30"),
                         ("Rođendan", datetime(2027, 1, 15, 14, 30)))

    def test_date_without_year_already_passed_goes_to_next_year(self):
        self.assertEqual(single("Event 01.10 18:00"),
                         ("Event", datetime(2027, 10, 1, 18, 0)))

    def test_multiword_text_is_kept(self):
        self.assertEqual(single("Pozovi mamu i tatu sutra 18:30"),
                         ("Pozovi mamu i tatu", datetime(2026, 11, 1, 18, 30)))

    def test_invalid_date_is_not_a_date(self):
        # 31.02 does not exist: the token is not taken as a date, so the
        # reminder text keeps it and the time alone decides the day
        self.assertEqual(single("Event 31.02. 10:00"),
                         ("Event 31.02.", datetime(2026, 11, 1, 10, 0)))

    def test_no_time_returns_none(self):
        self.assertIsNone(single("samo tekst"))

    def test_only_time_returns_none(self):
        self.assertIsNone(single("14:00"))

    def test_day_without_text_returns_none(self):
        self.assertIsNone(single("sutra 14:00"))

    def test_invalid_time_returns_none(self):
        self.assertIsNone(single("Kafa 25:00"))
        self.assertIsNone(single("Kafa 12:60"))

    def test_empty_message_returns_none(self):
        self.assertIsNone(single("   "))

    def test_naive_now_is_localized(self):
        self.assertEqual(single("Kafa 14:00", now=NOW),
                         ("Kafa", datetime(2026, 10, 31, 14, 0)))

    def test_aware_now_is_converted(self):
        import pytz
        aware = pytz.UTC.localize(datetime(2026, 10, 31, 9, 0))  # 10:00 Belgrade
        self.assertEqual(single("Kafa 10:30", now=aware),
                         ("Kafa", datetime(2026, 10, 31, 10, 30)))

    def test_user_timezone_changes_result(self):
        # The instant is 10:00 Belgrade = 04:00 New York: 09:00 is still ahead there
        instant = BELGRADE_TZ.localize(NOW)
        self.assertEqual(single("Kafa 09:00", tz="America/New_York", now=instant),
                         ("Kafa", datetime(2026, 10, 31, 9, 0)))
        # In Belgrade 09:00 has already passed and moves to tomorrow
        self.assertEqual(single("Kafa 09:00", tz=BELGRADE, now=instant),
                         ("Kafa", datetime(2026, 11, 1, 9, 0)))

    def test_unknown_timezone_falls_back_to_belgrade(self):
        self.assertEqual(single("Kafa 14:00", tz="Nowhere/City"),
                         single("Kafa 14:00", tz=BELGRADE))

    def test_result_is_naive(self):
        text, when = single("Kafa sutra 14:00")
        self.assertIsNone(when.tzinfo)

    # Known heuristics: a trailing number is read as an hour. These document
    # current behaviour so a change to the heuristic is a conscious decision.

    def test_heuristic_trailing_number_is_read_as_hour(self):
        self.assertEqual(single("Zadatak broj 2"),
                         ("Zadatak broj", datetime(2026, 11, 1, 2, 0)))

    def test_heuristic_four_digit_number_is_read_as_military_time(self):
        self.assertEqual(single("Kafa 2026"),
                         ("Kafa", datetime(2026, 10, 31, 20, 26)))


class DstTests(unittest.TestCase):
    """Output is naive local wall-clock time, so DST must not shift it."""

    def test_day_across_spring_forward(self):
        # Belgrade switches to DST on 2027-03-28 (02:00 -> 03:00)
        now = datetime(2027, 3, 27, 12, 0)
        self.assertEqual(single("Kafa sutra 14:00", now=now),
                         ("Kafa", datetime(2027, 3, 28, 14, 0)))

    def test_time_inside_spring_forward_gap_is_kept_as_wall_clock(self):
        now = datetime(2027, 3, 27, 12, 0)
        self.assertEqual(single("Kafa sutra 02:30", now=now),
                         ("Kafa", datetime(2027, 3, 28, 2, 30)))

    def test_day_across_fall_back(self):
        # Belgrade switches back on 2026-10-25; asked on the 24th for "tomorrow"
        now = datetime(2026, 10, 24, 12, 0)
        self.assertEqual(single("Kafa sutra 02:30", now=now),
                         ("Kafa", datetime(2026, 10, 25, 2, 30)))


class DualReminderTests(unittest.TestCase):

    def test_evening_and_morning_lands_next_day(self):
        self.assertEqual(dual("Meds 21:00 6:00"), [
            ("Meds", datetime(2026, 10, 31, 21, 0)),
            ("Meds", datetime(2026, 11, 1, 6, 0)),
        ])

    def test_day_and_weekday(self):
        self.assertEqual(dual("Task tomorrow 20:00 wed 21:00"), [
            ("Task", datetime(2026, 11, 1, 20, 0)),
            ("Task", datetime(2026, 11, 4, 21, 0)),
        ])

    def test_two_am_pm_times(self):
        # 9am has passed today -> tomorrow; 9pm is later the same day
        self.assertEqual(dual("Lek 9am 9pm"), [
            ("Lek", datetime(2026, 11, 1, 9, 0)),
            ("Lek", datetime(2026, 11, 1, 21, 0)),
        ])

    def test_single_time_is_not_dual(self):
        self.assertEqual(dual("Kafa sutra 14:00"),
                         [("Kafa", datetime(2026, 11, 1, 14, 0))])

    def test_returns_none_for_garbage(self):
        self.assertIsNone(dual("samo tekst"))

    def test_dual_respects_timezone(self):
        # The instant is 10:00 Belgrade = 04:00 New York: 09:00 is still ahead there
        instant = BELGRADE_TZ.localize(NOW)
        self.assertEqual(dual("Kafa 09:00 13:00", tz="America/New_York", now=instant), [
            ("Kafa", datetime(2026, 10, 31, 9, 0)),
            ("Kafa", datetime(2026, 10, 31, 13, 0)),
        ])
        self.assertEqual(dual("Kafa 09:00 13:00", tz=BELGRADE, now=instant), [
            ("Kafa", datetime(2026, 11, 1, 9, 0)),
            ("Kafa", datetime(2026, 11, 1, 13, 0)),
        ])


if __name__ == "__main__":
    unittest.main()
