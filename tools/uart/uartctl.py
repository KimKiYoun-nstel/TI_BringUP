#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import select
import socket
import sys
import termios
import tty
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOCKET_PATH = REPO_ROOT / "logs" / "uartd.sock"
ATTACH_ESCAPE = 0x1D


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
    expect_parser.add_argument("--fresh", action="store_true", help="Match only new UART output after this request")
    expect_parser.add_argument("--from-offset", type=int, default=None, help="Match only output at or after this daemon offset")

    command_parser = subparsers.add_parser("command")
    command_parser.add_argument("text")
    command_parser.add_argument("--expect", required=True, help="Pattern to wait for after sending the command")
    command_parser.add_argument("--timeout", type=float, default=30.0)
    command_parser.add_argument("--fresh", action="store_true", help="Wait only for new output after command send")
    command_parser.add_argument("--from-offset", type=int, default=None, help="Override match start offset")
    command_parser.add_argument("--no-newline", action="store_true", help="Do not append newline when sending")

    attach_parser = subparsers.add_parser("attach")
    attach_parser.add_argument("--backlog-lines", type=int, default=0)

    watch_parser = subparsers.add_parser("watch")
    watch_parser.add_argument("--backlog-lines", type=int, default=100)

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


def run_expect(socket_path: Path, pattern: str, timeout: float, fresh: bool, from_offset: int | None) -> int:
    payload: dict[str, object] = {"action": "expect", "pattern": pattern, "timeout": timeout}
    if fresh:
        payload["from"] = "fresh"
    if from_offset is not None:
        payload["from_offset"] = from_offset
    with send_request(socket_path, payload) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "expect failed"))
    print(json.dumps(response, ensure_ascii=False))
    return 0


def run_command(
    socket_path: Path,
    text: str,
    expect: str,
    timeout: float,
    fresh: bool,
    from_offset: int | None,
    newline: bool,
) -> int:
    payload: dict[str, object] = {
        "action": "send_expect",
        "text": text,
        "expect": expect,
        "timeout": timeout,
        "newline": newline,
    }
    if fresh:
        payload["from"] = "fresh"
    if from_offset is not None:
        payload["from_offset"] = from_offset
    with send_request(socket_path, payload) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "command failed"))
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


def run_attach(socket_path: Path, mode: str, backlog_lines: int) -> int:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        payload = {"action": "attach", "mode": mode, "backlog_lines": backlog_lines}
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        response = recv_json_line(sock)
        if not response.get("ok"):
            raise UartCtlError(response.get("error", "attach failed"))

        if mode == "ro":
            return _watch_stream(sock)
        return _attach_stream(sock)
    finally:
        sock.close()


def _watch_stream(sock: socket.socket) -> int:
    while True:
        data = sock.recv(4096)
        if not data:
            return 0
        os.write(sys.stdout.fileno(), data)


def _attach_stream(sock: socket.socket) -> int:
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    old_attrs = termios.tcgetattr(stdin_fd)
    escaped = False

    try:
        tty.setraw(stdin_fd)
        sys.stderr.write("[uartctl] attached mode=rw, shared_write=true. detach: Ctrl-] then q\n")
        sys.stderr.flush()

        while True:
            readable, _, _ = select.select([sock, stdin_fd], [], [])

            if sock in readable:
                data = sock.recv(4096)
                if not data:
                    return 0
                os.write(stdout_fd, data)

            if stdin_fd in readable:
                data = os.read(stdin_fd, 4096)
                if not data:
                    return 0

                output = bytearray()
                for value in data:
                    if escaped:
                        if value == ord("q"):
                            return 0
                        if value == ATTACH_ESCAPE:
                            output.append(ATTACH_ESCAPE)
                        else:
                            output.append(ATTACH_ESCAPE)
                            output.append(value)
                        escaped = False
                        continue

                    if value == ATTACH_ESCAPE:
                        escaped = True
                        continue

                    output.append(value)

                if output:
                    sock.sendall(bytes(output))
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)


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
            return run_expect(socket_path, args.pattern, args.timeout, args.fresh, args.from_offset)
        if args.command == "command":
            return run_command(
                socket_path,
                args.text,
                args.expect,
                args.timeout,
                args.fresh,
                args.from_offset,
                not args.no_newline,
            )
        if args.command == "attach":
            return run_attach(socket_path, mode="rw", backlog_lines=args.backlog_lines)
        if args.command == "watch":
            return run_attach(socket_path, mode="ro", backlog_lines=args.backlog_lines)
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
