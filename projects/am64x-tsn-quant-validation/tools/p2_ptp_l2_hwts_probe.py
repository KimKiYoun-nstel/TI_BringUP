#!/usr/bin/env python3
"""Qualify CPSW PTPv2 L2 raw hardware timestamps with sequence pairing."""

import argparse
import csv
import fcntl
import json
import select
import socket
import struct
import time


ETH_P_1588 = 0x88F7
PTP_MULTICAST = bytes.fromhex("011b19000000")
SIOCGIFHWADDR = 0x8927
SO_TIMESTAMPING = 37
SCM_TIMESTAMPING = 37
SO_PRIORITY = 12
SOL_PACKET = 263
PACKET_ADD_MEMBERSHIP = 1
PACKET_MR_MULTICAST = 0
PACKET_IGNORE_OUTGOING = 23
MSG_ERRQUEUE = socket.MSG_ERRQUEUE

SOF_TIMESTAMPING_TX_HARDWARE = 1 << 0
SOF_TIMESTAMPING_TX_SOFTWARE = 1 << 1
SOF_TIMESTAMPING_RX_HARDWARE = 1 << 2
SOF_TIMESTAMPING_RX_SOFTWARE = 1 << 3
SOF_TIMESTAMPING_SOFTWARE = 1 << 4
SOF_TIMESTAMPING_RAW_HARDWARE = 1 << 6
TIMESPEC_SET = struct.Struct("qqqqqq")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("send", "recv"))
    parser.add_argument("--iface", required=True)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--start-seq", type=int, default=1)
    parser.add_argument("--interval-ms", type=float, default=20.0)
    parser.add_argument("--timeout-sec", type=float, default=10.0)
    parser.add_argument("--vlan-id", type=int, default=0)
    parser.add_argument("--pcp", type=int, default=0)
    parser.add_argument("--socket-priority", type=int)
    parser.add_argument("--frame-size", type=int, default=128)
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()
    minimum_frame_size = 44 + (18 if args.vlan_id else 14)
    if args.frame_size < minimum_frame_size:
        parser.error(f"--frame-size must be at least {minimum_frame_size} bytes")
    return args


def interface_mac(iface):
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        request = struct.pack("256s", iface.encode())
        result = fcntl.ioctl(probe.fileno(), SIOCGIFHWADDR, request)
    finally:
        probe.close()
    return result[18:24]


def timestamp_flags(mode):
    common = SOF_TIMESTAMPING_SOFTWARE | SOF_TIMESTAMPING_RAW_HARDWARE
    if mode == "send":
        return common | SOF_TIMESTAMPING_TX_HARDWARE | SOF_TIMESTAMPING_TX_SOFTWARE
    return common | SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_RX_SOFTWARE


def timestamp_from_cmsgs(cmsgs):
    for level, ctype, data in cmsgs:
        if level != socket.SOL_SOCKET or ctype != SCM_TIMESTAMPING or len(data) < TIMESPEC_SET.size:
            continue
        values = TIMESPEC_SET.unpack_from(data)
        for source, index in (("raw_hw", 4), ("hw", 2), ("sw", 0)):
            sec, nsec = values[index], values[index + 1]
            if sec or nsec:
                return source, sec * 1_000_000_000 + nsec
    return "none", None


def make_ptp_sync(source_mac, sequence, vlan_id, pcp, frame_size):
    ptp = bytearray(44)
    ptp[0] = 0x00  # Sync event message.
    ptp[1] = 0x02  # PTP version 2.
    ptp[2:4] = len(ptp).to_bytes(2, "big")
    ptp[4] = 127  # Keep qualification frames out of the gPTP domain.
    ptp[6:8] = b"\x02\x00"  # twoStepFlag
    ptp[20:28] = source_mac[:3] + b"\xff\xfe" + source_mac[3:]
    ptp[28:30] = b"\x00\x01"
    ptp[30:32] = (sequence & 0xFFFF).to_bytes(2, "big")
    ptp[33] = 0x7F
    # Sync is two-step, so its originTimestamp is ignored. Retain a run-unique
    # sequence there because the on-wire PTP header sequence is only 16 bits.
    ptp[40:44] = sequence.to_bytes(4, "big")
    ethernet = PTP_MULTICAST + source_mac
    if vlan_id:
        tci = ((pcp & 0x7) << 13) | vlan_id
        ethernet += b"\x81\x00" + tci.to_bytes(2, "big")
    frame = ethernet + ETH_P_1588.to_bytes(2, "big") + ptp
    return frame + b"\x00" * (frame_size - len(frame))


def make_socket(args):
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_1588))
    sock.bind((args.iface, 0))
    mode = args.mode
    # Long runs can briefly queue timestamped PTP frames behind background NAPI work.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPING, timestamp_flags(mode))
    if mode == "send" and args.socket_priority is not None:
        sock.setsockopt(socket.SOL_SOCKET, SO_PRIORITY, args.socket_priority)
    if mode == "send":
        # Do not let this packet socket mistake its own transmitted PTP frame for
        # a TX timestamp event while waiting on the error queue.
        sock.setsockopt(SOL_PACKET, PACKET_IGNORE_OUTGOING, 1)
    sock.setblocking(False)
    if mode == "recv":
        membership = struct.pack("IHH8s", socket.if_nametoindex(args.iface), PACKET_MR_MULTICAST, 6, PTP_MULTICAST + b"\x00" * 2)
        sock.setsockopt(SOL_PACKET, PACKET_ADD_MEMBERSHIP, membership)
    return sock


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="ascii") as stream:
        writer = csv.DictWriter(stream, fieldnames=("sequence", "timestamp_source", "timestamp_ns"))
        writer.writeheader()
        writer.writerows(rows)


def frame_sequence(frame):
    ptp_offset = 18 if len(frame) >= 18 and frame[12:14] == b"\x81\x00" else 14
    if len(frame) < ptp_offset + 44 or frame[ptp_offset - 2:ptp_offset] != ETH_P_1588.to_bytes(2, "big"):
        return None
    # Ignore gPTP control traffic; only domain-127 Sync frames belong to this run.
    if frame[ptp_offset] != 0x00 or frame[ptp_offset + 4] != 127:
        return None
    return int.from_bytes(frame[ptp_offset + 40:ptp_offset + 44], "big")


def drain_tx_timestamps(sock, rows):
    while True:
        try:
            frame, cmsgs, _, _ = sock.recvmsg(2048, 256, MSG_ERRQUEUE)
        except BlockingIOError:
            return
        sequence = frame_sequence(frame)
        if sequence not in rows:
            continue
        source, timestamp_ns = timestamp_from_cmsgs(cmsgs)
        if source != "none":
            rows[sequence]["timestamp_source"] = source
            rows[sequence]["timestamp_ns"] = timestamp_ns


def send(args):
    sock = make_socket(args)
    source_mac = interface_mac(args.iface)
    rows = {}
    start = time.monotonic()
    try:
        for offset in range(args.count):
            sequence = args.start_seq + offset
            due = start + offset * args.interval_ms / 1000.0
            while time.monotonic() < due:
                remaining = due - time.monotonic()
                if remaining <= 0:
                    break
                ready, _, _ = select.select([sock], [], [], remaining)
                if ready:
                    drain_tx_timestamps(sock, rows)
            rows[sequence] = {"sequence": sequence, "timestamp_source": "none", "timestamp_ns": ""}
            sock.send(make_ptp_sync(source_mac, sequence, args.vlan_id, args.pcp, args.frame_size))
            drain_tx_timestamps(sock, rows)
        deadline = time.monotonic() + args.timeout_sec
        while any(row["timestamp_source"] == "none" for row in rows.values()) and time.monotonic() < deadline:
            ready, _, _ = select.select([sock], [], [], deadline - time.monotonic())
            if ready:
                drain_tx_timestamps(sock, rows)
    finally:
        sock.close()
    ordered_rows = [rows[args.start_seq + offset] for offset in range(args.count)]
    write_csv(args.csv, ordered_rows)
    return ordered_rows


def recv(args):
    sock = make_socket(args)
    rows = []
    deadline = time.monotonic() + args.timeout_sec
    try:
        while len(rows) < args.count and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            ready, _, _ = select.select([sock], [], [], remaining)
            if not ready:
                break
            frame, cmsgs, _, _ = sock.recvmsg(2048, 256)
            sequence = frame_sequence(frame)
            if sequence is None:
                continue
            if not args.start_seq <= sequence < args.start_seq + args.count:
                continue
            source, timestamp_ns = timestamp_from_cmsgs(cmsgs)
            rows.append({"sequence": sequence, "timestamp_source": source, "timestamp_ns": timestamp_ns or ""})
    finally:
        sock.close()
    write_csv(args.csv, rows)
    return rows


def main():
    args = parse_args()
    rows = send(args) if args.mode == "send" else recv(args)
    sources = {}
    for row in rows:
        sources[row["timestamp_source"]] = sources.get(row["timestamp_source"], 0) + 1
    print(json.dumps({"mode": args.mode, "iface": args.iface, "count": len(rows), "sources": sources, "vlan_id": args.vlan_id, "pcp": args.pcp, "socket_priority": args.socket_priority, "frame_size": args.frame_size}, sort_keys=True))


if __name__ == "__main__":
    main()
