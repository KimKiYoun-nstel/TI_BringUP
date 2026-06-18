#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import select
import socket
import sys
import threading
from pathlib import Path

from uart_endpoint import DEFAULT_TARGETS_FILE
from uart_endpoint import Endpoint
from uart_endpoint import EndpointConfigError
from uart_endpoint import endpoint_from_options

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    tty = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

ATTACH_ESCAPE = 0x1D  # Ctrl-]


class UartCtlError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UART daemon client")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None, help="uartd Unix socket path")
    transport.add_argument("--tcp", default=None, help="uartd TCP endpoint HOST:PORT")
    parser.add_argument("--target", default=None, help="Named UART target from tools/uart/targets.json")
    parser.add_argument("--targets-file", default=str(DEFAULT_TARGETS_FILE), help="UART target profile JSON path")
    parser.add_argument("--connect-timeout", type=float, default=10.0)
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


def endpoint_from_args(args: argparse.Namespace) -> Endpoint:
    try:
        return endpoint_from_options(
            tcp=args.tcp,
            socket_path=args.socket,
            target=args.target,
            targets_file=args.targets_file,
        )
    except EndpointConfigError as exc:
        raise UartCtlError(str(exc)) from exc


def connect_endpoint(endpoint: Endpoint, timeout: float = 10.0) -> socket.socket:
    if endpoint.kind == "tcp":
        assert endpoint.host is not None and endpoint.port is not None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((endpoint.host, endpoint.port))
        sock.settimeout(None)
        return sock

    if not hasattr(socket, "AF_UNIX"):
        raise UartCtlError("Unix socket transport is not available on this platform. Use --tcp HOST:PORT.")
    assert endpoint.socket_path is not None
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(str(endpoint.socket_path))
    sock.settimeout(None)
    return sock


def send_request(endpoint: Endpoint, payload: dict, timeout: float = 10.0) -> socket.socket:
    sock = connect_endpoint(endpoint, timeout=timeout)
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


def run_status(endpoint: Endpoint, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "status"}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_send(endpoint: Endpoint, text: str, newline: bool, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "send", "text": text, "newline": newline}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "send failed"))
    return 0


def run_expect(endpoint: Endpoint, pattern: str, timeout: float, fresh: bool, from_offset: int | None, connect_timeout: float) -> int:
    payload: dict[str, object] = {"action": "expect", "pattern": pattern, "timeout": timeout}
    if fresh:
        payload["from"] = "fresh"
    if from_offset is not None:
        payload["from_offset"] = from_offset
    with send_request(endpoint, payload, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "expect failed"))
    print(json.dumps(response, ensure_ascii=False))
    return 0


def run_command(
    endpoint: Endpoint,
    text: str,
    expect: str,
    timeout: float,
    fresh: bool,
    from_offset: int | None,
    newline: bool,
    connect_timeout: float,
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
    with send_request(endpoint, payload, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "command failed"))
    print(json.dumps(response, ensure_ascii=False))
    return 0


def run_tail(endpoint: Endpoint, lines: int, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "tail", "lines": lines}, timeout=connect_timeout) as sock:
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


def run_attach(endpoint: Endpoint, mode: str, backlog_lines: int, connect_timeout: float) -> int:
    sock = connect_endpoint(endpoint, timeout=connect_timeout)
    try:
        payload = {"action": "attach", "mode": mode, "backlog_lines": backlog_lines}
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        response = recv_json_line(sock)
        if not response.get("ok"):
            raise UartCtlError(response.get("error", "attach failed"))

        if mode == "ro":
            return _watch_stream(sock)
        if os.name == "nt":
            return _attach_stream_windows(sock)
        return _attach_stream_posix(sock)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _write_stdout_bytes(data: bytes) -> None:
    try:
        os.write(sys.stdout.fileno(), data)
    except OSError:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def _watch_stream(sock: socket.socket) -> int:
    while True:
        data = sock.recv(4096)
        if not data:
            return 0
        _write_stdout_bytes(data)


def _socket_to_stdout(sock: socket.socket, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            data = sock.recv(4096)
        except OSError:
            stop_event.set()
            return
        if not data:
            stop_event.set()
            return
        _write_stdout_bytes(data)


def _attach_stream_windows(sock: socket.socket) -> int:
    if msvcrt is None:
        raise UartCtlError("Windows console support is unavailable")
    kbhit = getattr(msvcrt, "kbhit", None)
    getch = getattr(msvcrt, "getch", None)
    if kbhit is None or getch is None:
        raise UartCtlError("Windows console support is incomplete")

    stop_event = threading.Event()
    reader = threading.Thread(target=_socket_to_stdout, args=(sock, stop_event), daemon=True)
    reader.start()

    sys.stderr.write("[uartctl] attached mode=rw, shared_write=true. detach: Ctrl-] then q\n")
    sys.stderr.flush()
    escaped = False

    while not stop_event.is_set():
        if not kbhit():
            stop_event.wait(0.02)
            continue
        data = getch()
        if not data:
            continue
        value = data[0]
        if escaped:
            if value == ord("q"):
                stop_event.set()
                return 0
            if value == ATTACH_ESCAPE:
                payload = bytes([ATTACH_ESCAPE])
            else:
                payload = bytes([ATTACH_ESCAPE]) + data
            escaped = False
        elif value == ATTACH_ESCAPE:
            escaped = True
            continue
        else:
            payload = data
        if payload:
            sock.sendall(payload)
    return 0


def _attach_stream_posix(sock: socket.socket) -> int:
    if termios is None or tty is None:
        raise UartCtlError("POSIX terminal control is unavailable")

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


def run_stop(endpoint: Endpoint, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "stop"}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    if not response.get("ok"):
        raise UartCtlError(response.get("error", "stop failed"))
    print("uartd stopping")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    endpoint = endpoint_from_args(args)

    try:
        if args.command == "status":
            return run_status(endpoint, args.connect_timeout)
        if args.command == "send":
            return run_send(endpoint, args.text, args.newline, args.connect_timeout)
        if args.command == "expect":
            return run_expect(endpoint, args.pattern, args.timeout, args.fresh, args.from_offset, args.connect_timeout)
        if args.command == "command":
            return run_command(
                endpoint,
                args.text,
                args.expect,
                args.timeout,
                args.fresh,
                args.from_offset,
                not args.no_newline,
                args.connect_timeout,
            )
        if args.command == "attach":
            return run_attach(endpoint, mode="rw", backlog_lines=args.backlog_lines, connect_timeout=args.connect_timeout)
        if args.command == "watch":
            return run_attach(endpoint, mode="ro", backlog_lines=args.backlog_lines, connect_timeout=args.connect_timeout)
        if args.command == "tail":
            return run_tail(endpoint, args.lines, args.connect_timeout)
        if args.command == "stop":
            return run_stop(endpoint, args.connect_timeout)
    except (OSError, UartCtlError, EndpointConfigError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
