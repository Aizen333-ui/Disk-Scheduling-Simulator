"""Workload generators and CSV import/export.

Real disk workloads are not uniform, and the algorithms rank differently on
different patterns, so the simulator supports several:

    uniform    - cylinders chosen uniformly at random
    sequential - cylinders increase by a fixed stride (wrapping around)
    hotspot    - most requests fall inside a small region of the disk

Arrival times: mean_interarrival_ms = 0 puts every request in the queue at
time 0 (batch workload). A value above 0 draws exponential gaps, i.e. a
Poisson arrival process.

CSV format (one request per line):  arrival_ms,cylinder
A header line and '#' comment lines are ignored. A single column is read as
the cylinder with arrival time 0.
"""

import random
from typing import List, Optional, Tuple

from engine import Request

WORKLOAD_KINDS = ["uniform", "sequential", "hotspot"]


def _arrival_times(n: int, mean_interarrival_ms: float, rng: random.Random) -> List[float]:
    if mean_interarrival_ms <= 0:
        return [0.0] * n
    times, t = [], 0.0
    for i in range(n):
        if i > 0:
            t += rng.expovariate(1.0 / mean_interarrival_ms)
        times.append(round(t, 3))
    return times


def _check(n: int, disk_size: int) -> None:
    if n < 1:
        raise ValueError("Number of requests must be at least 1.")
    if disk_size < 1:
        raise ValueError("Disk size must be at least 1 cylinder.")


def uniform(n: int, disk_size: int, mean_interarrival_ms: float = 0.0,
            seed: Optional[int] = None) -> List[Request]:
    _check(n, disk_size)
    rng = random.Random(seed)
    times = _arrival_times(n, mean_interarrival_ms, rng)
    return [Request(i, rng.randrange(disk_size), times[i]) for i in range(n)]


def sequential(n: int, disk_size: int, mean_interarrival_ms: float = 0.0,
               seed: Optional[int] = None, stride: int = 1) -> List[Request]:
    _check(n, disk_size)
    rng = random.Random(seed)
    times = _arrival_times(n, mean_interarrival_ms, rng)
    start = rng.randrange(disk_size)
    return [Request(i, (start + i * stride) % disk_size, times[i]) for i in range(n)]


def hotspot(n: int, disk_size: int, mean_interarrival_ms: float = 0.0,
            seed: Optional[int] = None, hot_probability: float = 0.8,
            hot_width_fraction: float = 0.1) -> List[Request]:
    _check(n, disk_size)
    rng = random.Random(seed)
    times = _arrival_times(n, mean_interarrival_ms, rng)
    width = max(1, int(disk_size * hot_width_fraction))
    lo = rng.randrange(max(1, disk_size - width + 1))
    hi = lo + width - 1
    reqs = []
    for i in range(n):
        cyl = rng.randint(lo, hi) if rng.random() < hot_probability else rng.randrange(disk_size)
        reqs.append(Request(i, cyl, times[i]))
    return reqs


def generate(kind: str, n: int, disk_size: int, mean_interarrival_ms: float = 0.0,
             seed: Optional[int] = None) -> List[Request]:
    if kind == "uniform":
        return uniform(n, disk_size, mean_interarrival_ms, seed)
    if kind == "sequential":
        return sequential(n, disk_size, mean_interarrival_ms, seed)
    if kind == "hotspot":
        return hotspot(n, disk_size, mean_interarrival_ms, seed)
    raise ValueError(f"Unknown workload '{kind}'.")


def starvation_demo(disk_size: int = 200, stream: int = 80,
                    gap_ms: float = 3.0) -> Tuple[List[Request], int]:
    """A workload that exposes SSTF starvation. Returns (requests, initial head).

    One request near the far end of the disk arrives while a steady stream of
    requests is already arriving close to the head. Because new nearby requests keep
    arriving faster than the disk can serve them, SSTF never gets round to the
    distant one until the stream ends.
    """
    if disk_size < 20:
        raise ValueError("The starvation demo needs a disk of at least 20 cylinders.")
    head = disk_size // 2
    reqs = [Request(0, disk_size - 5, 10.0)]     # the victim arrives once the stream is under way
    for i in range(stream):
        reqs.append(Request(i + 1, head - 5 + (i * 3) % 11, round(i * gap_ms, 3)))
    return reqs, head


# ------------------------------------------------------------------------- CSV
def to_csv_text(requests: List[Request]) -> str:
    lines = ["arrival_ms,cylinder"]
    lines += [f"{r.arrival_ms:g},{r.cylinder}" for r in requests]
    return "\n".join(lines) + "\n"


def parse_csv_text(text: str) -> List[Request]:
    requests: List[Request] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not requests and any(ch.isalpha() for ch in line):
            continue                                   # header row
        parts = [p.strip() for p in line.split(",")]
        try:
            if len(parts) == 1:
                arrival, cylinder = 0.0, int(parts[0])
            elif len(parts) == 2:
                arrival, cylinder = float(parts[0]), int(parts[1])
            else:
                raise ValueError
        except ValueError:
            raise ValueError(f"Line {number}: expected 'arrival_ms,cylinder' but found '{line}'.")
        requests.append(Request(len(requests), cylinder, arrival))
    if not requests:
        raise ValueError("The CSV file contains no requests.")
    return requests


def load_csv(path: str) -> List[Request]:
    with open(path, "r", encoding="utf-8") as f:
        return parse_csv_text(f.read())


def save_csv(requests: List[Request], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv_text(requests))
