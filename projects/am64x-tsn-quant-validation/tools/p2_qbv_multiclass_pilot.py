#!/usr/bin/env python3
"""Qualify a three-class Qbv schedule without requiring line-rate traffic."""

import argparse
import csv
import json
import math
import re
import shlex
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
UARTCTL = ROOT.parents[1] / "tools" / "uart" / "uartctl.py"
TMDS = ["ssh", "-o", "BatchMode=yes", "root@192.168.0.220"]
REMOTE_TOOLS = "/tmp/p2-qbv-on-tools"
KST = timezone(timedelta(hours=9))
CYCLE_NS = 1_000_000
TC0_CAPACITY_BPS = 250_000_000


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=int, default=60)
    parser.add_argument("--background-rate", default="500M")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--start-sequence", type=int, default=31_000_000)
    parser.add_argument("--test-id", default="QBV_MULTICLASS_01_PILOT")
    parser.add_argument("--summarize-only", action="store_true")
    return parser.parse_args()


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def uart(target, command, timeout=30, capture_output=False):
    return run(
        [str(UARTCTL), "--target", target, "command", command, "--expect", "# ",
         "--timeout", str(timeout)],
        capture_output=capture_output,
    )


def uart_text(target, command):
    return json.loads(uart(target, command, capture_output=True).stdout).get("output", "")


def stage_tools():
    run(TMDS + [f"rm -rf {REMOTE_TOOLS}; mkdir -p {REMOTE_TOOLS}"])
    for name in ("p2_ptp_l2_hwts_sender.c", "p2_ptp_l2_hwts_probe.py",
                 "p2_qbv_sender_run.sh", "p2_qbv_receiver_run.sh"):
        run(["scp", "-o", "BatchMode=yes", str(TOOLS / name),
             f"root@192.168.0.220:{REMOTE_TOOLS}/{name}"])
    run(TMDS + [
        f"chmod 0755 {REMOTE_TOOLS}/p2_ptp_l2_hwts_probe.py {REMOTE_TOOLS}/p2_qbv_receiver_run.sh; "
        f"ssh -o BatchMode=yes root@10.33.0.1 mkdir -p {REMOTE_TOOLS}; "
        f"scp -o BatchMode=yes {REMOTE_TOOLS}/p2_ptp_l2_hwts_sender.c root@10.33.0.1:{REMOTE_TOOLS}/; "
        f"scp -o BatchMode=yes {REMOTE_TOOLS}/p2_ptp_l2_hwts_probe.py root@10.33.0.1:{REMOTE_TOOLS}/; "
        f"scp -o BatchMode=yes {REMOTE_TOOLS}/p2_qbv_sender_run.sh root@10.33.0.1:{REMOTE_TOOLS}/"
    ])
    run(TMDS + [
        f"ssh -o BatchMode=yes root@10.33.0.1 "
        f"'gcc -std=c11 -Wall -Wextra -Werror -O2 {REMOTE_TOOLS}/p2_ptp_l2_hwts_sender.c "
        f"-o {REMOTE_TOOLS}/p2_native_sender && chmod 0755 {REMOTE_TOOLS}/p2_native_sender {REMOTE_TOOLS}/p2_qbv_sender_run.sh'"
    ])


def apply_multiclass_schedule():
    uart("sk",
         "BASE=$(phc_ctl /dev/ptp0 get | awk '/clock time/ {split($5,a,\".\"); printf \"%.0f\", (a[1]+3)*1000000000}'); "
         "tc qdisc del dev eth0 root 2>/dev/null || true; "
         "tc qdisc add dev eth0 root handle 100 taprio num_tc 3 map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 "
         "queues 1@0 1@1 1@2 base-time \"$BASE\" "
         "sched-entry S 0x4 500000 sched-entry S 0x2 250000 sched-entry S 0x1 250000 flags 0x2")
    output = uart_text("sk", "tc -s qdisc show dev eth0")
    required = ("flags 0x2", "gatemask 0x4 interval 500000",
                "gatemask 0x2 interval 250000", "gatemask 0x1 interval 250000")
    missing = [item for item in required if item not in output]
    if missing:
        raise RuntimeError(f"multiclass Qbv schedule is not active: missing {missing}")


def restore_all_open():
    uart("sk",
         "BASE=$(phc_ctl /dev/ptp0 get | awk '/clock time/ {split($5,a,\".\"); printf \"%.0f\", (a[1]+3)*1000000000}'); "
         "tc qdisc del dev eth0 root 2>/dev/null || true; "
         "tc qdisc add dev eth0 root handle 100 taprio num_tc 3 map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 "
         "queues 1@0 1@1 1@2 base-time \"$BASE\" sched-entry S 0x7 1000000 flags 0x2")


def start_receiver(name, sequence, timeout_sec, sample_count):
    uart("tmds",
         f"RUN=/tmp/{name}; export RUN; rm -rf $RUN; mkdir -p $RUN; "
         f"RUN=$RUN SEQUENCE={sequence} TIMEOUT_SEC={timeout_sec} SAMPLE_COUNT={sample_count} "
         f"{REMOTE_TOOLS}/p2_qbv_receiver_run.sh > /tmp/{name}-receiver-runner.log 2>&1 & echo $! > $RUN/runner.pid")


def start_sender(name, sequence, duration_sec, background_rate, sample_count):
    uart("sk",
         f"RUN=/tmp/{name}; export RUN; rm -rf $RUN; mkdir -p $RUN; "
         f"RUN=$RUN SEQUENCE={sequence} DURATION_SEC={duration_sec} BACKGROUND_RATE={background_rate} "
         f"SAMPLE_COUNT={sample_count} RELEASE_PHASE_NS=0 ENQUEUE_ADVANCE_NS=450000 "
         f"{REMOTE_TOOLS}/p2_qbv_sender_run.sh > /tmp/{name}-sender-runner.log 2>&1 & echo $! > $RUN/runner.pid")


def runner_state(target, name):
    return uart_text(target,
                     f"RUN=/tmp/{name}; cat $RUN/progress.txt 2>/dev/null || true; cat $RUN/done 2>/dev/null || true")


def wait_for_completion(name, timeout_sec):
    deadline = datetime.now().timestamp() + timeout_sec
    while datetime.now().timestamp() < deadline:
        sk = runner_state("sk", name)
        tmds = runner_state("tmds", name)
        if "failed" in sk or "failed" in tmds:
            raise RuntimeError(f"target runner failed: SK={sk!r} TMDS={tmds!r}")
        if "passed" in sk and "passed" in tmds:
            return
        subprocess.run(["sleep", "5"], check=True)
    raise RuntimeError("pilot timed out")


def snapshot_tmds_after(name):
    uart("tmds",
         f"RUN=/tmp/{name}; pmc -u -b 0 'GET TIME_STATUS_NP' > $RUN/ptp-health-after.txt 2>&1; "
         "pmc -u -b 0 'GET PORT_DATA_SET' > $RUN/ptp-port-after.txt 2>&1; "
         "tc -s qdisc show dev eth1 > $RUN/qos-after.txt; ethtool -S eth1 > $RUN/counters-after.txt")


def fetch_tree(remote_host, remote_dir, destination):
    archive = destination.with_suffix(".tar")
    with archive.open("wb") as stream:
        subprocess.run(["ssh", "-o", "BatchMode=yes", remote_host,
                        f"tar -C /tmp -cf - {remote_dir.name}"], check=True, stdout=stream)
    with tarfile.open(archive) as stream:
        stream.extractall(destination.parent)
    archive.unlink()
    (destination.parent / remote_dir.name).rename(destination)


def collect(name, artifact_dir):
    fetch_tree("root@192.168.0.220", Path(name), artifact_dir / "tmds")
    archive = artifact_dir / "sk.tar"
    with archive.open("wb") as stream:
        subprocess.run(TMDS + [f"ssh -o BatchMode=yes root@10.33.0.1 tar -C /tmp -cf - {name}"],
                       check=True, stdout=stream)
    with tarfile.open(archive) as stream:
        stream.extractall(artifact_dir)
    archive.unlink()
    (artifact_dir / name).rename(artifact_dir / "sk")


def iperf_bps(path, key):
    text = path.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):])
    return data["end"][key]["bits_per_second"]


def tc_stats(path, parent):
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"qdisc [^\n]*parent {re.escape(parent)}[^\n]*\n Sent (\d+) bytes (\d+) pkt \(dropped (\d+)", text)
    if not match:
        raise RuntimeError(f"cannot read {parent} qdisc statistics")
    assert match is not None
    return tuple(map(int, match.groups()))


def raw_rows(path):
    rows = []
    with path.open(newline="", encoding="ascii") as stream:
        for row in csv.DictReader(stream):
            if row["timestamp_source"] == "raw_hw" and row["planned_phc_ns"]:
                rows.append((int(row["timestamp_ns"]), int(row["planned_phc_ns"])))
    return rows


def percentile(values, fraction):
    return values[max(0, math.ceil(len(values) * fraction) - 1)]


def summarize(artifact_dir, sample_count):
    sender_rows = raw_rows(artifact_dir / "sk" / "sender.csv")
    receiver = json.loads((artifact_dir / "tmds" / "receiver.log").read_text(encoding="utf-8"))
    schedule = (artifact_dir / "sk" / "qos-after.txt").read_text(encoding="utf-8")
    base_match = re.search(r"base-time (\d+)", schedule)
    if not base_match:
        raise RuntimeError("cannot read taprio base-time")
    base = int(base_match.group(1))
    release = sorted(timestamp - planned for timestamp, planned in sender_rows)
    phases = sorted((timestamp - base) % CYCLE_NS for timestamp, _ in sender_rows)
    tc0_before = tc_stats(artifact_dir / "sk" / "qos-before.txt", "100:1")
    tc0_after = tc_stats(artifact_dir / "sk" / "qos-after.txt", "100:1")
    background_sent = iperf_bps(artifact_dir / "sk" / "background-client.json", "sum_sent")
    background_received = iperf_bps(artifact_dir / "tmds" / "background-server.json", "sum_received")
    result = {
        "valid": False,
        "schedule": ["0x4 500000", "0x2 250000", "0x1 250000"],
        "critical_raw_hw": len(sender_rows),
        "receiver_count": receiver["count"],
        "receiver_raw_hw": receiver.get("sources", {}).get("raw_hw"),
        "critical_release_p99_ns": percentile(release, .99) if release else None,
        "critical_tx_phase_min_ns": phases[0] if phases else None,
        "critical_tx_phase_p99_ns": percentile(phases, .99) if phases else None,
        "critical_tx_phase_max_ns": phases[-1] if phases else None,
        "background_source_bps": background_sent,
        "background_receiver_bps": background_received,
        "tc0_sent_bytes_delta": tc0_after[0] - tc0_before[0],
        "tc0_sent_packets_delta": tc0_after[1] - tc0_before[1],
        "tc0_dropped_packets_delta": tc0_after[2] - tc0_before[2],
        "gptp_port_after": (artifact_dir / "tmds" / "ptp-port-after.txt").read_text(encoding="utf-8"),
    }
    result["valid"] = (
        result["critical_raw_hw"] == sample_count
        and result["receiver_count"] == sample_count
        and result["receiver_raw_hw"] == sample_count
        and result["critical_tx_phase_min_ns"] is not None
        and result["critical_tx_phase_max_ns"] < 500_000
        and result["critical_release_p99_ns"] < 500_000
        and result["background_source_bps"] > TC0_CAPACITY_BPS
        and result["background_receiver_bps"] > TC0_CAPACITY_BPS * .80
        and result["tc0_dropped_packets_delta"] > 0
        and "portState               SLAVE" in result["gptp_port_after"]
    )
    (artifact_dir / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return result


def main():
    args = parse_args()
    if not 30 <= args.duration_sec <= 300:
        raise SystemExit("--duration-sec must be in 30..300")
    sample_count = args.duration_sec * 1000
    if args.summarize_only:
        if args.artifact_dir is None:
            raise SystemExit("--summarize-only requires --artifact-dir")
        summary = summarize(args.artifact_dir, sample_count)
        if not summary["valid"]:
            raise RuntimeError(f"multiclass summary failed validity gates: {summary}")
        return
    name = f"p2-qbv-multiclass-pilot-{datetime.now(KST):%Y%m%d-%H%M%S-kst}"
    artifact_dir = args.artifact_dir or ROOT / "artifacts" / name
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "test_id": args.test_id, "duration_sec": args.duration_sec,
        "background_rate_requested": args.background_rate, "critical_samples": sample_count,
        "schedule": ["TC2: 0x4 500000", "TC1: 0x2 250000", "TC0: 0x1 250000"],
    }, indent=2, sort_keys=True) + "\n", encoding="ascii")
    stage_tools()
    try:
        apply_multiclass_schedule()
        start_receiver(name, args.start_sequence, args.duration_sec + 90, sample_count)
        start_sender(name, args.start_sequence, args.duration_sec, args.background_rate, sample_count)
        wait_for_completion(name, args.duration_sec + 100)
        snapshot_tmds_after(name)
        collect(name, artifact_dir)
        summary = summarize(artifact_dir, sample_count)
        if not summary["valid"]:
            raise RuntimeError(f"multiclass pilot failed validity gates: {summary}")
    finally:
        restore_all_open()


if __name__ == "__main__":
    main()
