"""Parsing of user input text into requests and disk settings.

Kept separate from the GUI so it can be tested without Tkinter.

Request syntax: space- or comma-separated tokens, each either
    98        cylinder 98, arriving at time 0
    98@12.5   cylinder 98, arriving at 12.5 ms
"""

import re
from typing import List

from disk_model import DiskModel
from engine import Request


def parse_requests(text: str) -> List[Request]:
    tokens = [t for t in re.split(r"[,\s]+", text.strip()) if t]
    requests = []
    for i, token in enumerate(tokens):
        cyl_text, _, arrival_text = token.partition("@")
        try:
            cylinder = int(cyl_text)
            arrival = float(arrival_text) if arrival_text else 0.0
        except ValueError:
            raise ValueError(f"Cannot read request '{token}'. Use 98 or 98@12.5 (cylinder@arrival in ms).")
        requests.append(Request(i, cylinder, arrival))
    return requests


def format_requests(requests: List[Request]) -> str:
    return " ".join(str(r.cylinder) if r.arrival_ms == 0 else f"{r.cylinder}@{r.arrival_ms:g}"
                    for r in requests)


def parse_number(text: str, name: str, kind=float, minimum=None):
    try:
        value = kind(str(text).strip())
    except ValueError:
        what = "a whole number" if kind is int else "a number"
        raise ValueError(f"{name} must be {what}.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


def build_disk(cylinders: str, rpm: str, track_to_track_ms: str, full_stroke_ms: str,
               transfer_ms: str, rotation_mode: str) -> DiskModel:
    return DiskModel(
        cylinders=parse_number(cylinders, "Disk size", int, 1),
        rpm=parse_number(rpm, "RPM", int, 1),
        track_to_track_ms=parse_number(track_to_track_ms, "Track-to-track seek", float, 0),
        full_stroke_ms=parse_number(full_stroke_ms, "Full-stroke seek", float, 0),
        transfer_ms=parse_number(transfer_ms, "Transfer time", float, 0),
        rotation_mode=rotation_mode,
    )
