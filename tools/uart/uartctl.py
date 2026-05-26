#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOCKET_PATH = REPO_ROOT / "logs" / "uartd.sock"


class UartCtlError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UART daemon client")
    parser.add_argument("--socket", default=str(DEFAULT_SOCKET_PATH), help="uartd Unix socket path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("text")
    send_parser.add_argument("--newline", action="store_true")

    expect_parser = subparsers.add_parser("expect")
    expect_parser.add_argument("pattern")
    expect_parser.add_argument("--timeout", type=float, default=30.0)

    tail_parser = subparsers.add_parser("tail")
    tail_parser.add_argument("--lines", type=int, default=200)

    subparsers.add_parser("stop")
    return parser


def send_request(socket_path: Path, payload: dict) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(socket_path))
    sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    return sock


def recv_json_line(sock: socket.socket) -> dict:
    buffer = ""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise UartCtlError("uartd closed the connection")
        buffer += chunk.decode("utf-8", errors="replace")
        if "\n" not in buffer:
            continue
        line, _rest = buffer.split("\n", 1)
        if not line.strip():
            continue
        return json.loads(line)


def run_status(socket_path: Path) -> int:
    with send_request(socket_path, {"action": "status"}) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_send(socket_path: Path, text: str, newline: bool) -> int:
    with send_request(socket_path, {"action": "send", "text": text, "newline": newline}) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "send failed"))
    return 0


def run_expect(socket_path: Path, pattern: str, timeout: float) -> int:
    with send_request(socket_path, {"action": "expect", "pattern": pattern, "timeout": timeout}) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "expect failed"))
    print(json.dumps(response, ensure_ascii=False))
    return 0


def run_tail(socket_path: Path, lines: int) -> int:
    with send_request(socket_path, {"action": "tail", "lines": lines}) as sock:
        response = recv_json_line(sock)
        if not response.get("ok"):
            raise UartCtlError(response.get("error", "tail failed"))
        backlog = response.get("backlog", "")
        if backlog:
            sys.stdout.write(backlog)
            sys.stdout.flush()
        while True:
            event = recv_json_line(sock)
            if event.get("type") == "data":
                sys.stdout.write(event.get("data", ""))
                sys.stdout.flush()


def run_stop(socket_path: Path) -> int:
    with send_request(socket_path, {"action": "stop"}) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "stop failed"))
    print("uartd stopping")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    socket_path = Path(args.socket)

    try:
        if args.command == "status":
            return run_status(socket_path)
        if args.command == "send":
            return run_send(socket_path, args.text, args.newline)
        if args.command == "expect":
            return run_expect(socket_path, args.pattern, args.timeout)
        if args.command == "tail":
            return run_tail(socket_path, args.lines)
        if args.command == "stop":
            return run_stop(socket_path)
    except (OSError, UartCtlError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
