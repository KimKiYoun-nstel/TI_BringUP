#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import serial
except ImportError:
    serial = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_LOG = REPO_ROOT / "logs" / "runtime_log"
DEFAULT_SOCKET_PATH = REPO_ROOT / "logs" / "uartd.sock"
DEFAULT_PID_PATH = REPO_ROOT / "logs" / "uartd.pid"
DEFAULT_DAEMON_LOG = REPO_ROOT / "logs" / "uartd.log"
DEFAULT_PORT = "/dev/ttyUSB1"
DEFAULT_BAUD = 115200
DEFAULT_READ_TIMEOUT = 0.2
DEFAULT_WRITE_TIMEOUT = 5.0
BUFFER_LIMIT = 1024 * 1024


class UartDaemonError(Exception):
    pass


@dataclass
class ClientState:
    sock: socket.socket
    recv_buffer: str = ""
    monitor: bool = False
    monitor_from: int = 0


@dataclass
class ExpectWaiter:
    client: socket.socket
    pattern: str
    deadline: float
    start_offset: int


@dataclass
class DaemonConfig:
    port: str
    baud: int
    socket_path: Path
    pid_path: Path
    runtime_log: Path
    daemon_log: Path
    read_timeout: float
    write_timeout: float
    encoding: str
    exclusive: bool


class UartDaemon:
    def __init__(self, config: DaemonConfig) -> None:
        if serial is None:
            raise UartDaemonError(
                "pyserial is not installed. Install it with 'python3 -m pip install pyserial'."
            )

        self.config = config
        self.selector = selectors.DefaultSelector()
        self.server: socket.socket | None = None
        self.serial_port: Any | None = None
        self.clients: dict[socket.socket, ClientState] = {}
        self.waiters: list[ExpectWaiter] = []
        self.buffer = ""
        self.offset = 0
        self.running = True
        self.runtime_log_handle = self._open_append_file(config.runtime_log)
        self.daemon_log_handle = self._open_append_file(config.daemon_log)

    def _open_append_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.open("a", encoding="utf-8")

    def _log_daemon(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.daemon_log_handle.write(f"[{stamp}] {message}\n")
        self.daemon_log_handle.flush()

    def start(self) -> None:
        self._write_pid()
        self._setup_serial()
        self._setup_socket()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self._log_daemon(
            f"uartd started port={self.config.port} baud={self.config.baud} socket={self.config.socket_path}"
        )

        try:
            self.run_loop()
        finally:
            self.cleanup()

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        self._log_daemon(f"received signal {signum}, stopping")
        self.running = False

    def _write_pid(self) -> None:
        self.config.pid_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.pid_path.write_text(str(os.getpid()), encoding="utf-8")

    def _setup_serial(self) -> None:
        assert serial is not None
        kwargs: dict[str, Any] = {
            "port": self.config.port,
            "baudrate": self.config.baud,
            "timeout": self.config.read_timeout,
            "write_timeout": self.config.write_timeout,
        }
        if self.config.exclusive:
            kwargs["exclusive"] = True
        try:
            self.serial_port = serial.Serial(**kwargs)
        except Exception as exc:
            raise UartDaemonError(f"Failed to open serial port {self.config.port}: {exc}") from exc

    def _setup_socket(self) -> None:
        if self.config.socket_path.exists():
            self.config.socket_path.unlink()

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.config.socket_path))
        self.server.listen()
        self.server.setblocking(False)
        self.selector.register(self.server, selectors.EVENT_READ, self._accept_client)

    def run_loop(self) -> None:
        while self.running:
            self._read_serial()
            events = self.selector.select(timeout=0.1)
            for key, _ in events:
                callback = key.data
                callback(key.fileobj)
            self._check_waiters()

    def _accept_client(self, _server_sock: socket.socket) -> None:
        assert self.server is not None
        client_sock, _ = self.server.accept()
        client_sock.setblocking(False)
        self.clients[client_sock] = ClientState(sock=client_sock)
        self.selector.register(client_sock, selectors.EVENT_READ, self._read_client)

    def _read_client(self, client_sock: socket.socket) -> None:
        state = self.clients[client_sock]
        try:
            data = client_sock.recv(4096)
        except OSError:
            self._drop_client(client_sock)
            return

        if not data:
            self._drop_client(client_sock)
            return

        state.recv_buffer += data.decode("utf-8", errors="replace")
        while "\n" in state.recv_buffer:
            line, state.recv_buffer = state.recv_buffer.split("\n", 1)
            if not line.strip():
                continue
            self._handle_command(client_sock, line)

    def _handle_command(self, client_sock: socket.socket, line: str) -> None:
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            self._send_json(client_sock, {"ok": False, "error": f"invalid-json: {exc}"})
            return

        action = request.get("action")
        if action == "status":
            self._send_json(
                client_sock,
                {
                    "ok": True,
                    "pid": os.getpid(),
                    "port": self.config.port,
                    "baud": self.config.baud,
                    "socket": str(self.config.socket_path),
                    "runtime_log": str(self.config.runtime_log),
                    "clients": len(self.clients),
                },
            )
            return

        if action == "send":
            text = request.get("text", "")
            append_newline = bool(request.get("newline", False))
            if not isinstance(text, str):
                self._send_json(client_sock, {"ok": False, "error": "text must be string"})
                return
            payload = text + ("\n" if append_newline else "")
            self._write_serial(payload)
            self._send_json(client_sock, {"ok": True, "sent": payload})
            return

        if action == "expect":
            pattern = request.get("pattern")
            timeout = request.get("timeout", 30)
            if not isinstance(pattern, str) or pattern == "":
                self._send_json(client_sock, {"ok": False, "error": "pattern must be non-empty string"})
                return
            if not isinstance(timeout, (int, float)) or timeout < 0:
                self._send_json(client_sock, {"ok": False, "error": "timeout must be non-negative number"})
                return

            default_offset = self._buffer_start_offset()
            matched = self._search_since(pattern, int(request.get("from_offset", default_offset)))
            if matched:
                self._send_json(client_sock, {"ok": True, "matched": pattern, "offset": self.offset})
                return

            waiter = ExpectWaiter(
                client=client_sock,
                pattern=pattern,
                deadline=time.monotonic() + float(timeout),
                start_offset=int(request.get("from_offset", default_offset)),
            )
            self.waiters.append(waiter)
            return

        if action == "tail":
            state = self.clients[client_sock]
            state.monitor = True
            lines = request.get("lines", 200)
            backlog = self._tail_lines(int(lines) if isinstance(lines, int) else 200)
            self._send_json(client_sock, {"ok": True, "stream": True, "backlog": backlog})
            return

        if action == "stop":
            self._send_json(client_sock, {"ok": True, "stopping": True})
            self.running = False
            return

        self._send_json(client_sock, {"ok": False, "error": f"unknown action: {action}"})

    def _read_serial(self) -> None:
        assert self.serial_port is not None
        try:
            chunk = self.serial_port.read(4096)
        except Exception as exc:
            self._log_daemon(f"serial read failed: {exc}")
            self.running = False
            return

        if not chunk:
            return

        decoded = chunk.decode(self.config.encoding, errors="replace")
        self.runtime_log_handle.write(decoded)
        self.runtime_log_handle.flush()

        self.buffer += decoded
        if len(self.buffer) > BUFFER_LIMIT:
            self.buffer = self.buffer[-BUFFER_LIMIT:]
        self.offset += len(decoded)

        for state in list(self.clients.values()):
            if state.monitor:
                self._send_json(state.sock, {"type": "data", "data": decoded})

    def _write_serial(self, payload: str) -> None:
        assert self.serial_port is not None
        try:
            self.serial_port.write(payload.encode(self.config.encoding))
            self.serial_port.flush()
        except Exception as exc:
            raise UartDaemonError(f"Failed to write to serial port: {exc}") from exc

    def _check_waiters(self) -> None:
        now = time.monotonic()
        remaining: list[ExpectWaiter] = []
        for waiter in self.waiters:
            if self._search_since(waiter.pattern, waiter.start_offset):
                self._send_json(waiter.client, {"ok": True, "matched": waiter.pattern, "offset": self.offset})
                continue
            if now >= waiter.deadline:
                self._send_json(waiter.client, {"ok": False, "error": f"timeout waiting for {waiter.pattern!r}"})
                continue
            remaining.append(waiter)
        self.waiters = remaining

    def _search_since(self, pattern: str, start_offset: int) -> bool:
        oldest_offset = self._buffer_start_offset()
        effective_offset = max(start_offset, oldest_offset)
        if effective_offset >= self.offset:
            return False

        available_start = max(0, len(self.buffer) - (self.offset - effective_offset))
        return pattern in self.buffer[available_start:]

    def _buffer_start_offset(self) -> int:
        return max(0, self.offset - len(self.buffer))

    def _tail_lines(self, lines: int) -> str:
        if lines <= 0:
            lines = 200
        if not self.config.runtime_log.exists():
            return ""
        text = self.config.runtime_log.read_text(encoding="utf-8", errors="replace")
        selected = deque(text.splitlines(), maxlen=lines)
        return "\n".join(selected) + ("\n" if selected else "")

    def _send_json(self, client_sock: socket.socket, payload: dict[str, Any]) -> None:
        try:
            client_sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            self._drop_client(client_sock)

    def _drop_client(self, client_sock: socket.socket) -> None:
        if client_sock in self.clients:
            self.waiters = [item for item in self.waiters if item.client is not client_sock]
            try:
                self.selector.unregister(client_sock)
            except Exception:
                pass
            try:
                client_sock.close()
            except Exception:
                pass
            del self.clients[client_sock]

    def cleanup(self) -> None:
        for client in list(self.clients):
            self._drop_client(client)
        if self.server is not None:
            try:
                self.selector.unregister(self.server)
            except Exception:
                pass
            self.server.close()
        if self.serial_port is not None:
            self.serial_port.close()
        self.runtime_log_handle.close()
        self.daemon_log_handle.close()
        if self.config.socket_path.exists():
            self.config.socket_path.unlink()
        if self.config.pid_path.exists():
            self.config.pid_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent UART daemon")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "run"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--port", default=DEFAULT_PORT)
        sub.add_argument("--baud", type=int, default=DEFAULT_BAUD)
        sub.add_argument("--socket", default=str(DEFAULT_SOCKET_PATH))
        sub.add_argument("--pid-file", default=str(DEFAULT_PID_PATH))
        sub.add_argument("--runtime-log", default=str(DEFAULT_RUNTIME_LOG))
        sub.add_argument("--daemon-log", default=str(DEFAULT_DAEMON_LOG))
        sub.add_argument("--read-timeout", type=float, default=DEFAULT_READ_TIMEOUT)
        sub.add_argument("--write-timeout", type=float, default=DEFAULT_WRITE_TIMEOUT)
        sub.add_argument("--encoding", default="utf-8")
        sub.add_argument("--exclusive", action="store_true")

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("--socket", default=str(DEFAULT_SOCKET_PATH))
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--socket", default=str(DEFAULT_SOCKET_PATH))
    return parser


def daemon_config_from_args(args: argparse.Namespace) -> DaemonConfig:
    return DaemonConfig(
        port=args.port,
        baud=args.baud,
        socket_path=Path(args.socket),
        pid_path=Path(args.pid_file),
        runtime_log=Path(args.runtime_log),
        daemon_log=Path(args.daemon_log),
        read_timeout=args.read_timeout,
        write_timeout=args.write_timeout,
        encoding=args.encoding,
        exclusive=args.exclusive,
    )


def ping_socket(socket_path: Path) -> dict[str, Any] | None:
    if not socket_path.exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            sock.sendall(b'{"action":"status"}\n')
            data = sock.recv(4096)
    except OSError:
        return None
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def start_daemon(args: argparse.Namespace) -> int:
    socket_path = Path(args.socket)
    status = ping_socket(socket_path)
    if status is not None and status.get("ok"):
        print(f"uartd already running on {status.get('port')} ({status.get('socket')})")
        return 0

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--port",
        args.port,
        "--baud",
        str(args.baud),
        "--socket",
        args.socket,
        "--pid-file",
        args.pid_file,
        "--runtime-log",
        args.runtime_log,
        "--daemon-log",
        args.daemon_log,
        "--read-timeout",
        str(args.read_timeout),
        "--write-timeout",
        str(args.write_timeout),
        "--encoding",
        args.encoding,
    ]
    if args.exclusive:
        cmd.append("--exclusive")

    Path(args.daemon_log).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.daemon_log).open("a", encoding="utf-8") as handle:
        subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=handle,
            stderr=handle,
            start_new_session=True,
        )

    deadline = time.time() + 5
    while time.time() < deadline:
        status = ping_socket(socket_path)
        if status is not None and status.get("ok"):
            print(f"uartd started pid={status.get('pid')} socket={status.get('socket')}")
            return 0
        time.sleep(0.1)

    raise UartDaemonError("uartd did not become ready in time")


def stop_daemon(socket_path: Path) -> int:
    response = send_request(socket_path, {"action": "stop"})
    if not response.get("ok"):
        raise UartDaemonError(response.get("error", "failed to stop uartd"))
    print("uartd stopping")
    return 0


def send_request(socket_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        data = sock.recv(65536)
    if not data:
        raise UartDaemonError("no response from uartd")
    return json.loads(data.decode("utf-8"))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "start":
            return start_daemon(args)
        if args.command == "run":
            daemon = UartDaemon(daemon_config_from_args(args))
            daemon.start()
            return 0
        if args.command == "stop":
            return stop_daemon(Path(args.socket))
        if args.command == "status":
            status = ping_socket(Path(args.socket))
            if status is None:
                print("uartd not running")
                return 1
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
    except UartDaemonError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
