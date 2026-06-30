#!/usr/bin/env python3
import argparse
import ctypes
import json
import os
import socket
import struct
import threading
import time


SO_TIMESTAMPING = 37
SCM_TIMESTAMPING = 37

SOF_TIMESTAMPING_TX_HARDWARE = 1 << 0
SOF_TIMESTAMPING_TX_SOFTWARE = 1 << 1
SOF_TIMESTAMPING_SOFTWARE = 1 << 4
SOF_TIMESTAMPING_RAW_HARDWARE = 1 << 6
SOF_TIMESTAMPING_OPT_TSONLY = 1 << 11

MSG_ERRQUEUE = socket.MSG_ERRQUEUE

TIMESPEC_SET = struct.Struct("qqqqqq")

CLOCK_REALTIME = 0
CLOCKFD = 3


class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


libc = ctypes.CDLL("libc.so.6", use_errno=True)
libc.clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(Timespec)]
libc.clock_gettime.restype = ctypes.c_int


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest-ip", required=True)
    parser.add_argument("--ports", nargs="+", type=int, required=True)
    parser.add_argument("--duration-sec", type=float, default=4.0)
    parser.add_argument("--payload-len", type=int, default=1472)
    parser.add_argument("--rate-bps", type=float, required=True)
    parser.add_argument("--cycle-ns", type=int, default=0)
    parser.add_argument("--base-time-ns", type=int, default=0)
    parser.add_argument("--phc-device")
    parser.add_argument("--phase-step-ns", type=int, default=1000)
    parser.add_argument("--window", action="append", default=[])
    parser.add_argument("--start-delay-sec", type=float, default=0.0)
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def parse_windows(window_args):
    windows = {}
    for spec in window_args:
        port_s, start_s, dur_s = spec.split(":")
        windows[int(port_s)] = (int(start_s), int(dur_s))
    return windows


def clock_gettime_ns(clock_id):
    ts = Timespec()
    if libc.clock_gettime(clock_id, ctypes.byref(ts)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return ts.tv_sec * 1_000_000_000 + ts.tv_nsec


def fd_to_clockid(fd):
    return ((~fd) << 3) | CLOCKFD


def read_phc_and_realtime_ns(phc_device):
    fd = os.open(phc_device, os.O_RDONLY)
    try:
        phc_clock_id = fd_to_clockid(fd)
        rt_before = clock_gettime_ns(CLOCK_REALTIME)
        phc_ns = clock_gettime_ns(phc_clock_id)
        rt_after = clock_gettime_ns(CLOCK_REALTIME)
    finally:
        os.close(fd)
    rt_ns = (rt_before + rt_after) // 2
    return {"phc_ns": phc_ns, "realtime_ns": rt_ns, "offset_ns": phc_ns - rt_ns}


def make_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    flags = (
        SOF_TIMESTAMPING_TX_HARDWARE
        | SOF_TIMESTAMPING_TX_SOFTWARE
        | SOF_TIMESTAMPING_SOFTWARE
        | SOF_TIMESTAMPING_RAW_HARDWARE
        | SOF_TIMESTAMPING_OPT_TSONLY
    )
    sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPING, flags)
    sock.settimeout(0.5)
    return sock


def recv_hwts_ns(sock):
    while True:
        try:
            _, ancdata, _, _ = sock.recvmsg(256, 256, MSG_ERRQUEUE)
        except TimeoutError:
            return None
        except BlockingIOError:
            return None
        for level, ctype, data in ancdata:
            if level != socket.SOL_SOCKET or ctype != SCM_TIMESTAMPING:
                continue
            if len(data) < TIMESPEC_SET.size:
                continue
            ts = TIMESPEC_SET.unpack_from(data[: TIMESPEC_SET.size])
            sec = ts[4]
            nsec = ts[5]
            if sec or nsec:
                return "raw_hw", sec * 1_000_000_000 + nsec
            sec = ts[2]
            nsec = ts[3]
            if sec or nsec:
                return "hw", sec * 1_000_000_000 + nsec
            sec = ts[0]
            nsec = ts[1]
            if sec or nsec:
                return "sw", sec * 1_000_000_000 + nsec


def flow_worker(dest_ip, port, payload_len, duration_sec, rate_bps, start_delay_sec, out):
    sock = make_socket()
    addr = (dest_ip, port)
    payload = b"x" * payload_len
    interval = (payload_len * 8) / rate_bps
    if start_delay_sec:
        time.sleep(start_delay_sec)
    deadline = time.monotonic() + duration_sec
    next_send = time.monotonic()
    out[port] = {
        "raw_hw_ns": [],
        "hw_ns": [],
        "sw_ns": [],
        "sent_bytes": 0,
        "send_calls": 0,
    }

    while True:
        now = time.monotonic()
        if now >= deadline:
            break
        if now < next_send:
            time.sleep(next_send - now)
            continue
        out[port]["sent_bytes"] += sock.sendto(payload, addr)
        out[port]["send_calls"] += 1
        next_send += interval
        ts = recv_hwts_ns(sock)
        if ts is not None:
            source, ts_ns = ts
            out[port][f"{source}_ns"].append(ts_ns)

    end_wait = time.monotonic() + 1.0
    while time.monotonic() < end_wait:
        ts = recv_hwts_ns(sock)
        if ts is None:
            break
        source, ts_ns = ts
        out[port][f"{source}_ns"].append(ts_ns)

    sock.close()


def percentile_mid(values):
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    if n % 2:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2


def summarize(flow_data, cycle_ns, base_time_ns, windows):
    summary = {}
    for port, data in flow_data.items():
        source = None
        tx = []
        for name in ("raw_hw", "hw", "sw"):
            values = sorted(data[f"{name}_ns"])
            if values:
                source = name
                tx = values
                break
        item = {
            "sent_bytes": data["sent_bytes"],
            "send_calls": data["send_calls"],
            "timestamped_packets": len(tx),
            "timestamp_source": source,
            "first_tx_hw_ns": tx[0] if tx else None,
            "last_tx_hw_ns": tx[-1] if tx else None,
        }
        if cycle_ns and tx:
            phases = [((ns - base_time_ns) % cycle_ns) for ns in tx]
            item["median_phase_ns"] = percentile_mid(phases)
            if port in windows:
                start_ns, dur_ns = windows[port]
                in_window = sum(1 for phase in phases if start_ns <= phase < start_ns + dur_ns)
                item["in_window_ratio"] = in_window / len(phases)
                item["leakage_ratio"] = 1.0 - item["in_window_ratio"]
        summary[port] = item
    return summary


def summarize_with_sweep(flow_data, cycle_ns, base_time_ns, windows, step_ns):
    per_port = {}
    chosen = {}
    for port, data in flow_data.items():
        source = None
        tx = []
        for name in ("raw_hw", "hw", "sw"):
            values = sorted(data[f"{name}_ns"])
            if values:
                source = name
                tx = values
                break
        per_port[port] = {
            "timestamp_source": source,
            "tx": tx,
            "sent_bytes": data["sent_bytes"],
            "send_calls": data["send_calls"],
        }
        chosen[port] = tx

    if not cycle_ns or not windows:
        return {"flows": summarize(flow_data, cycle_ns, base_time_ns, windows)}

    best = None
    offset = 0
    while offset < cycle_ns:
        score = 0.0
        leak = 0
        total = 0
        per_offset = {}
        for port, tx in chosen.items():
            phases = [((ns - base_time_ns - offset) % cycle_ns) for ns in tx]
            total += len(phases)
            if port not in windows:
                continue
            start_ns, dur_ns = windows[port]
            in_window = sum(1 for phase in phases if start_ns <= phase < start_ns + dur_ns)
            leak += len(phases) - in_window
            ratio = in_window / len(phases) if phases else 0.0
            score += ratio
            per_offset[port] = {
                "median_phase_ns": percentile_mid(phases),
                "in_window_ratio": ratio,
                "packet_count": len(phases),
            }
        cand = {
            "score": score,
            "offset_ns": offset,
            "leakage_ratio": (leak / total) if total else 1.0,
            "per_port": per_offset,
        }
        if best is None or cand["score"] > best["score"]:
            best = cand
        offset += step_ns

    if best is None:
        return {"best_offset_ns": None, "leakage_ratio": None, "flows": summarize(flow_data, cycle_ns, base_time_ns, windows)}

    result = {"best_offset_ns": best["offset_ns"], "leakage_ratio": best["leakage_ratio"], "flows": {}}
    for port, data in per_port.items():
        flow = {
            "sent_bytes": data["sent_bytes"],
            "send_calls": data["send_calls"],
            "timestamp_source": data["timestamp_source"],
            "timestamped_packets": len(data["tx"]),
            "first_tx_hw_ns": data["tx"][0] if data["tx"] else None,
            "last_tx_hw_ns": data["tx"][-1] if data["tx"] else None,
        }
        if port in best["per_port"]:
            flow.update(best["per_port"][port])
        result["flows"][port] = flow
    return result


def main():
    args = parse_args()
    windows = parse_windows(args.window)
    phc_samples = {}
    if args.phc_device:
        phc_samples["before"] = read_phc_and_realtime_ns(args.phc_device)
    flow_data = {}
    threads = []
    for port in args.ports:
        thread = threading.Thread(
            target=flow_worker,
            args=(
                args.dest_ip,
                port,
                args.payload_len,
                args.duration_sec,
                args.rate_bps,
                args.start_delay_sec,
                flow_data,
            ),
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    if args.phc_device:
        phc_samples["after"] = read_phc_and_realtime_ns(args.phc_device)

    if args.phc_device:
        avg_offset_ns = (
            phc_samples["before"]["offset_ns"] + phc_samples["after"]["offset_ns"]
        ) // 2
        for data in flow_data.values():
            if data["sw_ns"] and not data["raw_hw_ns"] and not data["hw_ns"]:
                data["sw_ns"] = [ns + avg_offset_ns for ns in data["sw_ns"]]

    result = {
        "dest_ip": args.dest_ip,
        "ports": args.ports,
        "duration_sec": args.duration_sec,
        "payload_len": args.payload_len,
        "rate_bps": args.rate_bps,
        "cycle_ns": args.cycle_ns,
        "base_time_ns": args.base_time_ns,
        "phc_device": args.phc_device,
        "phc_samples": phc_samples,
    }
    result.update(
        summarize_with_sweep(
            flow_data,
            args.cycle_ns,
            args.base_time_ns,
            windows,
            args.phase_step_ns,
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
