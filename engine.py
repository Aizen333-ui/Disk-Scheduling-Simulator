"""Time-based disk scheduling engine.

Unlike the static module (disk_scheduling.py), requests here have arrival times
and the clock advances using a disk timing model, so the simulator can report
waiting time, response time, starvation and fairness as well as head movement.

Policies (all selectable by name):
    FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK, N-STEP-SCAN, FSCAN, DEADLINE

DEADLINE is a *simplified* model of Linux's mq-deadline scheduler: one sorted
queue plus one FIFO queue with an expiry time, served in batches. It leaves
out read/write separation and request merging.
"""

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from disk_model import DiskModel
from disk_scheduling import DOWN, UP


# --------------------------------------------------------------------------- data
@dataclass(frozen=True)
class Request:
    id: int
    cylinder: int
    arrival_ms: float = 0.0


@dataclass(frozen=True)
class Move:
    """A head movement that serves no request (travel to a disk edge, or a C-SCAN return jump)."""
    cylinder: int
    jump: bool = False


@dataclass
class Completion:
    request: Request
    start_ms: float        # when the disk began working on it (before the seek)
    finish_ms: float
    distance: int
    seek_ms: float
    rotation_ms: float
    transfer_ms: float

    @property
    def wait_ms(self) -> float:
        return self.start_ms - self.request.arrival_ms

    @property
    def response_ms(self) -> float:
        return self.finish_ms - self.request.arrival_ms


@dataclass
class SimResult:
    algorithm: str
    completions: List[Completion]            # in service order
    head_path: List[int]                     # every cylinder visited, starting at the initial head position
    seek_distances: List[int]                # counted distance per move (parallel to head_path[1:])
    jump_moves: List[int]                    # indices into seek_distances that are return jumps
    time_path: List[Tuple[float, int]]       # (time_ms, cylinder) points for the time-view plot
    elapsed_ms: float                        # last finish minus first arrival
    busy_ms: float                           # time the disk spent seeking/rotating/transferring

    # ---- cylinder metrics
    @property
    def service_order(self) -> List[int]:
        return [c.request.cylinder for c in self.completions]

    @property
    def total_movement(self) -> int:
        return sum(self.seek_distances)

    @property
    def average_seek(self) -> float:
        n = len(self.completions)
        return self.total_movement / n if n else 0.0

    # ---- time metrics
    @property
    def waits(self) -> List[float]:
        return [c.wait_ms for c in self.completions]

    @property
    def responses(self) -> List[float]:
        return [c.response_ms for c in self.completions]

    @property
    def avg_wait_ms(self) -> float:
        return sum(self.waits) / len(self.completions)

    @property
    def avg_response_ms(self) -> float:
        return sum(self.responses) / len(self.completions)

    @property
    def max_wait_ms(self) -> float:
        return max(self.waits)

    @property
    def max_response_ms(self) -> float:
        return max(self.responses)

    @property
    def response_std_ms(self) -> float:
        xs = self.responses
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))

    @property
    def fairness(self) -> float:
        """Jain's fairness index over response times: 1.0 = perfectly even, towards 1/n = very uneven."""
        xs = self.responses
        sq = sum(x * x for x in xs)
        return 1.0 if sq == 0 else sum(xs) ** 2 / (len(xs) * sq)

    @property
    def throughput_per_s(self) -> float:
        return len(self.completions) / self.elapsed_ms * 1000.0 if self.elapsed_ms > 0 else 0.0

    @property
    def utilization(self) -> float:
        return self.busy_ms / self.elapsed_ms if self.elapsed_ms > 0 else 0.0

    def summary(self) -> Dict[str, float]:
        return {
            "total_movement": self.total_movement,
            "average_seek": self.average_seek,
            "avg_wait_ms": self.avg_wait_ms,
            "avg_response_ms": self.avg_response_ms,
            "max_wait_ms": self.max_wait_ms,
            "max_response_ms": self.max_response_ms,
            "response_std_ms": self.response_std_ms,
            "fairness": self.fairness,
            "throughput_per_s": self.throughput_per_s,
            "utilization": self.utilization,
        }


# ------------------------------------------------------------------------ policies
Action = Union[Request, Move]


def _nearest_key(head: int):
    return lambda r: (abs(r.cylinder - head), r.arrival_ms, r.id)


class Policy:
    """Base class. choose() returns the next Request to serve or a Move."""
    name = "?"

    def reset(self, disk_size: int, head: int, direction: str) -> None:
        self.disk_size = disk_size
        self.direction = direction

    def choose(self, pending: List[Request], head: int, now: float) -> Action:
        raise NotImplementedError


class FCFS(Policy):
    def choose(self, pending, head, now):
        return min(pending, key=lambda r: (r.arrival_ms, r.id))


class SSTF(Policy):
    def choose(self, pending, head, now):
        return min(pending, key=_nearest_key(head))


class Sweep(Policy):
    """SCAN / C-SCAN / LOOK / C-LOOK in one class.

    circular=False, look=False -> SCAN   (travels to the physical end before reversing)
    circular=False, look=True  -> LOOK   (reverses at the last request)
    circular=True,  look=False -> C-SCAN (to the end, then jumps to the other end)
    circular=True,  look=True  -> C-LOOK (jumps straight to the furthest request on the other side)
    """

    def __init__(self, circular: bool = False, look: bool = False) -> None:
        self.circular = circular
        self.look = look

    def _flip(self) -> None:
        self.direction = DOWN if self.direction == UP else UP

    def pick(self, candidates: List[Request], head: int) -> Action:
        up = self.direction == UP
        ahead = [r for r in candidates if (r.cylinder >= head if up else r.cylinder <= head)]
        if ahead:
            return min(ahead, key=_nearest_key(head))

        last = self.disk_size - 1
        edge = last if up else 0
        if self.circular:
            if self.look:
                target = min(r.cylinder for r in candidates) if up else max(r.cylinder for r in candidates)
                return Move(target, jump=True)
            if head != edge:
                return Move(edge)
            return Move(0 if up else last, jump=True)

        # non-circular: reverse direction
        self._flip()
        if self.look or head == edge:
            return self.pick(candidates, head)
        return Move(edge)

    def choose(self, pending, head, now):
        return self.pick(pending, head)


class BatchSweep(Policy):
    """N-step SCAN (n given) and FSCAN (n=None).

    Requests are grouped into a batch; the batch is served with SCAN and requests
    arriving meanwhile wait for the next batch. This bounds how long a request can
    be postponed by a stream of new arrivals.
    """

    def __init__(self, n: Optional[int] = None) -> None:
        if n is not None and n < 1:
            raise ValueError("N must be at least 1.")
        self.n = n
        self.inner = Sweep()
        self.batch = set()

    def reset(self, disk_size, head, direction):
        super().reset(disk_size, head, direction)
        self.inner.reset(disk_size, head, direction)
        self.batch = set()

    def choose(self, pending, head, now):
        active = [r for r in pending if r.id in self.batch]
        if not active:
            ordered = sorted(pending, key=lambda r: (r.arrival_ms, r.id))
            active = ordered if self.n is None else ordered[:self.n]
            self.batch = {r.id for r in active}
        return self.inner.pick(active, head)


class Deadline(Policy):
    """Simplified Linux mq-deadline.

    Requests are served in ascending cylinder order (wrapping to the lowest), in
    batches of `fifo_batch`. At the start of each batch, if the oldest request
    has waited longer than `expire_ms`, it is served first and the batch continues
    from its position.
    """

    def __init__(self, fifo_batch: int = 16, expire_ms: float = 100.0) -> None:
        if fifo_batch < 1:
            raise ValueError("Batch size must be at least 1.")
        self.fifo_batch = fifo_batch
        self.expire_ms = expire_ms
        self.count = 0

    def reset(self, disk_size, head, direction):
        super().reset(disk_size, head, direction)
        self.count = 0

    def choose(self, pending, head, now):
        if self.count >= self.fifo_batch:
            self.count = 0
        oldest = min(pending, key=lambda r: (r.arrival_ms, r.id))
        if self.count == 0 and now - oldest.arrival_ms > self.expire_ms:
            pick = oldest
        else:
            pool = [r for r in pending if r.cylinder >= head] or pending
            pick = min(pool, key=lambda r: (r.cylinder, r.arrival_ms, r.id))
        self.count += 1
        return pick


POLICY_NAMES = ["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK", "N-STEP-SCAN", "FSCAN", "DEADLINE"]


def make_policy(name: str, **options) -> Policy:
    """Create a fresh policy by name. Options: n (N-STEP-SCAN), fifo_batch and expire_ms (DEADLINE)."""
    key = name.upper()
    if key == "FCFS":
        policy: Policy = FCFS()
    elif key == "SSTF":
        policy = SSTF()
    elif key == "SCAN":
        policy = Sweep(circular=False, look=False)
    elif key == "C-SCAN":
        policy = Sweep(circular=True, look=False)
    elif key == "LOOK":
        policy = Sweep(circular=False, look=True)
    elif key == "C-LOOK":
        policy = Sweep(circular=True, look=True)
    elif key == "N-STEP-SCAN":
        policy = BatchSweep(n=int(options.get("n", 4)))
    elif key == "FSCAN":
        policy = BatchSweep(n=None)
    elif key == "DEADLINE":
        policy = Deadline(fifo_batch=int(options.get("fifo_batch", 16)),
                          expire_ms=float(options.get("expire_ms", 100.0)))
    else:
        raise ValueError(f"Unknown algorithm '{name}'.")
    policy.name = key
    return policy


# ------------------------------------------------------------------------ engine
def validate_inputs(requests: Sequence[Request], head: int, disk: DiskModel, direction: str) -> None:
    if not requests:
        raise ValueError("The request queue is empty.")
    if not 0 <= head < disk.cylinders:
        raise ValueError(f"Head position {head} is outside 0..{disk.cylinders - 1}.")
    if direction not in (UP, DOWN):
        raise ValueError("Direction must be 'up' or 'down'.")
    for r in requests:
        if not 0 <= r.cylinder < disk.cylinders:
            raise ValueError(f"Request {r.cylinder} is outside 0..{disk.cylinders - 1}.")
        if r.arrival_ms < 0:
            raise ValueError("Arrival times cannot be negative.")
    if len({r.id for r in requests}) != len(requests):
        raise ValueError("Request ids must be unique.")


def simulate(requests: Sequence[Request], policy: Policy, disk: DiskModel, head: int,
             direction: str = UP, count_jump: bool = True,
             seed: Optional[int] = None) -> SimResult:
    """Run one policy over a request list and return the full result.

    count_jump=False treats the C-SCAN/C-LOOK return jump as free (zero distance, zero time).
    """
    validate_inputs(requests, head, disk, direction)
    policy.reset(disk.cylinders, head, direction)
    rng = random.Random(seed)

    arrivals = sorted(requests, key=lambda r: (r.arrival_ms, r.id))
    first_arrival = arrivals[0].arrival_ms
    pending: List[Request] = []
    completions: List[Completion] = []
    path = [head]
    distances: List[int] = []
    jumps: List[int] = []
    time_path: List[Tuple[float, int]] = [(0.0, head)]
    now, cur, busy, i = 0.0, head, 0.0, 0
    limit = 10 * len(arrivals) + 100
    steps = 0

    while i < len(arrivals) or pending:
        steps += 1
        if steps > limit:
            raise RuntimeError("The scheduling policy did not make progress.")
        while i < len(arrivals) and arrivals[i].arrival_ms <= now:
            pending.append(arrivals[i])
            i += 1
        if not pending:                       # disk idle until the next request arrives
            now = arrivals[i].arrival_ms
            time_path.append((now, cur))
            continue

        action = policy.choose(list(pending), cur, now)

        if isinstance(action, Move):
            dist = abs(action.cylinder - cur)
            counted = (not action.jump) or count_jump
            duration = disk.seek_ms(dist) if counted else 0.0
            distances.append(dist if counted else 0)
            if action.jump:
                jumps.append(len(distances) - 1)
            path.append(action.cylinder)
            now += duration
            busy += duration
            cur = action.cylinder
            time_path.append((now, cur))
        else:
            if action not in pending:
                raise RuntimeError("The policy chose a request that is not pending.")
            pending.remove(action)
            dist = abs(action.cylinder - cur)
            seek = disk.seek_ms(dist)
            rot = disk.rotational_latency_ms(rng)
            xfer = disk.transfer_ms
            start = now
            now = start + seek + rot + xfer
            busy += seek + rot + xfer
            distances.append(dist)
            path.append(action.cylinder)
            cur = action.cylinder
            time_path.append((start + seek, cur))
            time_path.append((now, cur))
            completions.append(Completion(action, start, now, dist, seek, rot, xfer))

    return SimResult(policy.name, completions, path, distances, jumps, time_path,
                     now - first_arrival, busy)


def run_all(requests: Sequence[Request], head: int, disk: DiskModel, direction: str = UP,
            count_jump: bool = True, names: Optional[Sequence[str]] = None,
            seed: Optional[int] = None, **policy_options) -> Dict[str, SimResult]:
    """Run several algorithms on the same input; returns results keyed by algorithm name."""
    chosen = list(names) if names else list(POLICY_NAMES)
    return {n: simulate(requests, make_policy(n, **policy_options), disk, head, direction, count_jump, seed)
            for n in chosen}


def requests_at_zero(cylinders: Sequence[int]) -> List[Request]:
    """Convenience: build requests that all arrive at time 0 (the classic textbook setting)."""
    return [Request(i, c, 0.0) for i, c in enumerate(cylinders)]
