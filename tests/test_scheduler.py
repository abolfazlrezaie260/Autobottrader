import os
import sys
from datetime import datetime, timedelta
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scheduler import BrowserClockSync, PrecisionScheduler

class TestScheduler(unittest.TestCase):
    def test_parse_hms_valid(self):
        res = BrowserClockSync.parse_hms("08:45:00")
        self.assertIsNotNone(res)
        self.assertEqual(res.hour, 8)
        self.assertEqual(res.minute, 45)
        self.assertEqual(res.second, 0)
        self.assertEqual(res.microsecond, 0)

    def test_parse_hms_invalid(self):
        self.assertIsNone(BrowserClockSync.parse_hms("invalid_time"))
        self.assertIsNone(BrowserClockSync.parse_hms(""))

    def test_parse_target_time_same_day(self):
        base = datetime(2026, 9, 7, 8, 0, 0, 0)
        target = PrecisionScheduler.parse_target_time("08:45:00.850", base)
        self.assertEqual(target.hour, 8)
        self.assertEqual(target.minute, 45)
        self.assertEqual(target.second, 0)
        self.assertEqual(target.microsecond, 850000)
        self.assertEqual(target.day, base.day)

    def test_parse_target_time_next_day(self):
        base = datetime(2026, 9, 7, 10, 0, 0, 0)
        target = PrecisionScheduler.parse_target_time("08:45:00.000", base)
        self.assertEqual(target.hour, 8)
        self.assertEqual(target.minute, 45)
        self.assertEqual(target.day, base.day + 1)

    def test_dynamic_ping_shift_arithmetic(self):
        rtt_ms = 80.0
        one_way_latency_ms = rtt_ms / 2.0
        base_target = datetime(2026, 9, 7, 8, 45, 0, 0)
        adjusted_target = base_target - timedelta(milliseconds=one_way_latency_ms)
        expected = datetime(2026, 9, 7, 8, 44, 59, 960000)
        self.assertEqual(adjusted_target, expected)

if __name__ == "__main__":
    unittest.main()
