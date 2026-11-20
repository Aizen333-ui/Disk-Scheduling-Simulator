"""Unit tests. Reference example (Silberschatz et al., Operating System Concepts):
queue 98, 183, 37, 122, 14, 124, 65, 67 / head at 53 / 200 cylinders (0-199).
"""

import unittest

from disk_scheduling import DOWN, UP, cscan, fcfs, run_all, scan, sstf

QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]
HEAD = 53
SIZE = 200


class TestTextbookExample(unittest.TestCase):
    def test_fcfs(self):
        r = fcfs(QUEUE, HEAD, SIZE)
        self.assertEqual(r.service_order, QUEUE)
        self.assertEqual(r.total_movement, 640)

    def test_sstf(self):
        r = sstf(QUEUE, HEAD, SIZE)
        self.assertEqual(r.service_order, [65, 67, 37, 14, 98, 122, 124, 183])
        self.assertEqual(r.total_movement, 236)

    def test_scan_down(self):
        r = scan(QUEUE, HEAD, SIZE, DOWN)
        self.assertEqual(r.service_order, [37, 14, 65, 67, 98, 122, 124, 183])
        self.assertEqual(r.head_path[3], 0)          # reaches cylinder 0 before reversing
        self.assertEqual(r.total_movement, 236)

    def test_scan_up(self):
        r = scan(QUEUE, HEAD, SIZE, UP)
        self.assertEqual(r.service_order, [65, 67, 98, 122, 124, 183, 37, 14])
        self.assertEqual(r.total_movement, (199 - 53) + (199 - 14))   # 331

    def test_cscan_up_with_jump(self):
        r = cscan(QUEUE, HEAD, SIZE, UP, count_jump=True)
        self.assertEqual(r.service_order, [65, 67, 98, 122, 124, 183, 14, 37])
        self.assertEqual(r.total_movement, 382)

    def test_cscan_up_without_jump(self):
        r = cscan(QUEUE, HEAD, SIZE, UP, count_jump=False)
        self.assertEqual(r.total_movement, 183)
        self.assertEqual(len(r.jump_moves), 1)

    def test_cscan_down(self):
        r = cscan(QUEUE, HEAD, SIZE, DOWN, count_jump=True)
        self.assertEqual(r.service_order, [37, 14, 183, 124, 122, 98, 67, 65])
        # 53 -> 0 (53), jump 0 -> 199 (199), 199 -> 65 (134)
        self.assertEqual(r.total_movement, 53 + 199 + 134)


class TestEdgeCases(unittest.TestCase):
    def test_single_request(self):
        for name, r in run_all([10], 10, 50).items():
            self.assertEqual(r.total_movement, 0, name)

    def test_duplicates_are_all_served(self):
        for name, r in run_all([5, 5, 20], 10, 50).items():
            self.assertEqual(sorted(r.service_order), [5, 5, 20], name)

    def test_every_request_served_once(self):
        for name, r in run_all(QUEUE, HEAD, SIZE).items():
            self.assertEqual(sorted(r.service_order), sorted(QUEUE), name)

    def test_average_seek(self):
        self.assertAlmostEqual(fcfs(QUEUE, HEAD, SIZE).average_seek, 640 / 8)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            fcfs([], 10, 50)
        with self.assertRaises(ValueError):
            fcfs([60], 10, 50)
        with self.assertRaises(ValueError):
            fcfs([5], 50, 50)
        with self.assertRaises(ValueError):
            fcfs([5], 10, 50, "sideways")


if __name__ == "__main__":
    unittest.main()
