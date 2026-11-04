#!/usr/bin/env python3
"""Run the P3 Qbu 1 Gbps fragmentation off/on control and summarize it."""

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
UARTCTL = ROOT.parents[1] / "tools" / "uart" / "uartctl.py"
UART_TCP = {"sk": "192.168.0.55:17003", "tmds": "192.168.0.55:17002"}
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null"]
TMDS_SSH_HOST = os.environ.get("P3_TMDS_SSH_HOST", "192.168.0.59")
SK_ARTIFACT_SSH = "timeout 60 ssh -o BatchMode=yes -o StrictHostKeyChecking=no"
REMOTE_TOOLS = "/tmp/p3-qbu-tools"
UART_STAGE_CHUNK_BYTES = 512
KST = timezone(timedelta(hours=9))
SK_IP = "10.33.0.1"
TMDS_IP = "10.33.0.2"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=int, default=30)
    parser.add_argument("--preemptible-rate", default="200M")
    parser.add_argument("--express-rate", default="50M")
    parser.add_argument("--preemptible-length", type=int, default=1472)
    parser.add_argument("--express-length", type=int, default=1472)
    parser.add_argument("--preemptible-cpu", type=int)
    parser.add_argument("--express-cpu", type=int)
    parser.add_argument("--pacing-timer-us", type=int)
    parser.add_argument("--receiver-rmem-default", type=int)
    parser.add_argument("--tx-min-frag-size", type=int, choices=(60, 124, 188, 252), default=124)
    parser.add_argument("--telemetry-interval-sec", type=int)
    parser.add_argument("--mode", choices=("off", "on", "both"), default="on")
    parser.add_argument("--case-id", default="golden-baseline")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--test-id", default="QBU_1G_OPERATIONAL_01")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--skip-stage-tools", action="store_true")
    return parser.parse_args()


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def uart(target, command, timeout=60, capture_output=False):
    return run(
        [sys.executable, str(UARTCTL), "--tcp", UART_TCP[target], "command", command, "--expect", "# ",
         "--timeout", str(timeout)],
        capture_output=capture_output,
    )


def uart_text(target, command, timeout=60):
    return json.loads(uart(target, command, timeout=timeout, capture_output=True).stdout).get("output", "")


def stage_tools():
    runner = TOOLS / "p3_qbu_endpoint_run.sh"
    payload = base64.b64encode(gzip.compress(runner.read_bytes())).decode("ascii")
    digest = hashlib.sha256(runner.read_bytes()).hexdigest()
    for target in ("sk", "tmds"):
        encoded = f"{REMOTE_TOOLS}/p3_qbu_endpoint_run.sh.gz.b64"
        uart(target, f"mkdir -p {REMOTE_TOOLS}; : > {encoded}", capture_output=True)
        for offset in range(0, len(payload), UART_STAGE_CHUNK_BYTES):
            chunk = payload[offset:offset + UART_STAGE_CHUNK_BYTES]
            uart(target, f"printf %s {shlex.quote(chunk)} >> {encoded}", capture_output=True)
        command = (
            f"base64 -d {encoded} | gzip -d > {REMOTE_TOOLS}/p3_qbu_endpoint_run.sh; rm -f {encoded}; "
            f"chmod 0755 {REMOTE_TOOLS}/p3_qbu_endpoint_run.sh"
        )
        uart(target, command, capture_output=True)
        output = uart_text(target, f"sha256sum {REMOTE_TOOLS}/p3_qbu_endpoint_run.sh")
        match = re.search(r"\b([0-9a-f]{64})\b", output)
        if not match or match.group(1) != digest:
            raise RuntimeError(f"P3 UART stage verification failed on {target}")


def endpoint(target, name, mode, action, duration_sec, preemptible_rate, express_rate,
              preemptible_length, express_length, preemptible_cpu=None, express_cpu=None,
              pacing_timer_us=None, receiver_rmem_default=None, tx_min_frag_size=124,
              telemetry_interval_sec=None):
    if target == "sk":
        role, dev, sibling_dev, local_ip, peer_ip = "receiver", "eth1", "eth0", SK_IP, TMDS_IP
    else:
        role, dev, sibling_dev, local_ip, peer_ip = "sender", "eth1", "eth0", TMDS_IP, SK_IP
    variables = {
        "RUN": f"/tmp/{name}/{mode}", "ROLE": role, "MODE": mode, "ACTION": action,
        "DEV": dev, "SIBLING_DEV": sibling_dev, "LOCAL_IP": local_ip, "PEER_IP": peer_ip,
        "DURATION_SEC": str(duration_sec), "PREEMPTIBLE_RATE": preemptible_rate,
        "EXPRESS_RATE": express_rate, "PREEMPTIBLE_LENGTH": str(preemptible_length),
        "EXPRESS_LENGTH": str(express_length),
        "PREEMPTIBLE_CPU": "" if preemptible_cpu is None else str(preemptible_cpu),
        "EXPRESS_CPU": "" if express_cpu is None else str(express_cpu),
        "PACING_TIMER_US": "" if pacing_timer_us is None else str(pacing_timer_us),
        "RECEIVER_RMEM_DEFAULT": "" if receiver_rmem_default is None else str(receiver_rmem_default),
        "TX_MIN_FRAG_SIZE": str(tx_min_frag_size),
        "TELEMETRY_INTERVAL_SEC": "" if telemetry_interval_sec is None else str(telemetry_interval_sec),
    }
    command = " ".join(f"{key}={shlex.quote(value)}" for key, value in variables.items())
    command += f" {REMOTE_TOOLS}/p3_qbu_endpoint_run.sh"
    timeout = duration_sec + 90 if action == "send" else 90
    uart(target, command, timeout=timeout)


def run_mode(name, mode, args):
    traffic = (args.duration_sec, args.preemptible_rate, args.express_rate,
               args.preemptible_length, args.express_length, args.preemptible_cpu,
               args.express_cpu, args.pacing_timer_us, args.receiver_rmem_default,
               args.tx_min_frag_size, args.telemetry_interval_sec)
    for target in ("sk", "tmds"):
        endpoint(target, name, mode, "setup", *traffic)
    if mode == "on":
        require_sender_mm_ready()
    for target in ("sk", "tmds"):
        endpoint(target, name, mode, "snapshot-before", *traffic)
        endpoint(target, name, mode, "peer-proof", *traffic)
    endpoint("sk", name, mode, "serve", *traffic)
    if args.telemetry_interval_sec is not None:
        endpoint("sk", name, mode, "start-telemetry", *traffic)
        endpoint("tmds", name, mode, "start-telemetry", *traffic)
    endpoint("tmds", name, mode, "send", *traffic)
    if args.telemetry_interval_sec is not None:
        endpoint("tmds", name, mode, "stop-telemetry", *traffic)
        endpoint("sk", name, mode, "stop-telemetry", *traffic)
    for target in ("sk", "tmds"):
        endpoint(target, name, mode, "snapshot-after", *traffic)


def read_link_state():
    return {"sk-eth1": uart_text("sk", "ethtool eth1"),
            "tmds-eth1": uart_text("tmds", "ethtool eth1")}


def prepare_tmds_data_link():
    """Restore the known reboot-time admin-down state before link preflight."""
    uart_text("tmds", "ip link set dev eth1 up; sleep 5; ethtool eth1", timeout=90)


def require_sender_mm_ready():
    state = uart_text("tmds", "ethtool --show-mm eth1")
    required = ("pMAC enabled: on", "TX enabled: on", "TX active: on",
                "Verification status: SUCCEEDED")
    missing = [item for item in required if item not in state]
    if missing:
        raise RuntimeError(f"P3 requires TMDS eth1 sender MAC Merge readiness: {missing}")


def require_1g_link(state):
    required = ("Speed: 1000Mb/s", "Duplex: Full", "Link detected: yes")
    missing = {target: [item for item in required if item not in text]
               for target, text in state.items()}
    missing = {target: items for target, items in missing.items() if items}
    if missing:
        raise RuntimeError(f"P3 requires the live 1 Gbps/full SK eth1 <-> TMDS eth1 CPSW path: {missing}")
def tmds_ssh(host):
    return ["ssh", *SSH_OPTIONS, f"root@{host}"]


def recover_tmds_management_host():
    deadline = time.monotonic() + 90
    last_error = None
    while time.monotonic() < deadline:
        try:
            # Keep link recovery and address discovery as separate UART transactions.
            # The management link transition can otherwise consume the prompt that
            # the combined command is waiting for.
            uart_text("tmds", "ip link set dev eth0 up", timeout=90)
            output = uart_text("tmds", "ip -4 -o addr show dev eth0 scope global", timeout=90)
        except subprocess.CalledProcessError as error:
            last_error = str(error)
            time.sleep(5)
            continue
        match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", output)
        if match:
            return match.group(1)
        time.sleep(5)
    detail = f"; last UART error: {last_error}" if last_error else ""
    raise RuntimeError("P3 artifact collection could not recover a TMDS eth0 management address" + detail)


def fetch_ssh_tree(command, remote_dir, destination, tmds_host):
    name = Path(remote_dir).name
    archive = destination.with_suffix(".tar")
    deadline = time.monotonic() + 90
    last_error = None
    while time.monotonic() < deadline:
        archive.unlink(missing_ok=True)
        try:
            with archive.open("wb") as stream:
                subprocess.run(tmds_ssh(tmds_host) + [command], check=True, stdout=stream,
                               timeout=max(1, int(deadline - time.monotonic())))
            with tarfile.open(archive) as stream:
                stream.extractall(destination.parent)
            archive.unlink()
            (destination.parent / name).rename(destination)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, tarfile.TarError) as error:
            last_error = error
            archive.unlink(missing_ok=True)
            if time.monotonic() + 5 >= deadline:
                break
            time.sleep(5)
    raise RuntimeError(f"P3 artifact collection did not recover within 90 seconds: {last_error}")


def collect(name, artifact_dir):
    tmds_host = recover_tmds_management_host()
    (artifact_dir / "artifact-transport.json").write_text(json.dumps({
        "tmds_management_host": tmds_host,
        "discovery": "UART eth0 IPv4 after cleanup",
    }, indent=2, sort_keys=True) + "\n", encoding="ascii")
    fetch_ssh_tree(f"tar -C /tmp -cf - {shlex.quote(name)}", name, artifact_dir / "tmds", tmds_host)
    fetch_ssh_tree(f"{SK_ARTIFACT_SSH} root@10.33.0.1 tar -C /tmp -cf - {shlex.quote(name)}",
                   name, artifact_dir / "sk", tmds_host)


def write_transport_status(artifact_dir, state, **details):
    (artifact_dir / "transport-status.json").write_text(
        json.dumps({"state": state, **details}, indent=2, sort_keys=True) + "\n",
        encoding="ascii")


def counter_value(text, names):
    for name in names:
        match = re.search(rf"(?m)^\s*{re.escape(name)}:\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def counter_delta(before, after, names):
    old = counter_value(before.read_text(encoding="utf-8"), names)
    new = counter_value(after.read_text(encoding="utf-8"), names)
    return None if old is None or new is None else new - old


def json_value(data, paths):
    for path in paths:
        value = data
        try:
            for key in path:
                value = value[key]
        except KeyError:
            continue
        return value
    return None


def iperf_result(path):
    text = path.read_text(encoding="utf-8")
    json_start = text.find("{")
    if json_start < 0:
        raise ValueError(f"iperf3 JSON payload is missing: {path}")
    data = json.loads(text[json_start:])
    return {
        "sent_bps": json_value(data, (("end", "sum_sent", "bits_per_second"),)),
        "sent_packets": json_value(data, (("end", "sum_sent", "packets"),)),
        "received_bps": json_value(data, (("end", "sum_received", "bits_per_second"),
                                            ("end", "sum", "bits_per_second"))),
        "received_packets": json_value(data, (("end", "sum_received", "packets"),
                                                ("end", "sum", "packets"))),
        "lost_packets": json_value(data, (("end", "sum", "lost_packets"),
                                            ("end", "sum_received", "lost_packets"))),
    }


def rate_bps(value):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([KMG])", value, re.IGNORECASE)
    if not match:
        raise ValueError(f"unsupported rate: {value}")
    return float(match.group(1)) * {"K": 1e3, "M": 1e6, "G": 1e9}[match.group(2).upper()]


def flow_rate_ok(flow):
    sent_bps = flow["sent_bps"]
    if not isinstance(sent_bps, (int, float)):
        return False
    return sent_bps >= float(flow["requested_bps"]) * .90


def flow_loss_free(flow):
    return flow["lost_packets"] == 0


def positive_counter(value):
    return isinstance(value, int) and value > 0


def non_dominant_errors(assembly_ok, *errors):
    return isinstance(assembly_ok, int) and all(
        isinstance(error, int) and error <= assembly_ok for error in errors)


def filter_packet_counts(path):
    return [int(count) for count in re.findall(
        r"Sent \d+ bytes (\d+) pkt", path.read_text(encoding="utf-8"))]


def filter_class_hit(before, after):
    before_counts = filter_packet_counts(before)
    after_counts = filter_packet_counts(after)
    if len(before_counts) < 2 or len(before_counts) != len(after_counts):
        return False, []
    deltas = [new - old for old, new in zip(before_counts, after_counts)]
    return all(delta > 0 for delta in deltas), deltas


def mode_summary(artifact_dir, mode, args):
    sender = artifact_dir / "tmds" / mode
    receiver = artifact_dir / "sk" / mode
    sender_before = sender / "counters-before.txt"
    sender_after = sender / "counters-after.txt"
    receiver_before = receiver / "counters-before.txt"
    receiver_after = receiver / "counters-after.txt"
    deltas = {
        "sender_fragment": counter_delta(sender_before, sender_after, ("MACMergeFragCountTx", "iet_tx_frag")),
        "receiver_fragment": counter_delta(receiver_before, receiver_after, ("MACMergeFragCountRx", "iet_rx_frag")),
        "receiver_assembly_ok": counter_delta(receiver_before, receiver_after, ("MACMergeFrameAssOkCount", "iet_rx_assembly_ok")),
        "receiver_assembly_error": counter_delta(receiver_before, receiver_after, ("MACMergeFrameAssErrorCount", "iet_rx_assembly_err", "assembly_err")),
        "receiver_smd_error": counter_delta(receiver_before, receiver_after, ("MACMergeFrameSmdErrorCount", "iet_rx_smd_err", "smd_err")),
        "sender_tc2": counter_delta(sender_before, sender_after, ("tx_pri2",)),
        "sender_tc3": counter_delta(sender_before, sender_after, ("tx_pri3",)),
    }
    sender_mac = (sender / "local-mac.txt").read_text(encoding="ascii").strip().lower()
    receiver_mac = (receiver / "local-mac.txt").read_text(encoding="ascii").strip().lower()
    sender_peer = (sender / "peer-proof.txt").read_text(encoding="utf-8").lower()
    receiver_peer = (receiver / "peer-proof.txt").read_text(encoding="utf-8").lower()
    sender_link = (sender / "link-before.txt").read_text(encoding="utf-8")
    receiver_link = (receiver / "link-before.txt").read_text(encoding="utf-8")
    sender_mm = (sender / "mm-before.txt").read_text(encoding="utf-8")
    receiver_mm = (receiver / "mm-before.txt").read_text(encoding="utf-8")
    flows = {}
    for name, port, requested in (("preemptible", 5002, args.preemptible_rate),
                                  ("express", 5003, args.express_rate)):
        client = iperf_result(sender / f"traffic-{port}-client.json")
        server = iperf_result(receiver / f"traffic-{port}-server.json")
        flows[name] = {"requested_bps": rate_bps(requested), **client,
                       "server_received_bps": server["received_bps"],
                       "server_received_packets": server["received_packets"],
                       "lost_packets": server["lost_packets"]}
    link_ok = all(value in sender_link for value in ("Speed: 1000Mb/s", "Duplex: Full", "Link detected: yes"))
    link_ok = link_ok and all(value in receiver_link for value in ("Speed: 1000Mb/s", "Duplex: Full", "Link detected: yes"))
    peer_ok = receiver_mac in sender_peer and sender_mac in receiver_peer
    flow_rate_okay = all(flow_rate_ok(flow) for flow in flows.values())
    loss_free = all(flow_loss_free(flow) for flow in flows.values())
    class_hit, filter_deltas = filter_class_hit(
        sender / "filters-before.txt", sender / "filters-after.txt")
    hardware_class_hit = all(positive_counter(deltas[key]) for key in ("sender_tc2", "sender_tc3"))
    assembly_ok = deltas["receiver_assembly_ok"]
    errors_ok = non_dominant_errors(
        assembly_ok, deltas["receiver_assembly_error"], deltas["receiver_smd_error"])
    if mode == "on":
        mm_ok = all(item in sender_mm for item in (
            "pMAC enabled: on", "TX enabled: on", "TX active: on", "Verification status: SUCCEEDED"))
        mm_ok = mm_ok and all(item in receiver_mm for item in ("pMAC enabled: on", "TX enabled: on"))
        counter_ok = all(positive_counter(deltas[key]) for key in
                         ("sender_fragment", "receiver_fragment", "receiver_assembly_ok"))
    else:
        mm_ok = all(item in sender_mm for item in ("pMAC enabled: off", "TX enabled: off"))
        mm_ok = mm_ok and all(item in receiver_mm for item in ("pMAC enabled: off", "TX enabled: off"))
        counter_ok = all(deltas[key] == 0 for key in
                         ("sender_fragment", "receiver_fragment", "receiver_assembly_ok"))
    counter_readable = all(isinstance(value, int) for value in deltas.values())
    measurement_valid = link_ok and peer_ok and mm_ok and flow_rate_okay and class_hit and hardware_class_hit and counter_readable
    if not measurement_valid:
        classification = "invalid"
    elif mode == "off":
        if not counter_ok:
            classification = "control-failed"
        elif loss_free and errors_ok:
            classification = "control-pass"
        else:
            classification = "control-degraded"
    else:
        if not counter_ok:
            classification = "inactive" if loss_free and errors_ok else "inactive-degraded"
        else:
            classification = "active" if loss_free and errors_ok else "degraded"
    return {
        "valid": measurement_valid and (mode == "on" or classification != "control-failed"),
        "measurement_valid": measurement_valid, "activation_observed": mode == "on" and counter_ok,
        "classification": classification,
        "link_ok": link_ok, "peer_ok": peer_ok, "flow_rate_ok": flow_rate_okay,
        "loss_free": loss_free, "class_hit": class_hit, "hardware_class_hit": hardware_class_hit,
        "counter_readable": counter_readable,
        "filter_packet_deltas": filter_deltas, "mm_ok": mm_ok, "counter_ok": counter_ok,
        "errors_ok": errors_ok, "counters": deltas, "flows": flows,
    }


def summarize(artifact_dir, args):
    modes = ("off", "on") if args.mode == "both" else (args.mode,)
    result = {"test_id": args.test_id, "case_id": args.case_id, "mode": args.mode,
              "valid": False, "modes": {mode: mode_summary(artifact_dir, mode, args) for mode in modes}}
    result["valid"] = all(summary["valid"] for summary in result["modes"].values())
    (artifact_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return result


def cleanup(name, args):
    errors = []
    modes = ("off", "on") if args.mode == "both" else (args.mode,)
    for mode in modes:
        for target in ("sk", "tmds"):
            try:
                endpoint(target, name, mode, "cleanup", args.duration_sec,
                          args.preemptible_rate, args.express_rate,
                          args.preemptible_length, args.express_length,
                           args.preemptible_cpu, args.express_cpu, args.pacing_timer_us,
                           args.receiver_rmem_default, args.tx_min_frag_size,
                           args.telemetry_interval_sec)
            except subprocess.CalledProcessError as error:
                errors.append({"phase": "cleanup", "target": target, "mode": mode,
                               "error": str(error)})
    return errors


def reset_data_ports(name, args):
    errors = []
    for target in ("sk", "tmds"):
        try:
            endpoint(target, name, "off", "reset", args.duration_sec,
                     args.preemptible_rate, args.express_rate,
                     args.preemptible_length, args.express_length,
                     args.preemptible_cpu, args.express_cpu, args.pacing_timer_us,
                     args.receiver_rmem_default, args.tx_min_frag_size,
                     args.telemetry_interval_sec)
        except subprocess.CalledProcessError as error:
            errors.append({"phase": "reset", "target": target, "error": str(error)})
    return errors


def main():
    args = parse_args()
    if not 30 <= args.duration_sec <= 300:
        raise SystemExit("--duration-sec must be in 30..300")
    if args.pacing_timer_us is not None and not 1 <= args.pacing_timer_us <= 1_000_000:
        raise SystemExit("--pacing-timer-us must be in 1..1000000")
    if any(cpu is not None and cpu < 0 for cpu in (args.preemptible_cpu, args.express_cpu)):
        raise SystemExit("CPU affinity values must be non-negative")
    if args.telemetry_interval_sec is not None and args.telemetry_interval_sec < 1:
        raise SystemExit("--telemetry-interval-sec must be at least 1")
    if args.summarize_only:
        if args.artifact_dir is None:
            raise SystemExit("--summarize-only requires --artifact-dir")
        if not summarize(args.artifact_dir, args)["valid"]:
            raise RuntimeError("P3 Qbu summary failed validity gates")
        return

    name = f"p3-qbu-fragmentation-{datetime.now(KST):%Y%m%d-%H%M%S-kst}"
    artifact_dir = args.artifact_dir or ROOT / "artifacts" / name
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "test_id": args.test_id, "case_id": args.case_id, "mode": args.mode,
        "duration_sec": args.duration_sec,
        "path": "TMDS eth1 CPSW -> SK eth1 CPSW", "link": "1 Gbps/full existing direct path",
        "preemptible": {"port": 5002, "rate": args.preemptible_rate, "length": args.preemptible_length},
        "express": {"port": 5003, "rate": args.express_rate, "length": args.express_length},
        "generator": {"preemptible_cpu": args.preemptible_cpu, "express_cpu": args.express_cpu,
                      "pacing_timer_us": args.pacing_timer_us},
        "receiver_rmem_default": args.receiver_rmem_default,
        "artifact_transport": {"tmds_management_host": TMDS_SSH_HOST},
        "mac_merge": {"verify_enabled": True, "tx_min_frag_size": args.tx_min_frag_size},
    }, indent=2, sort_keys=True) + "\n", encoding="ascii")
    prepare_tmds_data_link()
    initial_link = read_link_state()
    (artifact_dir / "preflight-link.json").write_text(
        json.dumps(initial_link, indent=2, sort_keys=True) + "\n", encoding="ascii")
    require_1g_link(initial_link)
    if not args.skip_stage_tools:
        stage_tools()
    failure = None
    cleanup_errors = []
    reset_errors = []
    transport_error = None
    try:
        for mode in (("off", "on") if args.mode == "both" else (args.mode,)):
            run_mode(name, mode, args)
    except Exception as error:  # Preserve available raw evidence before reporting the failure.
        failure = error
    finally:
        try:
            cleanup_errors = cleanup(name, args)
            try:
                collect(name, artifact_dir)
            except Exception as error:
                transport_error = error
        finally:
            reset_errors = reset_data_ports(name, args)
    if transport_error:
        write_transport_status(artifact_dir, "transport-failed",
                               error=str(transport_error), cleanup_errors=cleanup_errors,
                               reset_errors=reset_errors,
                               run_error=str(failure) if failure else None)
    else:
        write_transport_status(artifact_dir, "collected", cleanup_errors=cleanup_errors,
                               reset_errors=reset_errors,
                               run_error=str(failure) if failure else None)
    if failure:
        raise failure
    if transport_error:
        raise transport_error
    result = summarize(artifact_dir, args)
    if not result["valid"]:
        raise RuntimeError("P3 Qbu fragmentation validity gates failed")


if __name__ == "__main__":
    main()
