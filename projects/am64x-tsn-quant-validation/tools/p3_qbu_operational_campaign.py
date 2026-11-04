#!/usr/bin/env python3
"""Run and aggregate the P3 Qbu/IET operational-envelope traffic matrix."""

import argparse
import collections
import json
import statistics
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "p3_qbu_fragmentation.py"
DEFAULT_MATRIX = ROOT / "config" / "p3-qbu-operational-matrix.json"
KST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--artifact-dir", type=Path)
    return parser.parse_args()


def write_status(campaign_dir, state, **details):
    status = {"state": state, "updated_at": datetime.now(KST).isoformat(), **details}
    (campaign_dir / "campaign-status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="ascii")


def run_case(case, mode, test_id, run_dir, stage_tools):
    command = [
        "python3", str(RUNNER), "--artifact-dir", str(run_dir), "--test-id", test_id,
        "--case-id", case["case_id"], "--mode", mode,
        "--duration-sec", str(case["duration_sec"]),
        "--preemptible-rate", case["preemptible_rate"],
        "--preemptible-length", str(case["preemptible_length"]),
        "--express-rate", case["express_rate"],
        "--express-length", str(case["express_length"]),
    ]
    if not stage_tools:
        command.append("--skip-stage-tools")
    for field, option in (("preemptible_cpu", "--preemptible-cpu"),
                          ("express_cpu", "--express-cpu"),
                          ("pacing_timer_us", "--pacing-timer-us"),
                          ("receiver_rmem_default", "--receiver-rmem-default"),
                          ("tx_min_frag_size", "--tx-min-frag-size"),
                          ("telemetry_interval_sec", "--telemetry-interval-sec")):
        if field in case:
            command.extend((option, str(case[field])))
    timeout_sec = case["duration_sec"] + 600
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_sec)
        result = {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired:
        result = {
            "exit_code": 124,
            "stdout": "",
            "stderr": f"P3 run exceeded the {timeout_sec}-second host timeout.",
        }
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        result["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        result["summary"] = None
    transport_path = run_dir / "transport-status.json"
    result["transport"] = (json.loads(transport_path.read_text(encoding="utf-8"))
                           if transport_path.exists() else None)
    return result


def number_summary(values):
    values = [value for value in values if isinstance(value, (int, float))]
    if not values:
        return None
    return {
        "count": len(values), "min": min(values), "median": statistics.median(values), "max": max(values),
    }


def mode_result(record, mode):
    summary = record.get("summary")
    if not summary:
        return None
    return summary.get("modes", {}).get(mode)


def aggregate_case(case, mode, records):
    samples = [mode_result(record, mode) for record in records]
    samples = [sample for sample in samples if sample is not None]
    usable = [sample for sample in samples if sample["measurement_valid"]]
    classifications = collections.Counter(sample["classification"] for sample in samples)
    active = sum(sample["activation_observed"] for sample in usable)
    duration = case["duration_sec"]
    def counters(name):
        return [value / duration for sample in usable
                if isinstance((value := sample["counters"][name]), (int, float))]
    flows = lambda name, key: [sample["flows"][name][key] for sample in usable]
    if mode == "on":
        if not usable:
            envelope = "invalid"
        elif any(sample["classification"] in {"degraded", "inactive-degraded"} for sample in usable):
            envelope = "degraded"
        elif active == 0:
            envelope = "inactive"
        elif active == len(usable):
            envelope = "active"
        else:
            envelope = "intermittent"
    else:
        if len(usable) != len(records) or any(
                sample["classification"] == "control-failed" for sample in usable):
            envelope = "control-failed"
        elif any(sample["classification"] == "control-degraded" for sample in usable):
            envelope = "control-degraded"
        else:
            envelope = "control-pass"
    return {
        "case": case,
        "mode": mode,
        "run_count": len(records),
        "measurement_valid_runs": len(usable),
        "classifications": dict(classifications),
        "activation_probability": active / len(usable) if mode == "on" and usable else None,
        "operational_region": envelope,
        "sender_fragment_per_sec": number_summary(counters("sender_fragment")),
        "receiver_fragment_per_sec": number_summary(counters("receiver_fragment")),
        "receiver_assembly_ok_per_sec": number_summary(counters("receiver_assembly_ok")),
        "receiver_assembly_error_per_sec": number_summary(counters("receiver_assembly_error")),
        "receiver_smd_error_per_sec": number_summary(counters("receiver_smd_error")),
        "preemptible_sent_bps": number_summary(flows("preemptible", "sent_bps")),
        "preemptible_received_bps": number_summary(flows("preemptible", "server_received_bps")),
        "express_sent_bps": number_summary(flows("express", "sent_bps")),
        "express_received_bps": number_summary(flows("express", "server_received_bps")),
        "preemptible_lost_packets": number_summary(flows("preemptible", "lost_packets")),
        "express_lost_packets": number_summary(flows("express", "lost_packets")),
    }


def require_accepted_baseline(matrix):
    baseline = matrix.get("baseline")
    if not baseline or baseline.get("status") != "accepted":
        raise SystemExit("P3 campaign requires an accepted activation baseline record")
    return baseline


def enforce_baseline_gate(matrix, case, mode, records):
    baseline = matrix["baseline"]
    aggregate = aggregate_case(case, mode, records)
    if mode == "off":
        if aggregate["operational_region"] == "control-failed":
            raise SystemExit("P3 negative control failed; refusing to run the on-case matrix")
        return
    if case["case_id"] != baseline["golden_case_id"]:
        return
    if (len(records) < baseline["required_repeats"] or
            aggregate["measurement_valid_runs"] < baseline["minimum_measurement_valid_runs"] or
            aggregate["activation_probability"] < baseline["minimum_activation_probability"]):
        raise SystemExit("P3 activation baseline failed; refusing to run the remaining matrix")


def enforce_run_acceptance(matrix, case, mode, record):
    acceptance = matrix.get("run_acceptance")
    if not acceptance or mode != "on" or case["case_id"] != acceptance["case_id"]:
        return
    sample = mode_result(record, mode)
    if sample is None:
        raise SystemExit("P3 acceptance run has no summary")
    failures = []
    if acceptance.get("require_active") and sample["classification"] != "active":
        failures.append(f"classification={sample['classification']}")
    if acceptance.get("require_loss_free") and not sample["loss_free"]:
        failures.append("packet loss observed")
    if acceptance.get("require_errors_ok") and not sample["errors_ok"]:
        failures.append("assembly/SMD error observed")
    if failures:
        raise SystemExit("P3 run acceptance failed: " + ", ".join(failures))


def main():
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    require_accepted_baseline(matrix)
    campaign_dir = args.artifact_dir or ROOT / "artifacts" / (
        f"p3-qbu-operational-{datetime.now(KST):%Y%m%d-%H%M%S-kst}")
    campaign_dir.mkdir(parents=True)
    (campaign_dir / "matrix.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="ascii")
    write_status(campaign_dir, "running", completed_runs=0)

    plan = [(matrix["negative_control"], "off")] + [(case, "on") for case in matrix["on_cases"]]
    records_by_case = {}
    tools_staged = False
    completed_runs = 0
    for case, mode in plan:
        records = []
        for repeat in range(1, case["repeats"] + 1):
            run_dir = campaign_dir / "runs" / case["case_id"] / f"run-{repeat:02d}"
            write_status(campaign_dir, "running", current_case=case["case_id"],
                         current_repeat=repeat, completed_runs=completed_runs)
            record = run_case(case, mode, matrix["test_id"], run_dir, stage_tools=not tools_staged)
            if record["exit_code"] == 0:
                tools_staged = True
            record["repeat"] = repeat
            (run_dir / "campaign-record.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="ascii")
            records.append(record)
            completed_runs += 1
            if record["exit_code"] != 0:
                write_status(campaign_dir, "failed", current_case=case["case_id"],
                             current_repeat=repeat, completed_runs=completed_runs,
                             reason=record["stderr"])
                raise SystemExit("P3 run failed; refusing to continue the campaign")
            try:
                enforce_run_acceptance(matrix, case, mode, record)
            except SystemExit as error:
                write_status(campaign_dir, "failed", current_case=case["case_id"],
                             current_repeat=repeat, completed_runs=completed_runs, reason=str(error))
                raise
        records_by_case[case["case_id"]] = (case, mode, records)
        try:
            enforce_baseline_gate(matrix, case, mode, records)
        except SystemExit as error:
            write_status(campaign_dir, "failed", current_case=case["case_id"],
                         completed_runs=completed_runs, reason=str(error))
            raise

    cases = [aggregate_case(case, mode, records) for case, mode, records in records_by_case.values()]
    valid = all(
        item["operational_region"] != "invalid" and
        (item["mode"] != "off" or item["operational_region"] != "control-failed")
        for item in cases)
    summary = {
        "test_id": matrix["test_id"], "baseline": matrix["baseline"], "valid": valid,
        "purpose": "Qbu/IET operational-envelope characterization, not latency A/B.",
        "cases": cases,
    }
    (campaign_dir / "campaign-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    write_status(campaign_dir, "completed", completed_runs=completed_runs, valid=valid)
    if not valid:
        raise SystemExit("P3 campaign contains invalid measurements or a failed negative control")


if __name__ == "__main__":
    main()
