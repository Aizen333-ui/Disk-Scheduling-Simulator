"""Core disk scheduling algorithms: FCFS, SSTF, SCAN, C-SCAN.

Pure logic with no GUI, so it can be tested on its own and reused by the
command-line tool and the later Tkinter/matplotlib interface.

Cylinders are numbered 0 .. disk_size - 1.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

UP = "up"      # towards higher cylinder numbers
DOWN = "down"  # towards lower cylinder numbers


@dataclass
class ScheduleResult:
    algorithm: str
    service_order: List[int]     # requests in the order they are served
    head_path: List[int]         # every cylinder the head visits, starting at the initial position
    seek_distances: List[int]    # distance counted for each move (parallel to head_path[1:])
    jump_moves: List[int]        # indices into seek_distances that are C-SCAN return jumps

    @property
    def total_movement(self) -> int:
        return sum(self.seek_distances)

    @property
    def average_seek(self) -> float:
        n = len(self.service_order)
        return self.total_movement / n if n else 0.0


def validate(requests: List[int], head: int, disk_size: int, direction: str) -> None:
    """Raise ValueError if the input is not a valid simulation setup."""
    if disk_size < 1:
        raise ValueError("Disk size must be at least 1 cylinder.")
    if not 0 <= head < disk_size:
        raise ValueError(f"Head position {head} is outside 0..{disk_size - 1}.")
    if direction not in (UP, DOWN):
        raise ValueError("Direction must be 'up' or 'down'.")
    if not requests:
        raise ValueError("The request queue is empty.")
    for r in requests:
        if not 0 <= r < disk_size:
            raise ValueError(f"Request {r} is outside 0..{disk_size - 1}.")


def _build(name: str, head: int, steps: List[Tuple[int, bool]],
           order: List[int], count_jump: bool) -> ScheduleResult:
    """Turn a list of (position, is_jump) moves into a ScheduleResult."""
    path = [head]
    distances: List[int] = []
    jumps: List[int] = []
    for pos, is_jump in steps:
        dist = abs(pos - path[-1])
        if is_jump:
            jumps.append(len(distances))
        distances.append(dist if (not is_jump or count_jump) else 0)
        path.append(pos)
    return ScheduleResult(name, order, path, distances, jumps)


def fcfs(requests: List[int], head: int, disk_size: int,
         direction: str = UP, count_jump: bool = True) -> ScheduleResult:
    """First-Come First-Served: serve requests in arrival order."""
    validate(requests, head, disk_size, direction)
    steps = [(r, False) for r in requests]
    return _build("FCFS", head, steps, list(requests), count_jump)


def sstf(requests: List[int], head: int, disk_size: int,
         direction: str = UP, count_jump: bool = True) -> ScheduleResult:
    """Shortest Seek Time First: always serve the closest pending request.

    Ties are broken in favour of the request that arrived first.
    """
    validate(requests, head, disk_size, direction)
    pending = list(requests)
    order: List[int] = []
    current = head
    while pending:
        nearest = min(pending, key=lambda r: abs(r - current))
        pending.remove(nearest)
        order.append(nearest)
        current = nearest
    steps = [(r, False) for r in order]
    return _build("SSTF", head, steps, order, count_jump)


def scan(requests: List[int], head: int, disk_size: int,
         direction: str = UP, count_jump: bool = True) -> ScheduleResult:
    """SCAN (elevator): sweep to the end of the disk, then reverse.

    If requests remain behind the head, the arm travels to the physical end
    of the disk before reversing (textbook SCAN, not LOOK).
    """
    validate(requests, head, disk_size, direction)
    last = disk_size - 1
    if direction == UP:
        first = sorted(r for r in requests if r >= head)
        second = sorted((r for r in requests if r < head), reverse=True)
        edge = last
    else:
        first = sorted((r for r in requests if r <= head), reverse=True)
        second = sorted(r for r in requests if r > head)
        edge = 0

    steps = [(r, False) for r in first]
    if second:
        steps.append((edge, False))
        steps.extend((r, False) for r in second)
    return _build("SCAN", head, steps, first + second, count_jump)


def cscan(requests: List[int], head: int, disk_size: int,
          direction: str = UP, count_jump: bool = True) -> ScheduleResult:
    """C-SCAN: sweep one way, jump back to the other end, sweep again.

    The return jump is included in total movement when count_jump is True
    (as in Silberschatz et al.) and excluded when it is False.
    """
    validate(requests, head, disk_size, direction)
    last = disk_size - 1
    if direction == UP:
        first = sorted(r for r in requests if r >= head)
        second = sorted(r for r in requests if r < head)
        edge, other_edge = last, 0
    else:
        first = sorted((r for r in requests if r <= head), reverse=True)
        second = sorted((r for r in requests if r > head), reverse=True)
        edge, other_edge = 0, last

    steps = [(r, False) for r in first]
    if second:
        steps.append((edge, False))
        steps.append((other_edge, True))   # return jump
        steps.extend((r, False) for r in second)
    return _build("C-SCAN", head, steps, first + second, count_jump)


ALGORITHMS: Dict[str, Callable[..., ScheduleResult]] = {
    "FCFS": fcfs,
    "SSTF": sstf,
    "SCAN": scan,
    "C-SCAN": cscan,
}


def run_all(requests: List[int], head: int, disk_size: int,
            direction: str = UP, count_jump: bool = True) -> Dict[str, ScheduleResult]:
    """Run every algorithm on the same input and return results by name."""
    return {name: fn(requests, head, disk_size, direction, count_jump)
            for name, fn in ALGORITHMS.items()}
