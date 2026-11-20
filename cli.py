"""Command-line front end for the disk scheduling simulator.

Requests are cylinder numbers, optionally with an arrival time: 98 or 98@12.5 (ms).

Example:
    python cli.py --requests 98 183 37 122 14 124 65 67 --head 53 --size 200 --direction up
    python cli.py --requests 98@0 183@5 37@8 --head 53 --algorithms FCFS SSTF LOOK
"""

import argparse

import inputs
from disk_model import DiskModel
from disk_scheduling import DOWN, UP
from engine import POLICY_NAMES, run_all


def main() -> None:
    p = argparse.ArgumentParser(description="Disk scheduling simulator")
    p.add_argument("--requests", nargs="+", required=True, help="cylinders, optionally cylinder@arrival_ms")
    p.add_argument("--head", type=int, required=True, help="initial head position")
    p.add_argument("--size", type=int, default=200, help="number of cylinders (default 200)")
    p.add_argument("--direction", choices=[UP, DOWN], default=UP)
    p.add_argument("--no-jump", action="store_true", help="do not count the C-SCAN/C-LOOK return jump")
    p.add_argument("--rpm", type=int, default=7200)
    p.add_argument("--algorithms", nargs="+", default=POLICY_NAMES, help=f"any of: {' '.join(POLICY_NAMES)}")
    args = p.parse_args()

    try:
        requests = inputs.parse_requests(" ".join(args.requests))
        disk = DiskModel(cylinders=args.size, rpm=args.rpm)
        results = run_all(requests, args.head, disk, args.direction, not args.no_jump,
                          [a.upper() for a in args.algorithms])
    except ValueError as e:
        p.error(str(e))

    for name, r in results.items():
        print(f"\n{name}")
        print("  Service order :", " -> ".join(map(str, r.service_order)))
        print("  Head path     :", " -> ".join(map(str, r.head_path)))
        print(f"  Head movement : {r.total_movement} cylinders (average {r.average_seek:.2f} per request)")
        print(f"  Response time : average {r.avg_response_ms:.2f} ms, maximum wait {r.max_wait_ms:.2f} ms")

    print("\nComparison (sorted by total head movement)")
    print(f"  {'Algorithm':<12}{'Movement':>10}{'Avg resp ms':>13}{'Max wait ms':>13}{'Fairness':>10}")
    for name, r in sorted(results.items(), key=lambda kv: kv[1].total_movement):
        print(f"  {name:<12}{r.total_movement:>10}{r.avg_response_ms:>13.2f}{r.max_wait_ms:>13.2f}{r.fairness:>10.3f}")


if __name__ == "__main__":
    main()
