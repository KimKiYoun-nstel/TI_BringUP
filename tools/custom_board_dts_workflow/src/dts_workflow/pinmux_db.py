from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


def normalize_name(value: str) -> str:
    text = (value or "").strip().upper().replace("/", "_").replace("-", "_")
    if text.startswith("SOC_"):
        text = text[4:]
    if text.startswith("AM") and "_" in text:
        prefix, rest = text.split("_", 1)
        if any(ch.isdigit() for ch in prefix):
            text = rest
    return text


@dataclass
class PinmuxDB:
    rows: list[dict[str, str]]
    rows_by_ball_signal: dict[tuple[str, str], list[dict[str, str]]]
    rows_by_ball_device: dict[tuple[str, str], list[dict[str, str]]]
    rows_by_ball: dict[str, list[dict[str, str]]]


def load_pinmux_db(csv_path: Path) -> PinmuxDB:
    with csv_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    rows_by_ball_signal: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    rows_by_ball_device: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    rows_by_ball: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        ball = row.get("ball", "").upper()
        rows_by_ball[ball].append(row)
        rows_by_ball_signal[(ball, normalize_name(row.get("signal_name", "")))].append(row)
        rows_by_ball_device[(ball, normalize_name(row.get("device_pin_name", "")))].append(row)

    return PinmuxDB(
        rows=rows,
        rows_by_ball_signal=dict(rows_by_ball_signal),
        rows_by_ball_device=dict(rows_by_ball_device),
        rows_by_ball=dict(rows_by_ball),
    )
