#!/usr/bin/env python3
"""Collect the fixed five-run multiclass Qbv ON validation campaign."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tools" / "p2_qbv_multiclass_pilot.py"
KST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--duration-sec", type=int, default=300)
    parser.add_argument("--background-rate", default="500M")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def now_kst():
    return datetime.now(KST).isoformat(timespec="seconds")


def main():
    args = parse_args()
    if args.runs != 5 or args.duration_sec != 300:
        raise SystemExit("formal campaign is fixed at five 300-second runs")
    artifact_dir = args.artifact_dir or ROOT / "artifacts" / f"qbv-multiclass-01-{datetime.now(KST):%Y%m%d-%H%M%S-kst}"
    if artifact_dir.exists() and not args.resume:
        raise SystemExit(f"artifact directory already exists: {artifact_dir}")
    if not artifact_dir.exists():
        artifact_dir.mkdir(parents=True)
        write_json(artifact_dir / "manifest.json", {
            "test_id": "QBV_MULTICLASS_01", "runs": args.runs,
            "duration_sec": args.duration_sec, "background_rate_requested": args.background_rate,
            "schedule": ["TC2: 0x4 500000", "TC1: 0x2 250000", "TC0: 0x1 250000"],
            "created_at_kst": now_kst(),
        })
    status_path = artifact_dir / "campaign-status.json"
    completed = []
    write_json(status_path, {"state": "running", "completed_runs": completed, "updated_at_kst": now_kst()})
    try:
        for index in range(1, args.runs + 1):
            run_dir = artifact_dir / f"run-{index:02d}"
            if run_dir.exists():
                command = [sys.executable, str(PILOT), "--duration-sec", str(args.duration_sec),
                           "--artifact-dir", str(run_dir), "--summarize-only"]
                print(f"[{now_kst()}] revalidating run-{index:02d}", flush=True)
            else:
                command = [sys.executable, str(PILOT), "--duration-sec", str(args.duration_sec),
                           "--background-rate", args.background_rate, "--artifact-dir", str(run_dir),
                           "--start-sequence", str(31_000_000 + index * 500_000),
                           "--test-id", "QBV_MULTICLASS_01"]
                print(f"[{now_kst()}] starting run-{index:02d}", flush=True)
            subprocess.run(command, check=True)
            summary = json.loads((run_dir / "summary.json").read_text(encoding="ascii"))
            if not summary["valid"]:
                raise RuntimeError(f"run-{index:02d} failed its validity gate")
            if f"run-{index:02d}" not in completed:
                completed.append(f"run-{index:02d}")
            write_json(status_path, {"state": "running", "completed_runs": completed, "updated_at_kst": now_kst()})
            print(f"[{now_kst()}] passed run-{index:02d}", flush=True)
    except BaseException as error:
        write_json(status_path, {"state": "failed", "completed_runs": completed,
                                 "error": str(error), "updated_at_kst": now_kst()})
        raise
    summaries = [json.loads((artifact_dir / name / "summary.json").read_text(encoding="ascii")) for name in completed]
    write_json(artifact_dir / "campaign-summary.json", {
        "valid": all(summary["valid"] for summary in summaries), "runs": summaries,
    })
    write_json(status_path, {"state": "passed", "completed_runs": completed, "updated_at_kst": now_kst()})


if __name__ == "__main__":
    main()
