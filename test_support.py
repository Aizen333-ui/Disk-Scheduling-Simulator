"""Tests for input parsing."""

import unittest

import inputs


class TestInputs(unittest.TestCase):
    def test_parse_requests(self):
        reqs = inputs.parse_requests("98 183@5.5, 37")
        self.assertEqual([(r.id, r.cylinder, r.arrival_ms) for r in reqs],
                         [(0, 98, 0.0), (1, 183, 5.5), (2, 37, 0.0)])

    def test_format_round_trip(self):
        text = "98 183@5.5 37"
        self.assertEqual(inputs.format_requests(inputs.parse_requests(text)), text)

    def test_bad_token(self):
        with self.assertRaises(ValueError):
            inputs.parse_requests("98 abc")

    def test_parse_number(self):
        self.assertEqual(inputs.parse_number(" 5 ", "X", int), 5)
        with self.assertRaises(ValueError):
            inputs.parse_number("x", "X", int)
        with self.assertRaises(ValueError):
            inputs.parse_number("0", "X", int, 1)

    def test_build_disk(self):
        d = inputs.build_disk("100", "5400", "1.5", "12", "0.1", "random")
        self.assertEqual((d.cylinders, d.rpm, d.rotation_mode), (100, 5400, "random"))
        with self.assertRaises(ValueError):
            inputs.build_disk("100", "7200", "5", "2", "0.1", "average")   # full stroke < track-to-track


if __name__ == "__main__":
    unittest.main()
