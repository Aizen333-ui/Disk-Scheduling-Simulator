"""Tests for the time-based engine.

Reference example (Silberschatz et al.): queue 98 183 37 122 14 124 65 67,
head at 53, 200 cylinders.
"""

import random
import unittest

import disk_scheduling as static
from disk_model import DiskModel
from engine import (DOWN, POLICY_NAMES, UP, Request, make_policy, requests_at_zero,
                    run_all, simulate)

QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]
HEAD = 53
DISK = DiskModel(cylinders=200)


def run(name, requests, head=HEAD, direction=UP, count_jump=True, disk=DISK, **opts):
    return simulate(requests, make_policy(name, **opts), disk, head, direction, count_jump)


class TestParityWithStaticModule(unittest.TestCase):
    """With every request at time 0 the engine must match the classic algorithms."""

    def test_matches_static_results(self):
        reqs = requests_at_zero(QUEUE)
        for direction in (UP, DOWN):
            for count_jump in (True, False):
                expected = static.run_all(QUEUE, HEAD, 200, direction, count_jump)
                for name, ref in expected.items():
                    got = run(name, reqs, direction=direction, count_jump=count_jump)
                    self.assertEqual(got.service_order, ref.service_order, (name, direction))
                    self.assertEqual(got.total_movement, ref.total_movement, (name, direction, count_jump))
                    self.assertEqual(got.head_path, ref.head_path, (name, direction))

    def test_textbook_totals(self):
        reqs = requests_at_zero(QUEUE)
        self.assertEqual(run("FCFS", reqs).total_movement, 640)
        self.assertEqual(run("SSTF", reqs).total_movement, 236)
        self.assertEqual(run("SCAN", reqs, direction=DOWN).total_movement, 236)
        self.assertEqual(run("C-SCAN", reqs).total_movement, 382)


class TestLookFamily(unittest.TestCase):
    def test_look_up(self):
        r = run("LOOK", requests_at_zero(QUEUE))
        self.assertEqual(r.service_order, [65, 67, 98, 122, 124, 183, 37, 14])
        self.assertEqual(r.total_movement, 299)           # reverses at 183, not at 199

    def test_look_down(self):
        r = run("LOOK", requests_at_zero(QUEUE), direction=DOWN)
        self.assertEqual(r.service_order, [37, 14, 65, 67, 98, 122, 124, 183])
        self.assertEqual(r.total_movement, 208)           # reverses at 14, not at 0

    def test_clook(self):
        reqs = requests_at_zero(QUEUE)
        r = run("C-LOOK", reqs)
        self.assertEqual(r.service_order, [65, 67, 98, 122, 124, 183, 14, 37])
        self.assertEqual(r.total_movement, 130 + 169 + 23)    # 322 including the jump
        self.assertEqual(run("C-LOOK", reqs, count_jump=False).total_movement, 153)

    def test_look_never_beats_scan_by_going_further(self):
        reqs = requests_at_zero(QUEUE)
        self.assertLessEqual(run("LOOK", reqs).total_movement, run("SCAN", reqs).total_movement)
        self.assertLessEqual(run("C-LOOK", reqs).total_movement, run("C-SCAN", reqs).total_movement)


class TestOnlineArrivals(unittest.TestCase):
    def setUp(self):
        # 70 arrives while the disk is busy serving 60.
        self.reqs = [Request(0, 60, 0.0), Request(1, 80, 0.0), Request(2, 70, 4.0)]

    def test_scan_picks_up_new_request_ahead(self):
        self.assertEqual(run("SCAN", self.reqs, head=50).service_order, [60, 70, 80])

    def test_fscan_makes_new_request_wait_for_next_batch(self):
        self.assertEqual(run("FSCAN", self.reqs, head=50).service_order, [60, 80, 70])

    def test_nstep_with_n_equal_one_behaves_like_fcfs(self):
        reqs = requests_at_zero([90, 10, 50])
        r = run("N-STEP-SCAN", reqs, head=0, n=1)
        self.assertEqual(r.service_order, [90, 10, 50])

    def test_idle_gap_is_skipped(self):
        r = run("FCFS", [Request(0, 20, 1000.0)], head=0)
        c = r.completions[0]
        self.assertEqual(c.start_ms, 1000.0)
        self.assertEqual(c.wait_ms, 0.0)


class TestDeadline(unittest.TestCase):
    def setUp(self):
        # head 100; request 0 is old and far below the head, the rest are ahead of it
        self.reqs = requests_at_zero([10, 110, 120, 130, 140])

    def test_expired_request_is_served_at_batch_start(self):
        r = run("DEADLINE", self.reqs, head=100, fifo_batch=2, expire_ms=1.0)
        self.assertEqual(r.service_order, [110, 120, 10, 130, 140])

    def test_without_expiry_it_is_a_pure_ascending_sweep(self):
        r = run("DEADLINE", self.reqs, head=100, fifo_batch=2, expire_ms=10_000.0)
        self.assertEqual(r.service_order, [110, 120, 130, 140, 10])


class TestTimingModel(unittest.TestCase):
    def test_seek_curve(self):
        d = DiskModel(cylinders=200)
        self.assertEqual(d.seek_ms(0), 0.0)
        self.assertEqual(d.seek_ms(1), d.track_to_track_ms)
        self.assertAlmostEqual(d.seek_ms(199), d.full_stroke_ms)
        self.assertTrue(all(d.seek_ms(k) < d.seek_ms(k + 1) for k in range(1, 199)))

    def test_rotation_average(self):
        self.assertAlmostEqual(DiskModel(rpm=7200).rotational_latency_ms(random.Random(0)), 60000 / 7200 / 2)

    def test_single_request_service_time(self):
        d = DiskModel(cylinders=200)
        r = simulate([Request(0, 100, 0.0)], make_policy("FCFS"), d, 0)
        expected = d.seek_ms(100) + d.rotation_ms / 2 + d.transfer_ms
        self.assertAlmostEqual(r.completions[0].response_ms, expected)
        self.assertEqual(r.completions[0].wait_ms, 0.0)

    def test_free_jump_costs_no_time(self):
        reqs = requests_at_zero(QUEUE)
        paid = run("C-SCAN", reqs, count_jump=True)
        free = run("C-SCAN", reqs, count_jump=False)
        self.assertLess(free.elapsed_ms, paid.elapsed_ms)

    def test_random_rotation_is_repeatable_with_a_seed(self):
        d = DiskModel(rotation_mode="random")
        reqs = requests_at_zero(QUEUE)
        a = simulate(reqs, make_policy("SSTF"), d, HEAD, seed=5)
        b = simulate(reqs, make_policy("SSTF"), d, HEAD, seed=5)
        self.assertEqual(a.elapsed_ms, b.elapsed_ms)


class TestMetrics(unittest.TestCase):
    def test_equal_responses_give_fairness_one(self):
        r = run("FCFS", [Request(0, 53, 0.0)])
        self.assertEqual(r.fairness, 1.0)

    def test_uneven_service_lowers_fairness(self):
        reqs = requests_at_zero(QUEUE)
        self.assertLess(run("FCFS", reqs).fairness, 1.0)

    def test_summary_keys(self):
        s = run("FCFS", requests_at_zero(QUEUE)).summary()
        for key in ("total_movement", "avg_wait_ms", "avg_response_ms", "max_wait_ms",
                    "fairness", "throughput_per_s", "utilization"):
            self.assertIn(key, s)
        self.assertLessEqual(s["utilization"], 1.0 + 1e-9)

    def test_all_policy_names_are_supported(self):
        for name in POLICY_NAMES:
            self.assertEqual(make_policy(name).name, name)
        with self.assertRaises(ValueError):
            make_policy("ELEVATOR")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            simulate([], make_policy("FCFS"), DISK, 0)
        with self.assertRaises(ValueError):
            simulate([Request(0, 500, 0.0)], make_policy("FCFS"), DISK, 0)
        with self.assertRaises(ValueError):
            simulate([Request(0, 5, -1.0)], make_policy("FCFS"), DISK, 0)
        with self.assertRaises(ValueError):
            simulate([Request(0, 5, 0.0), Request(0, 6, 0.0)], make_policy("FCFS"), DISK, 0)
        with self.assertRaises(ValueError):
            simulate([Request(0, 5, 0.0)], make_policy("FCFS"), DISK, 999)


if __name__ == "__main__":
    unittest.main()
