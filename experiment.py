"""Random workload experiment with statistics.

Each trial generates one random workload and runs every algorithm on that same
workload (a paired comparison). Repeating over many trials gives a distribution
of each metric per algorithm, summarised as a mean with a 95% confidence interval.

Example:
    python experiment.py --workload hotspot --trials 300 --requests 30 --gap 4
"""

import argparse
import random
from typing import Dict, List, Optional, Sequence

import stats
import workloads
from disk_model import DiskModel
from disk_scheduling import DOWN, UP
from engine import POLICY_NAMES, run_all

METRICS = [
    ("avg_response_ms", "Average response time (ms)"),
    ("avg_wait_ms", "Average wait time (ms)"),
    ("max_wait_ms", "Maximum wait time (ms)"),
    ("total_movement", "Total head movement (cylinders)"),
    ("fairness", "Fairness index (Jain, response times)"),
    ("response_std_ms", "Response time std. deviation (ms)"),
]
METRIC_LABELS = dict(METRICS)


def run_experiment(trials: int, n_requests: int, disk: DiskModel, workload: str = "uniform",
                   mean_interarrival_ms: float = 0.0, names: Optional[Sequence[str]] = None,
                   count_jump: bool = True, seed: Optional[int] = None,
                   policy_options: Optional[dict] = None) -> Dict[str, Dict[str, List[float]]]:
    """Return {metric: {algorithm: [value per trial]}}."""
    if trials < 1 or n_requests < 1:
        raise ValueError("Trials and number of requests must be at least 1.")
    rng = random.Random(seed)
    algos = list(names) if names else list(POLICY_NAMES)
    data = {key: {a: [] for a in algos} for key, _ in METRICS}
    options = policy_options or {}
    for _ in range(trials):
        requests = workloads.generate(workload, n_requests, disk.cylinders,
                                      mean_interarrival_ms, seed=rng.randrange(2 ** 31))
        head = rng.randrange(disk.cylinders)
        direction = rng.choice([UP, DOWN])
        results = run_all(requests, head, disk, direction, count_jump, algos,
                          seed=rng.randrange(2 ** 31), **options)
        for algo, result in results.items():
            summary = result.summary()
            for key, _ in METRICS:
                data[key][algo].append(summary[key])
    return data


def main() -> None:
    p = argparse.ArgumentParser(description="Random workload experiment")
    p.add_argument("--workload", choices=workloads.WORKLOAD_KINDS, default="uniform")
    p.add_argument("--trials", type=int, default=300)
    p.add_argument("--requests", type=int, default=30, help="requests per trial")
    p.add_argument("--gap", type=float, default=8.0, help="mean time between arrivals in ms (0 = all at once)")
    p.add_argument("--size", type=int, default=200)
    p.add_argument("--seed", type=int, default=None, help="fix for repeatable results")
    args = p.parse_args()

    data = run_experiment(args.trials, args.requests, DiskModel(cylinders=args.size),
                          args.workload, args.gap, seed=args.seed)
    print(f"{args.workload} workload, {args.trials} trials, {args.requests} requests each, "
          f"mean gap {args.gap} ms, {args.size} cylinders   (mean +/- 95% CI)\n")
    shown = ["avg_response_ms", "max_wait_ms", "total_movement", "fairness"]
    print(f"  {'Algorithm':<12}" + "".join(f"{METRIC_LABELS[k].split(' (')[0][:22]:>26}" for k in shown))
    summaries = {k: stats.summarize(data[k]) for k in shown}
    order = sorted(data["avg_response_ms"], key=lambda a: summaries["avg_response_ms"][a][0])
    for algo in order:
        cells = "".join(f"{summaries[k][algo][0]:>16.2f} +/- {summaries[k][algo][1]:<6.2f}" for k in shown)
        print(f"  {algo:<12}{cells}")


if __name__ == "__main__":
    main()
