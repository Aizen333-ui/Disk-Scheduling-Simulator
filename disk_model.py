"""A simple disk timing model.

Total service time of a request = seek time + rotational latency + transfer time.

* Seek time grows with the square root of the distance, a common approximation
  for real drives (short seeks are dominated by acceleration, long seeks by
  cruising speed). It runs from `track_to_track_ms` for a one-cylinder seek up
  to `full_stroke_ms` for a seek across the whole disk.
* Rotational latency is either the average (half a rotation, deterministic) or
  a random value between 0 and one full rotation.
* Transfer time is a fixed per-request constant.

All times are in milliseconds.
"""

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DiskModel:
    cylinders: int = 200
    rpm: int = 7200
    track_to_track_ms: float = 1.0
    full_stroke_ms: float = 15.0
    transfer_ms: float = 0.05
    rotation_mode: str = "average"      # "average" or "random"

    def __post_init__(self) -> None:
        if self.cylinders < 1:
            raise ValueError("Disk size must be at least 1 cylinder.")
        if self.rpm <= 0:
            raise ValueError("RPM must be positive.")
        if self.track_to_track_ms < 0 or self.transfer_ms < 0:
            raise ValueError("Times cannot be negative.")
        if self.full_stroke_ms < self.track_to_track_ms:
            raise ValueError("Full-stroke seek time cannot be shorter than the track-to-track time.")
        if self.rotation_mode not in ("average", "random"):
            raise ValueError("Rotation mode must be 'average' or 'random'.")

    @property
    def rotation_ms(self) -> float:
        """Time for one full rotation."""
        return 60000.0 / self.rpm

    def seek_ms(self, distance: int) -> float:
        distance = abs(distance)
        if distance == 0:
            return 0.0
        if distance == 1 or self.cylinders <= 2:
            return self.track_to_track_ms
        fraction = min(1.0, (distance - 1) / (self.cylinders - 2))
        return self.track_to_track_ms + (self.full_stroke_ms - self.track_to_track_ms) * math.sqrt(fraction)

    def rotational_latency_ms(self, rng: random.Random) -> float:
        if self.rotation_mode == "random":
            return rng.uniform(0.0, self.rotation_ms)
        return self.rotation_ms / 2.0
