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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import serial
except ImportError:
    serial = None


def _resolve_repo_root() -> Path:
    script = Path(__file__).resolve()
    # Project layout: <repo>/tools/uart/uartd.py -> use <repo>.
    # Standalone layout: <dir>/uartd.py -> use <dir>.
    if len(script.parents) >= 3 and script.parent.name == "uart" and script.parent.parent.name == "tools":
        return script.parents[2]
    return script.parent


REPO_ROOT = _resolve_repo_root()
DEFAULT_LOG_DIR = REPO_ROOT / "logs"
DEFAULT_RUNTIME_LOG = DEFAULT_LOG_DIR / "runtime_log"
DEFAULT_SOCKET_PATH = DEFAULT_LOG_DIR / "uartd.sock"
DEFAULT_PID_PATH = DEFAULT_LOG_DIR / "uartd.pid"
DEFAULT_DAEMON_LOG = DEFAULT_LOG_DIR / "uartd.log"
DEFAULT_PORT = "COM7" if os.name == "nt" else "/dev/ttyUSB1"
DEFAULT_BAUD = 115200
DEFAULT_READ_TIMEOUT = 0.2
DEFAULT_WRITE_TIMEOUT = 5.0
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 17001
DEFAULT_TCP = f"{DEFAULT_TCP_HOST}:{DEFAULT_TCP_PORT}"
BUFFER_LIMIT = 1024 * 1024


class UartDaemonError(Exception):
    pass


@dataclass
class ClientState:
    sock: socket.socket
    recv_buffer: str = ""
    monitor: bool = False
    monitor_from: int = 0
    attached: bool = False
    attach_mode: str = "none"
    client_id: int = 0
    peer: str = "unknown"


@dataclass
class ExpectWaiter:
    client: socket.socket
    pattern: str
    deadline: float
    start_offset: int
    payload: dict[str, Any] | None = None
    include_output: bool = False


@dataclass
class SearchMatch:
    start_offset: int
    end_offset: int


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
    tcp_host: str | None
    tcp_port: int | None
    enable_unix_socket: bool


class UartDaemon:
    def __init__(self, config: DaemonConfig) -> None:
        if serial is None:
            raise UartDaemonError(
                "pyserial is not installed. Install it with 'python -m pip install pyserial'."
            )

        self.config = config
        self.selector = selectors.DefaultSelector()
        self.servers: list[socket.socket] = []
        self.server_names: dict[socket.socket, str] = {}
        self.serial_port: Any | None = None
        self.clients: dict[socket.socket, ClientState] = {}
        self.waiters: list[ExpectWaiter] = []
        self.buffer = ""
        self.offset = 0
        self.next_client_id = 1
        self.last_write_source: str | None = None
        self.last_write_at: float | None = None
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
        self._setup_servers()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self._log_daemon(
            "uartd started "
            f"port={self.config.port} baud={self.config.baud} "
            f"unix={self.config.socket_path if self.config.enable_unix_socket else 'disabled'} "
            f"tcp={self._tcp_description()}"
        )

        try:
            self.run_loop()
        finally:
            self.cleanup()

    def _tcp_description(self) -> str:
        if self.config.tcp_host is None or self.config.tcp_port is None:
            return "disabled"
        return f"{self.config.tcp_host}:{self.config.tcp_port}"

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
        if self.config.exclusive and os.name != "nt":
            kwargs["exclusive"] = True
        try:
            self.serial_port = serial.Serial(**kwargs)
        except Exception as exc:
            raise UartDaemonError(f"Failed to open serial port {self.config.port}: {exc}") from exc

    def _setup_servers(self) -> None:
        if self.config.enable_unix_socket:
            self._setup_unix_socket()
        if self.config.tcp_host is not None and self.config.tcp_port is not None:
            self._setup_tcp_socket()
        if not self.servers:
            raise UartDaemonError("no control socket enabled; enable Unix socket or TCP")

    def _setup_unix_socket(self) -> None:
        if not hasattr(socket, "AF_UNIX"):
            raise UartDaemonError("Unix sockets are not available on this platform. Use --tcp-host/--tcp-port.")
        if self.config.socket_path.exists():
            self.config.socket_path.unlink()
        self.config.socket_path.parent.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.config.socket_path))
        server.listen()
        server.setblocking(False)
        self.selector.register(server, selectors.EVENT_READ, self._accept_client)
        self.servers.append(server)
        self.server_names[server] = f"unix:{self.config.socket_path}"

    def _setup_tcp_socket(self) -> None:
        assert self.config.tcp_host is not None and self.config.tcp_port is not None
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.config.tcp_host, self.config.tcp_port))
        server.listen()
        server.setblocking(False)
        self.selector.register(server, selectors.EVENT_READ, self._accept_client)
        self.servers.append(server)
        self.server_names[server] = f"tcp:{self.config.tcp_host}:{self.config.tcp_port}"

    def run_loop(self) -> None:
        while self.running:
            self._read_serial()
            events = self.selector.select(timeout=0.1)
            for key, _ in events:
                callback = key.data
                callback(key.fileobj)
            self._check_waiters()

    def _accept_client(self, server_sock: socket.socket) -> None:
        client_sock, addr = server_sock.accept()
        client_sock.setblocking(False)
        client_id = self.next_client_id
        self.next_client_id += 1
        peer = self._format_peer(server_sock, addr)
        self.clients[client_sock] = ClientState(sock=client_sock, client_id=client_id, peer=peer)
        self.selector.register(client_sock, selectors.EVENT_READ, self._read_client)
        self._log_daemon(f"client connected id={client_id} peer={peer}")

    def _format_peer(self, server_sock: socket.socket, addr: Any) -> str:
        name = self.server_names.get(server_sock, "unknown")
        if isinstance(addr, tuple) and len(addr) >= 2:
            return f"{name}/{addr[0]}:{addr[1]}"
        return name

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

        if state.attached:
            self._handle_attached_input(state, data)
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

        try:
            self._handle_command_inner(client_sock, request)
        except UartDaemonError as exc:
            self._send_json(client_sock, {"ok": False, "error": str(exc)})

    def _handle_command_inner(self, client_sock: socket.socket, request: dict[str, Any]) -> None:
        action = request.get("action")

        if action == "status":
            last_write_iso = None
            if self.last_write_at is not None:
                last_write_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(self.last_write_at))
            state = self.clients.get(client_sock)
            self._send_json(
                client_sock,
                {
                    "ok": True,
                    "pid": os.getpid(),
                    "port": self.config.port,
                    "baud": self.config.baud,
                    "socket": str(self.config.socket_path) if self.config.enable_unix_socket else None,
                    "tcp": self._tcp_description(),
                    "runtime_log": str(self.config.runtime_log),
                    "clients": len(self.clients),
                    "client_peer": state.peer if state else None,
                    "attached_clients": self._count_attached_clients(),
                    "attach_clients": self._count_attached_clients(),
                    "rw_attach_clients": self._count_attach_mode("rw"),
                    "ro_attach_clients": self._count_attach_mode("ro"),
                    "monitor_clients": self._count_monitor_clients(),
                    "shared_write": True,
                    "last_write_source": self.last_write_source,
                    "last_writer": self.last_write_source,
                    "last_write_at": self.last_write_at,
                    "last_write_at_iso": last_write_iso,
                    "offset": self.offset,
                    "buffer_start_offset": self._buffer_start_offset(),
                    "buffer_length": len(self.buffer),
                },
            )
            return

        if action == "send":
            text = request.get("text", "")
            newline = self._resolve_newline(request.get("newline", False))
            if not isinstance(text, str):
                self._send_json(client_sock, {"ok": False, "error": "text must be string"})
                return
            payload = text + newline
            self._write_serial(payload, source="json-api:send")
            self._send_json(
                client_sock,
                {
                    "ok": True,
                    "sent": payload,
                    "shared_write": True,
                    "active_attach_clients": self._count_attached_clients(),
                },
            )
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

            start_offset = self._resolve_start_offset(request)
            matched = self._search_since(pattern, start_offset)
            if matched is not None:
                self._send_json(
                    client_sock,
                    {
                        "ok": True,
                        "matched": pattern,
                        "pattern": pattern,
                        "output": self._text_since_offset(start_offset),
                        "offset": self.offset,
                        "start_offset": start_offset,
                        "end_offset": self.offset,
                        "match_start_offset": matched.start_offset,
                        "match_end_offset": matched.end_offset,
                    },
                )
                return

            self.waiters.append(
                ExpectWaiter(
                    client=client_sock,
                    pattern=pattern,
                    deadline=time.monotonic() + float(timeout),
                    start_offset=start_offset,
                    include_output=True,
                )
            )
            return

        if action == "send_expect":
            text = request.get("text", "")
            pattern = request.get("expect")
            timeout = request.get("timeout", 30)
            if not isinstance(text, str):
                self._send_json(client_sock, {"ok": False, "error": "text must be string"})
                return
            if not isinstance(pattern, str) or pattern == "":
                self._send_json(client_sock, {"ok": False, "error": "expect must be non-empty string"})
                return
            if not isinstance(timeout, (int, float)) or timeout < 0:
                self._send_json(client_sock, {"ok": False, "error": "timeout must be non-negative number"})
                return

            start_offset = self._resolve_start_offset(request, default_mode="now")
            payload = text + self._resolve_newline(request.get("newline", True))
            self._write_serial(payload, source="json-api:send_expect")
            matched = self._search_since(pattern, start_offset)
            if matched is not None:
                self._send_json(
                    client_sock,
                    {
                        "ok": True,
                        "sent": payload,
                        "matched": pattern,
                        "expect": pattern,
                        "output": self._text_since_offset(start_offset),
                        "shared_write": True,
                        "active_attach_clients": self._count_attached_clients(),
                        "offset": self.offset,
                        "start_offset": start_offset,
                        "end_offset": self.offset,
                        "match_start_offset": matched.start_offset,
                        "match_end_offset": matched.end_offset,
                    },
                )
                return

            self.waiters.append(
                ExpectWaiter(
                    client=client_sock,
                    pattern=pattern,
                    deadline=time.monotonic() + float(timeout),
                    start_offset=start_offset,
                    payload={
                        "sent": payload,
                        "expect": pattern,
                        "shared_write": True,
                        "active_attach_clients": self._count_attached_clients(),
                    },
                    include_output=True,
                )
            )
            return

        if action == "tail":
            state = self.clients[client_sock]
            state.monitor = True
            lines = request.get("lines", 200)
            backlog = self._tail_lines(int(lines) if isinstance(lines, int) else 200)
            self._send_json(client_sock, {"ok": True, "stream": True, "backlog": backlog})
            return

        if action == "tail_once":
            lines = request.get("lines", 200)
            resolved_lines = int(lines) if isinstance(lines, int) else 200
            self._send_json(
                client_sock,
                {
                    "ok": True,
                    "lines": resolved_lines,
                    "offset": self.offset,
                    "text": self._tail_lines(resolved_lines),
                },
            )
            return

        if action == "attach":
            self._handle_attach(client_sock, request)
            return

        if action == "stop":
            self._send_json(client_sock, {"ok": True, "stopping": True})
            self.running = False
            return

        self._send_json(client_sock, {"ok": False, "error": f"unknown action: {action}"})

    def _handle_attach(self, client_sock: socket.socket, request: dict[str, Any]) -> None:
        state = self.clients[client_sock]
        mode = request.get("mode", "rw")
        if mode not in {"ro", "rw"}:
            self._send_json(client_sock, {"ok": False, "error": "mode must be ro or rw"})
            return

        default_backlog = 0 if mode == "rw" else 100
        backlog_lines = request.get("backlog_lines", default_backlog)
        if not isinstance(backlog_lines, int) or backlog_lines < 0:
            self._send_json(client_sock, {"ok": False, "error": "backlog_lines must be a non-negative integer"})
            return

        state.monitor = False
        state.attached = True
        state.attach_mode = mode
        state.recv_buffer = ""

        self._send_json(
            client_sock,
            {
                "ok": True,
                "attached": True,
                "mode": mode,
                "raw": True,
                "shared_write": True,
                "client_id": state.client_id,
                "active_attach_clients": self._count_attached_clients(),
            },
        )

        if backlog_lines > 0:
            backlog = self._tail_lines(backlog_lines)
            if backlog:
                try:
                    client_sock.sendall(backlog.encode(self.config.encoding, errors="replace"))
                except OSError:
                    self._drop_client(client_sock)

    def _handle_attached_input(self, state: ClientState, data: bytes) -> None:
        if state.attach_mode == "ro":
            return
        self._write_serial_bytes(data, source=f"attach:{state.client_id}")

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
            if state.attached:
                try:
                    state.sock.sendall(chunk)
                except OSError:
                    self._drop_client(state.sock)
            elif state.monitor:
                self._send_json(state.sock, {"type": "data", "data": decoded})

    def _write_serial_bytes(self, payload: bytes, source: str) -> None:
        assert self.serial_port is not None
        try:
            self.serial_port.write(payload)
            self.serial_port.flush()
            self.last_write_source = source
            self.last_write_at = time.time()
        except Exception as exc:
            raise UartDaemonError(f"Failed to write to serial port: {exc}") from exc

    def _write_serial(self, payload: str, source: str) -> None:
        self._write_serial_bytes(payload.encode(self.config.encoding), source=source)

    def _check_waiters(self) -> None:
        now = time.monotonic()
        remaining: list[ExpectWaiter] = []
        for waiter in self.waiters:
            if waiter.client not in self.clients:
                continue
            matched = self._search_since(waiter.pattern, waiter.start_offset)
            if matched is not None:
                response = {
                    "ok": True,
                    "matched": waiter.pattern,
                    "pattern": waiter.pattern,
                    "offset": self.offset,
                    "start_offset": waiter.start_offset,
                    "end_offset": self.offset,
                    "match_start_offset": matched.start_offset,
                    "match_end_offset": matched.end_offset,
                }
                if waiter.include_output:
                    response["output"] = self._text_since_offset(waiter.start_offset)
                if waiter.payload:
                    response.update(waiter.payload)
                self._send_json(waiter.client, response)
                continue
            if now >= waiter.deadline:
                response = {
                    "ok": False,
                    "error": f"timeout waiting for {waiter.pattern!r}",
                    "pattern": waiter.pattern,
                    "start_offset": waiter.start_offset,
                    "offset": self.offset,
                    "tail": self._tail_lines(100),
                }
                if waiter.include_output:
                    response["output_since_start"] = self._text_since_offset(waiter.start_offset)
                if waiter.payload:
                    response.update(waiter.payload)
                self._send_json(waiter.client, response)
                continue
            remaining.append(waiter)
        self.waiters = remaining

    def _search_since(self, pattern: str, start_offset: int) -> SearchMatch | None:
        oldest_offset = self._buffer_start_offset()
        effective_offset = max(start_offset, oldest_offset)
        if effective_offset >= self.offset:
            return None

        available_start = max(0, len(self.buffer) - (self.offset - effective_offset))
        relative_index = self.buffer[available_start:].find(pattern)
        if relative_index < 0:
            return None

        match_start = effective_offset + relative_index
        return SearchMatch(start_offset=match_start, end_offset=match_start + len(pattern))

    def _resolve_start_offset(self, request: dict[str, Any], default_mode: str = "buffer") -> int:
        raw_offset = request.get("from_offset")
        if raw_offset is not None:
            if not isinstance(raw_offset, int) or raw_offset < 0:
                raise UartDaemonError("from_offset must be a non-negative integer")
            return raw_offset

        from_mode = request.get("from", default_mode)
        if not isinstance(from_mode, str):
            raise UartDaemonError("from must be a string")

        normalized = from_mode.strip().lower()
        if normalized in {"buffer", "backlog"}:
            return self._buffer_start_offset()
        if normalized in {"now", "end", "fresh"}:
            return self.offset
        raise UartDaemonError(f"unsupported expect origin: {from_mode}")

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

    def _text_since_offset(self, start_offset: int) -> str:
        oldest_offset = self._buffer_start_offset()
        effective_offset = max(start_offset, oldest_offset)
        if effective_offset >= self.offset:
            return ""
        available_start = max(0, len(self.buffer) - (self.offset - effective_offset))
        return self.buffer[available_start:]

    def _count_attached_clients(self) -> int:
        return sum(1 for state in self.clients.values() if state.attached)

    def _count_attach_mode(self, mode: str) -> int:
        return sum(1 for state in self.clients.values() if state.attached and state.attach_mode == mode)

    def _count_monitor_clients(self) -> int:
        return sum(1 for state in self.clients.values() if state.monitor)

    def _resolve_newline(self, value: Any) -> str:
        if value is True:
            return "\n"
        if value in {False, None}:
            return ""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "lf":
                return "\n"
            if normalized == "crlf":
                return "\r\n"
            if normalized == "cr":
                return "\r"
            if normalized == "none":
                return ""
        raise UartDaemonError("unsupported newline")

    def _send_json(self, client_sock: socket.socket, payload: dict[str, Any]) -> None:
        try:
            client_sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            self._drop_client(client_sock)

    def _drop_client(self, client_sock: socket.socket) -> None:
        state = self.clients.get(client_sock)
        if state is None:
            return
        self.waiters = [item for item in self.waiters if item.client is not client_sock]
        try:
            self.selector.unregister(client_sock)
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass
        self._log_daemon(f"client disconnected id={state.client_id} peer={state.peer}")
        del self.clients[client_sock]

    def cleanup(self) -> None:
        for client in list(self.clients):
            self._drop_client(client)
        for server in list(self.servers):
            try:
                self.selector.unregister(server)
            except Exception:
                pass
            try:
                server.close()
            except Exception:
                pass
        if self.serial_port is not None:
            self.serial_port.close()
        self.runtime_log_handle.close()
        self.daemon_log_handle.close()
        if self.config.enable_unix_socket and self.config.socket_path.exists():
            try:
                self.config.socket_path.unlink()
            except OSError:
                pass
        if self.config.pid_path.exists():
            try:
                self.config.pid_path.unlink()
            except OSError:
                pass


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


def add_common_server_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--port", default=DEFAULT_PORT, help="Serial port, e.g. COM7 on Windows or /dev/ttyUSB1 on Linux")
    sub.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    sub.add_argument("--socket", default=None, help="Unix socket path, Linux/WSL only. Default is instance-specific.")
    sub.add_argument("--no-unix-socket", action="store_true", help="Disable Unix socket listener")
    sub.add_argument("--no-tcp", action="store_true", help="Disable TCP listener")
    sub.add_argument("--tcp", default=None, help=f"Enable TCP listener HOST:PORT, e.g. 0.0.0.0:{DEFAULT_TCP_PORT}")
    sub.add_argument("--tcp-host", default=None, help="Enable TCP listener on this host/interface")
    sub.add_argument("--tcp-port", type=int, default=None, help="Enable TCP listener on this port")
    sub.add_argument("--pid-file", default=None, help="PID file path. Default is instance-specific.")
    sub.add_argument("--runtime-log", default=None, help="UART runtime log path. Default is instance-specific.")
    sub.add_argument("--daemon-log", default=None, help="Daemon internal log path. Default is instance-specific.")
    sub.add_argument("--read-timeout", type=float, default=DEFAULT_READ_TIMEOUT)
    sub.add_argument("--write-timeout", type=float, default=DEFAULT_WRITE_TIMEOUT)
    sub.add_argument("--encoding", default="utf-8")
    sub.add_argument("--exclusive", action="store_true", help="Open serial port exclusively where supported")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent UART daemon")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "run"):
        sub = subparsers.add_parser(name)
        add_common_server_args(sub)

    stop_parser = subparsers.add_parser("stop")
    transport = stop_parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None)
    transport.add_argument("--tcp", default=None)

    status_parser = subparsers.add_parser("status")
    transport = status_parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None)
    transport.add_argument("--tcp", default=None)
    return parser


def resolve_tcp_args(args: argparse.Namespace) -> tuple[str | None, int | None]:
    if getattr(args, "no_tcp", False):
        return None, None
    if getattr(args, "tcp", None):
        return parse_tcp_endpoint(args.tcp)
    host = getattr(args, "tcp_host", None)
    port = getattr(args, "tcp_port", None)
    if host is not None or port is not None:
        return (host if host is not None else DEFAULT_TCP_HOST, port if port is not None else DEFAULT_TCP_PORT)
    return DEFAULT_TCP_HOST, DEFAULT_TCP_PORT


def _sanitize_name(value: str) -> str:
    text = value.replace("\\", "-").replace("/", "-").replace(":", "-").strip("- ")
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "uart"


def _instance_name(port: str, tcp_port: int | None) -> str:
    port_part = _sanitize_name(port)
    if tcp_port is None:
        return f"uartd-{port_part}"
    return f"uartd-{port_part}-{tcp_port}"


def _resolved_paths(args: argparse.Namespace, tcp_port: int | None) -> tuple[Path, Path, Path, Path]:
    name = _instance_name(args.port, tcp_port)
    socket_path = Path(args.socket) if args.socket else DEFAULT_LOG_DIR / f"{name}.sock"
    pid_path = Path(args.pid_file) if args.pid_file else DEFAULT_LOG_DIR / f"{name}.pid"
    runtime_log = Path(args.runtime_log) if args.runtime_log else DEFAULT_LOG_DIR / f"runtime_log-{name}"
    daemon_log = Path(args.daemon_log) if args.daemon_log else DEFAULT_LOG_DIR / f"{name}.log"
    return socket_path, pid_path, runtime_log, daemon_log


def _connect_host_for_bind(host: str) -> str:
    # 0.0.0.0/:: are bind addresses, not good readiness/status connect targets.
    if host in {"0.0.0.0", "", "*"}:
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host


def _control_endpoint_for_bind(host: str | None, port: int | None) -> str | None:
    if host is None or port is None:
        return None
    return f"{_connect_host_for_bind(host)}:{port}"


def daemon_config_from_args(args: argparse.Namespace) -> DaemonConfig:
    tcp_host, tcp_port = resolve_tcp_args(args)
    socket_path, pid_path, runtime_log, daemon_log = _resolved_paths(args, tcp_port)
    enable_unix_socket = not args.no_unix_socket and os.name != "nt"
    return DaemonConfig(
        port=args.port,
        baud=args.baud,
        socket_path=socket_path,
        pid_path=pid_path,
        runtime_log=runtime_log,
        daemon_log=daemon_log,
        read_timeout=args.read_timeout,
        write_timeout=args.write_timeout,
        encoding=args.encoding,
        exclusive=args.exclusive,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
        enable_unix_socket=enable_unix_socket,
    )


def connect_control(socket_path: Path | None = None, tcp: str | None = None, timeout: float = 3.0) -> socket.socket:
    if tcp:
        host, port = parse_tcp_endpoint(tcp)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.settimeout(None)
        return sock
    path = socket_path if socket_path is not None else DEFAULT_SOCKET_PATH
    if not hasattr(socket, "AF_UNIX"):
        raise UartDaemonError("Unix socket transport is not available. Use --tcp HOST:PORT.")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(str(path))
    sock.settimeout(None)
    return sock


def ping_control(socket_path: Path | None = None, tcp: str | None = None) -> dict[str, Any] | None:
    if tcp is None:
        path = socket_path if socket_path is not None else DEFAULT_SOCKET_PATH
        if not path.exists():
            return None
    try:
        with connect_control(socket_path=socket_path, tcp=tcp) as sock:
            sock.sendall(b'{"action":"status"}\n')
            data = sock.recv(4096)
    except (OSError, UartDaemonError):
        return None
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def start_daemon(args: argparse.Namespace) -> int:
    tcp_host, tcp_port = resolve_tcp_args(args)
    tcp_endpoint = _control_endpoint_for_bind(tcp_host, tcp_port)
    socket_path, pid_path, runtime_log, daemon_log = _resolved_paths(args, tcp_port)

    status = ping_control(socket_path=None if os.name == "nt" else socket_path, tcp=tcp_endpoint)
    if status is not None and status.get("ok"):
        print(f"uartd already running on {status.get('port')} (tcp={status.get('tcp')} socket={status.get('socket')})")
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
        str(socket_path),
        "--pid-file",
        str(pid_path),
        "--runtime-log",
        str(runtime_log),
        "--daemon-log",
        str(daemon_log),
        "--read-timeout",
        str(args.read_timeout),
        "--write-timeout",
        str(args.write_timeout),
        "--encoding",
        args.encoding,
    ]
    if args.no_unix_socket:
        cmd.append("--no-unix-socket")
    if args.no_tcp:
        cmd.append("--no-tcp")
    if args.tcp:
        cmd.extend(["--tcp", args.tcp])
    else:
        if args.tcp_host is not None:
            cmd.extend(["--tcp-host", args.tcp_host])
        if args.tcp_port is not None:
            cmd.extend(["--tcp-port", str(args.tcp_port)])
    if args.exclusive:
        cmd.append("--exclusive")

    daemon_log.parent.mkdir(parents=True, exist_ok=True)
    with daemon_log.open("a", encoding="utf-8") as handle:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(REPO_ROOT),
            "stdout": handle,
            "stderr": handle,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            popen_kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **popen_kwargs)

    deadline = time.time() + 5
    while time.time() < deadline:
        status = ping_control(socket_path=None if os.name == "nt" else socket_path, tcp=tcp_endpoint)
        if status is not None and status.get("ok"):
            print(
                f"uartd started pid={status.get('pid')} tcp={status.get('tcp')} socket={status.get('socket')} "
                f"pid_file={pid_path} runtime_log={runtime_log} daemon_log={daemon_log}"
            )
            return 0
        time.sleep(0.1)
    raise UartDaemonError("uartd did not become ready in time")


def send_request(socket_path: Path | None, tcp: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    with connect_control(socket_path=socket_path, tcp=tcp) as sock:
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        data = sock.recv(65536)
    if not data:
        raise UartDaemonError("no response from uartd")
    return json.loads(data.decode("utf-8"))


def stop_daemon(socket_path: Path | None = None, tcp: str | None = None) -> int:
    response = send_request(socket_path, tcp, {"action": "stop"})
    if not response.get("ok"):
        raise UartDaemonError(response.get("error", "failed to stop uartd"))
    print("uartd stopping")
    return 0


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
            socket_path = Path(args.socket) if args.socket else None
            tcp = args.tcp or (DEFAULT_TCP if os.name == "nt" and args.socket is None else None)
            return stop_daemon(socket_path=socket_path, tcp=tcp)
        if args.command == "status":
            socket_path = Path(args.socket) if args.socket else None
            tcp = args.tcp or (DEFAULT_TCP if os.name == "nt" and args.socket is None else None)
            status = ping_control(socket_path=socket_path, tcp=tcp)
            if status is None:
                print("uartd not running")
                return 1
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
    except (UartDaemonError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
