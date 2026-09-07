import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from trader import parse_number

class TestTrader(unittest.TestCase):
    def test_parse_number_with_commas(self):
        self.assertEqual(parse_number("13,540"), 13540)
        self.assertEqual(parse_number("1,000,000"), 1000000)

    def test_parse_number_persian_digits(self):
        self.assertEqual(parse_number("۱۲۳,۴۵۶"), 123456)
        self.assertEqual(parse_number("۰"), 0)
        self.assertEqual(parse_number("۲,۷۲۲"), 2722)

    def test_parse_number_whitespace_and_junk(self):
        self.assertEqual(parse_number("  154429  \n"), 154429)
        self.assertEqual(parse_number("قیمت: 12,000 ریال"), 12000)

    def test_parse_number_empty_or_none(self):
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number(None))
        self.assertIsNone(parse_number("   "))

if __name__ == "__main__":
    unittest.main()
