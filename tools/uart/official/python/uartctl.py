#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import select
import socket
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from uart_api import JsonSocketReader, UARTAPIError

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


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SOCKET_PATH = REPO_ROOT / "logs" / "uartd.sock"
DEFAULT_TCP = "127.0.0.1:17001"
ATTACH_ESCAPE = 0x1D  # Ctrl-]


class UartCtlError(Exception):
    pass


@dataclass(frozen=True)
class Endpoint:
    kind: str  # "unix" or "tcp"
    socket_path: Path | None = None
    host: str | None = None
    port: int | None = None
    token: str | None = None
    response_timeout: float = 10.0

    @property
    def description(self) -> str:
        if self.kind == "tcp":
            return f"tcp://{self.host}:{self.port}"
        return f"unix://{self.socket_path}"


def parse_tcp_endpoint(value: str) -> tuple[str, int]:
    text = value.strip()
    if text.startswith("tcp://"):
        text = text[len("tcp://") :]
    if ":" not in text:
        raise argparse.ArgumentTypeError("TCP endpoint must be HOST:PORT")
    host, port_text = text.rsplit(":", 1)
    if not host:
        host = "127.0.0.1"
    try:
        port = int(port_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("TCP port must be an integer") from exc
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError("TCP port must be in 1..65535")
    return host, port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UART daemon client")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None, help="uartd Unix socket path")
    transport.add_argument("--tcp", default=None, help=f"uartd TCP endpoint HOST:PORT, e.g. {DEFAULT_TCP}")
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--response-timeout", type=float, default=10.0,
                        help="Control reply timeout; expect adds its own wait plus 6s write allowance")
    parser.add_argument("--token-file", help="UTF-8 access token file (or use UARTD_TOKEN env)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    baud_parser = subparsers.add_parser("baud", help="Change host UART baud without restarting uartd")
    baud_parser.add_argument("rate", type=int)
    subparsers.add_parser("ports", help="List serial ports on remote uartd host")
    port_parser = subparsers.add_parser("port", help="Select/replace serial port without stopping uartd")
    port_parser.add_argument("device", help="COM11, /dev/ttyUSB0, loop:// ...")
    port_parser.add_argument("--baud", type=int, default=None)
    port_parser.add_argument("--force", action="store_true", help="Switch despite connected RW attach users")
    disconnect_parser = subparsers.add_parser("disconnect", help="Disconnect current UART, keep TCP server alive")
    disconnect_parser.add_argument("--force", action="store_true")

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
    if args.token_file:
        token = Path(args.token_file).read_text(encoding="utf-8-sig").strip()
        if not token:
            raise UartCtlError("token file is empty")
    else:
        token = os.environ.get("UARTD_TOKEN", "").strip() or None
    if args.tcp or (os.name == "nt" and not args.socket):
        host, port = parse_tcp_endpoint(args.tcp or DEFAULT_TCP)
        return Endpoint(kind="tcp", host=host, port=port, token=token, response_timeout=args.response_timeout)
    socket_path = Path(args.socket) if args.socket else DEFAULT_SOCKET_PATH
    return Endpoint(kind="unix", socket_path=socket_path, token=token, response_timeout=args.response_timeout)


def connect_endpoint(endpoint: Endpoint, timeout: float = 10.0) -> socket.socket:
    if endpoint.kind == "tcp":
        assert endpoint.host is not None and endpoint.port is not None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((endpoint.host, endpoint.port))
        except OSError:
            sock.close()
            raise
        return sock

    if not hasattr(socket, "AF_UNIX"):
        raise UartCtlError("Unix socket transport is not available on this platform. Use --tcp HOST:PORT.")
    assert endpoint.socket_path is not None
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(endpoint.socket_path))
    except OSError:
        sock.close()
        raise
    return sock


def send_request(endpoint: Endpoint, payload: dict, timeout: float = 10.0) -> socket.socket:
    sock = connect_endpoint(endpoint, timeout=timeout)
    payload = payload.copy()
    if endpoint.token:
        payload["token"] = endpoint.token
    reply_timeout = endpoint.response_timeout
    if payload.get("action") in {"expect", "send_expect"}:
        wait = payload.get("timeout", 30)
        if type(wait) in (int, float) and 0 <= wait <= 3600 and math.isfinite(wait):
            reply_timeout = max(reply_timeout, wait + 6)
    sock.settimeout(reply_timeout)
    try:
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    except OSError:
        sock.close()
        raise
    return sock


def recv_json_line(sock: socket.socket) -> dict:
    return JsonSocketReader(sock).recv_json()


def run_ports(endpoint: Endpoint, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "list_ports"}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_port(endpoint: Endpoint, device: str, baud: int | None, force: bool, connect_timeout: float) -> int:
    payload: dict[str, object] = {"action": "set_port", "port": device, "force": force}
    if baud is not None:
        payload["baud"] = baud
    with send_request(endpoint, payload, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_disconnect(endpoint: Endpoint, force: bool, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "disconnect_port", "force": force}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_status(endpoint: Endpoint, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "status"}, timeout=connect_timeout) as sock:
        response = recv_json_line(sock)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def run_baud(endpoint: Endpoint, rate: int, connect_timeout: float) -> int:
    with send_request(endpoint, {"action": "baud", "baud": rate}, timeout=connect_timeout) as sock:
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
        reader = JsonSocketReader(sock)
        response = reader.recv_json()
        if not response.get("ok"):
            raise UartCtlError(response.get("error", "tail failed"))
        sock.settimeout(None)  # Long-lived stream, only handshake has a deadline.
        backlog = response.get("backlog", "")
        if backlog:
            sys.stdout.write(backlog)
            sys.stdout.flush()
        while True:
            event = reader.recv_json()
            if event.get("type") == "data":
                sys.stdout.write(event.get("data", ""))
                sys.stdout.flush()


def run_attach(endpoint: Endpoint, mode: str, backlog_lines: int, connect_timeout: float) -> int:
    sock = connect_endpoint(endpoint, timeout=connect_timeout)
    try:
        payload = {"action": "attach", "mode": mode, "backlog_lines": backlog_lines}
        if endpoint.token:
            payload["token"] = endpoint.token
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        reader = JsonSocketReader(sock)
        response = reader.recv_json()
        first_raw = reader.take_remaining()
        if not response.get("ok"):
            raise UartCtlError(response.get("error", "attach failed"))
        sock.settimeout(None)

        if mode == "ro":
            return _watch_stream(sock, first_raw)
        if os.name == "nt":
            return _attach_stream_windows(sock, first_raw)
        return _attach_stream_posix(sock, first_raw)
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


def _watch_stream(sock: socket.socket, first_raw: bytes = b"") -> int:
    if first_raw:
        _write_stdout_bytes(first_raw)
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


def _attach_stream_windows(sock: socket.socket, first_raw: bytes = b"") -> int:
    if first_raw:
        _write_stdout_bytes(first_raw)
    if msvcrt is None:
        raise UartCtlError("Windows console support is unavailable")

    stop_event = threading.Event()
    reader = threading.Thread(target=_socket_to_stdout, args=(sock, stop_event), daemon=True)
    reader.start()

    sys.stderr.write("[uartctl] attached mode=rw, shared_write=true. detach: Ctrl-] then q\n")
    sys.stderr.flush()
    escaped = False

    while not stop_event.is_set():
        try:
            if not msvcrt.kbhit():
                stop_event.wait(0.02)
                continue
            data = msvcrt.getch()
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
        except KeyboardInterrupt:
            # On Windows, Ctrl+C is delivered to Python as SIGINT instead of
            # being returned by msvcrt.getch(). Convert it back to the UART
            # control character ETX (0x03) and keep attach mode running.
            escaped = False
            sock.sendall(b"\x03")
    return 0


def _attach_stream_posix(sock: socket.socket, first_raw: bytes = b"") -> int:
    if first_raw:
        _write_stdout_bytes(first_raw)
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
    try:
        if any(not math.isfinite(value) or value <= 0 for value in (args.connect_timeout, args.response_timeout)):
            raise UartCtlError("connect/response timeout must be finite and positive")
        endpoint = endpoint_from_args(args)
        if args.command == "status":
            return run_status(endpoint, args.connect_timeout)
        if args.command == "baud":
            return run_baud(endpoint, args.rate, args.connect_timeout)
        if args.command == "ports":
            return run_ports(endpoint, args.connect_timeout)
        if args.command == "port":
            return run_port(endpoint, args.device, args.baud, args.force, args.connect_timeout)
        if args.command == "disconnect":
            return run_disconnect(endpoint, args.force, args.connect_timeout)
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
    except (OSError, UartCtlError, UARTAPIError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
