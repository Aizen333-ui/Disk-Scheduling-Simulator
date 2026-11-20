"""Tests for workloads, CSV import/export, input parsing, statistics and the experiment."""

import unittest

import experiment
import inputs
import stats
import workloads
from disk_model import DiskModel
from engine import POLICY_NAMES


class TestWorkloads(unittest.TestCase):
    def test_uniform_is_repeatable_and_in_range(self):
        a = workloads.uniform(50, 200, 3.0, seed=1)
        b = workloads.uniform(50, 200, 3.0, seed=1)
        self.assertEqual(a, b)
        self.assertTrue(all(0 <= r.cylinder < 200 for r in a))
        arrivals = [r.arrival_ms for r in a]
        self.assertEqual(arrivals, sorted(arrivals))

    def test_batch_workload_arrives_at_zero(self):
        self.assertTrue(all(r.arrival_ms == 0 for r in workloads.uniform(10, 100, 0.0, seed=2)))

    def test_sequential_pattern(self):
        reqs = workloads.sequential(5, 10, seed=3)
        cyls = [r.cylinder for r in reqs]
        self.assertEqual(cyls, [(cyls[0] + i) % 10 for i in range(5)])

    def test_hotspot_concentrates_requests(self):
        reqs = workloads.hotspot(1000, 200, seed=4)
        counts = {}
        for r in reqs:
            counts[r.cylinder // 20] = counts.get(r.cylinder // 20, 0) + 1
        self.assertGreater(max(counts.values()), 0.45 * len(reqs))

    def test_generate_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            workloads.generate("zigzag", 5, 100)
        with self.assertRaises(ValueError):
            workloads.uniform(0, 100)


class TestCsv(unittest.TestCase):
    def test_round_trip(self):
        reqs = workloads.uniform(20, 200, 2.5, seed=9)
        back = workloads.parse_csv_text(workloads.to_csv_text(reqs))
        self.assertEqual([(r.cylinder, round(r.arrival_ms, 3)) for r in back],
                         [(r.cylinder, round(r.arrival_ms, 3)) for r in reqs])

    def test_header_comments_and_single_column(self):
        text = "# my trace\narrival_ms,cylinder\n0,10\n5.5,20\n"
        self.assertEqual([(r.arrival_ms, r.cylinder) for r in workloads.parse_csv_text(text)],
                         [(0.0, 10), (5.5, 20)])
        self.assertEqual([r.cylinder for r in workloads.parse_csv_text("7\n8\n")], [7, 8])

    def test_errors_name_the_line(self):
        with self.assertRaises(ValueError) as ctx:
            workloads.parse_csv_text("0,10\n1,abc\n")
        self.assertIn("Line 2", str(ctx.exception))
        with self.assertRaises(ValueError):
            workloads.parse_csv_text("\n# nothing here\n")


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


class TestStats(unittest.TestCase):
    def test_ci95(self):
        m, half = stats.ci95([1, 2, 3, 4, 5])
        self.assertAlmostEqual(m, 3.0)
        self.assertAlmostEqual(half, 2.776 * 1.5811388 / 5 ** 0.5, places=3)

    def test_single_value_has_zero_interval(self):
        self.assertEqual(stats.ci95([4.0]), (4.0, 0.0))

    def test_percentile(self):
        self.assertEqual(stats.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(stats.percentile([5], 90), 5)

    def test_t_critical_large_df(self):
        self.assertAlmostEqual(stats.t_critical(500), 1.96)


class TestExperiment(unittest.TestCase):
    def run_small(self, seed):
        return experiment.run_experiment(6, 8, DiskModel(cylinders=60), "hotspot", 3.0, seed=seed)

    def test_structure(self):
        data = self.run_small(1)
        self.assertEqual(set(data), {k for k, _ in experiment.METRICS})
        for per_algo in data.values():
            self.assertEqual(set(per_algo), set(POLICY_NAMES))
            self.assertTrue(all(len(v) == 6 for v in per_algo.values()))

    def test_repeatable_with_seed(self):
        self.assertEqual(self.run_small(2), self.run_small(2))

    def test_scan_family_beats_fcfs_on_movement(self):
        data = experiment.run_experiment(60, 20, DiskModel(cylinders=200), "uniform", 0.0, seed=3)
        mean = lambda a: stats.mean(data["total_movement"][a])
        self.assertLess(mean("SSTF"), mean("FCFS"))
        self.assertLess(mean("LOOK"), mean("FCFS"))

    def test_rejects_bad_counts(self):
        with self.assertRaises(ValueError):
            experiment.run_experiment(0, 5, DiskModel())


if __name__ == "__main__":
    unittest.main()
