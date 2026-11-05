#!/usr/bin/env python3

from __future__ import annotations

import argparse
import codecs
import json
import math
import queue
import hmac
import ipaddress
import threading
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

from uart_runtime import RotatingTextLog, SerialIO

try:
    import serial
except ImportError:
    serial = None


def _resolve_repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
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
MAX_REQUEST_BYTES = 128 * 1024
MAX_OUTGOING_BYTES = 512 * 1024
MAX_TEXT_BYTES = 48 * 1024
MAX_RESPONSE_BYTES = 384 * 1024
MAX_CLIENTS = 64
MAX_WAITERS = 32
MAX_EXPECT_TIMEOUT = 3600


class UartDaemonError(Exception):
    pass


@dataclass
class ClientState:
    sock: socket.socket
    recv_buffer: bytes = b""
    outgoing: deque[bytes] = field(default_factory=deque)
    pending_bytes: int = 0
    monitor: bool = False
    monitor_from: int = 0
    attached: bool = False
    attach_mode: str = "none"
    client_id: int = 0
    peer: str = "unknown"
    last_activity: float = field(default_factory=time.monotonic)
    has_requested: bool = False


@dataclass
class ExpectWaiter:
    client: socket.socket
    pattern: str
    deadline: float
    start_offset: int
    payload: dict[str, Any] | None = None
    include_output: bool = False
    owns_lease: bool = False
    scan_offset: int | None = None
    checked_offset: int = -1


@dataclass
class SearchMatch:
    start_offset: int
    end_offset: int


@dataclass
class DaemonConfig:
    port: str | None
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
    auth_token: str | None = None
    instance_id: str | None = None


class UartDaemon:
    def __init__(self, config: DaemonConfig) -> None:
        if serial is None:
            raise UartDaemonError(
                "pyserial is not installed. Install it with 'python -m pip install pyserial'."
            )

        # 외부 인터페이스에 TCP를 열 때는 암호 없는 접근을 차단한다.
        if config.tcp_host is not None and not _is_loopback(config.tcp_host) and not config.auth_token:
            raise UartDaemonError("External TCP bind requires --token-file or UARTD_TOKEN")
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
        self.stop_requested_at: float | None = None
        self.serial_state = "disconnected"
        self.last_serial_error: str | None = None
        self.session_generation = 0
        self.decoder = codecs.getincrementaldecoder(config.encoding)(errors="replace")
        self.serial_io: SerialIO | None = None
        self.pending_writes: dict[int, tuple[socket.socket | None, Any, int, str]] = {}
        self.next_write_id = 0
        self.command_owner: socket.socket | None = None
        self.wakeup_read, self.wakeup_write = socket.socketpair()
        self.wakeup_read.setblocking(False)
        self.wakeup_write.setblocking(False)
        self.selector.register(self.wakeup_read, selectors.EVENT_READ, "uart")
        self.last_log_flush = time.monotonic()
        self.runtime_log_handle = self._open_append_file(config.runtime_log)
        self.daemon_log_handle = self._open_append_file(config.daemon_log)

    def _open_append_file(self, path: Path):
        return RotatingTextLog(path)

    def _wake(self) -> None:
        try:
            self.wakeup_write.send(b"x")
        except (BlockingIOError, OSError):
            pass

    def _start_serial_io(self) -> None:
        self.serial_io = SerialIO(self.serial_port, self._wake)
        self.serial_io.start()

    def _stop_serial_io(self, *, close: bool = True, timeout: float = 0.5) -> None:
        if self.serial_io:
            self.serial_io.stop(close=close, timeout=timeout)
            failure = None
            if not close:
                # Baud changes reuse the handle and must preserve already-read RX.
                while not self.serial_io.events.empty():
                    kind, value = self.serial_io.events.get_nowait()
                    if kind == "rx":
                        self._receive_serial(value)
                    elif kind == "error":
                        failure = value
            self.serial_io = None
            if failure is not None:
                self._serial_failed(failure)
                raise UartDaemonError(f"Serial I/O failed before baud change: {failure}")

    def _drain_serial_events(self) -> None:
        try:
            while self.wakeup_read.recv(4096):
                pass
        except BlockingIOError:
            pass
        worker = self.serial_io
        if not worker:
            return
        for _ in range(256):
            try:
                kind, value = worker.events.get_nowait()
            except queue.Empty:
                break
            if kind == "rx":
                self._receive_serial(value)
            elif kind == "written":
                pending = self.pending_writes.pop(value, None)
                if pending:
                    sock, callback, _size, source = pending
                    self.last_write_source, self.last_write_at = source, time.time()
                    if sock is None or sock in self.clients:
                        callback()
                    elif self.command_owner is sock:
                        self.command_owner = None
            elif kind == "error":
                self._serial_failed(value)
                break

    def _log_daemon(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.daemon_log_handle.write(f"[{stamp}] {message}\n")
        self.daemon_log_handle.flush()

    def start(self) -> None:
        try:
            self._setup_servers()
            if self.config.port is not None:
                self._setup_serial()
            self._write_pid()
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGTERM, self._handle_signal)
                signal.signal(signal.SIGINT, self._handle_signal)
            self._log_daemon(
                "uartd started "
                f"port={self.config.port or 'disconnected'} baud={self.config.baud} "
                f"unix={self.config.socket_path if self.config.enable_unix_socket else 'disabled'} "
                f"tcp={self._tcp_description()}"
            )
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

    def _open_serial(self, port: str, baud: int) -> Any:
        assert serial is not None
        kwargs: dict[str, Any] = {
            "port": port,
            "baudrate": baud,
            "timeout": self.config.read_timeout,
            "write_timeout": self.config.write_timeout,
        }
        if self.config.exclusive and os.name != "nt":
            kwargs["exclusive"] = True
        try:
            # pySerial loop:// 는 장비 없이 기능 테스트할 때만 사용한다.
            if "://" in port:
                kwargs.pop("port")
                return serial.serial_for_url(port, **kwargs)
            return serial.Serial(**kwargs)
        except Exception as exc:
            raise UartDaemonError(f"Failed to open serial port {port}: {exc}") from exc

    def _setup_serial(self) -> None:
        assert self.config.port is not None
        self.serial_port = self._open_serial(self.config.port, self.config.baud)
        self.serial_state = "connected"
        self.last_serial_error = None
        self.session_generation += 1
        self._start_serial_io()

    def _check_port_transition(self, force: bool) -> None:
        if self.pending_writes:
            raise UartDaemonError("Serial writes are pending; retry after completion")
        if self.waiters:
            raise UartDaemonError("An expect/command is pending; retry after it finishes")
        if self._count_attach_mode("rw") and not force:
            raise UartDaemonError("RW attach clients are connected; retry with force=true after confirming")

    def _reset_serial_search(self) -> None:
        # 전체 offset은 증가만 시킨다. 이전 COM 출력으로 새 expect가 매칭되지 않도록 한다.
        self.buffer = ""
        self.decoder.reset()

    def _log_serial_transition(self, label: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.runtime_log_handle.write(f"\n[UART SESSION {timestamp}] {label}\n")
        self.runtime_log_handle.flush()

    def _replace_port(self, port: str, baud: int, force: bool) -> dict[str, Any]:
        if self.config.port == port and self.serial_port is not None:
            previous_baud = self.config.baud
            if baud != previous_baud:
                self._change_baud(baud)
            return {"ok": True, "changed": baud != previous_baud, "port": port,
                    "previous_port": port, "baud": self.config.baud,
                    "session_generation": self.session_generation}
        self._check_port_transition(force)
        # 신규 포트를 먼저 열어 실패 시 이전 COM을 그대로 보존한다.
        candidate = self._open_serial(port, baud)
        previous_port = self.config.port if self.serial_port is not None else None
        previous_serial = self.serial_port
        try:
            self._stop_serial_io()
        except RuntimeError as exc:
            candidate.close()
            raise UartDaemonError(str(exc)) from exc
        self.serial_port = candidate
        self.config.port = port
        self.config.baud = baud
        self.serial_state = "connected"
        self.last_serial_error = None
        self.session_generation += 1
        self._start_serial_io()
        self._reset_serial_search()
        self._log_serial_transition(f"{previous_port or 'none'} -> {port}, baud={baud}")
        if previous_serial is not None:
            try:
                previous_serial.close()
            except Exception as exc:
                self._log_daemon(f"previous serial close warning: {exc}")
        self._log_daemon(f"port changed: {previous_port} -> {port}, baud={baud}")
        return {"ok": True, "changed": True, "previous_port": previous_port,
                "port": port, "baud": baud, "session_generation": self.session_generation,
                "attached_clients": self._count_attached_clients()}

    def _disconnect_port(self, force: bool) -> dict[str, Any]:
        self._check_port_transition(force)
        self._stop_serial_io()
        previous_port = self.config.port
        previous_serial = self.serial_port
        self.serial_port = None
        self.config.port = None
        self.serial_state = "disconnected"
        self.last_serial_error = None
        self.session_generation += 1
        self._reset_serial_search()
        self._log_serial_transition(f"{previous_port or 'none'} -> disconnected")
        if previous_serial is not None:
            try:
                previous_serial.close()
            except Exception as exc:
                self._log_daemon(f"serial close warning: {exc}")
        self._log_daemon(f"port disconnected: {previous_port}")
        return {"ok": True, "previous_port": previous_port, "port": None,
                "serial_state": self.serial_state, "session_generation": self.session_generation}

    def _change_baud(self, baud: int) -> int:
        if self.waiters or self.pending_writes:
            raise UartDaemonError("An expect/command is pending; wait before changing baud")
        previous = self.config.baud
        if self.serial_port is not None:
            self._stop_serial_io(close=False)
            try:
                self.serial_port.baudrate = baud
            except Exception as exc:
                try:
                    self.serial_port.baudrate = previous
                except Exception as rollback:
                    raise UartDaemonError(f"Baud change failed: {exc}; restore failed: {rollback}") from exc
                raise UartDaemonError(f"Baud change failed; restored {previous}: {exc}") from exc
            finally:
                self._start_serial_io()
        self.config.baud = baud
        self._log_daemon(f"baud changed: {previous} -> {baud}")
        return previous

    def _serial_failed(self, exc: Exception) -> None:
        self._stop_serial_io()
        self._log_daemon(f"serial I/O failed, daemon remains active: {exc}")
        bad_port = self.serial_port
        self.serial_port = None
        self.serial_state = "error"
        self.last_serial_error = str(exc)
        self.session_generation += 1
        self._reset_serial_search()
        self._log_serial_transition(f"error on {self.config.port}: {exc}")
        if bad_port is not None:
            try:
                bad_port.close()
            except Exception:
                pass
        for waiter in self.waiters:
            if waiter.client in self.clients:
                self._send_json(waiter.client, {"ok": False, "error": f"serial disconnected: {exc}"})
        self.waiters.clear()
        for sock, _callback, _size, _source in self.pending_writes.values():
            if sock in self.clients:
                self._send_json(sock, {"ok": False, "error": f"serial write failed: {exc}; completion unknown"})
        self.pending_writes.clear()
        self.command_owner = None

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
            for key, mask in self.selector.select(timeout=0.1):
                if key.fileobj is self.wakeup_read:
                    self._drain_serial_events()
                elif key.fileobj in self.server_names:
                    self._accept_client(key.fileobj)
                else:
                    self._service_client(key.fileobj, mask)
            self._check_waiters()
            now = time.monotonic()
            if now - self.last_log_flush >= 0.25:
                self.runtime_log_handle.flush()
                self.last_log_flush = now
            for sock, state in list(self.clients.items()):
                if (not state.has_requested and not state.attached and not state.monitor
                        and not any(w.client is sock for w in self.waiters)
                        and not any(p[0] is sock for p in self.pending_writes.values())
                        and now - state.last_activity > 60):
                    self._drop_client(sock)
            if self.stop_requested_at is not None:
                if (not any(state.pending_bytes for state in self.clients.values())
                        or time.monotonic() - self.stop_requested_at > 0.5):
                    self.running = False

    def _service_client(self, sock: socket.socket, mask: int) -> None:
        if sock not in self.clients:
            return
        if mask & selectors.EVENT_READ:
            self._read_client(sock)
        if sock in self.clients and mask & selectors.EVENT_WRITE:
            self._write_client(sock)

    def _queue_data(self, sock: socket.socket, data: bytes) -> None:
        state = self.clients.get(sock)
        if state is None:
            return
        if state.pending_bytes + len(data) > MAX_OUTGOING_BYTES:
            self._log_daemon(f"dropping slow client id={state.client_id}: output queue full")
            self._drop_client(sock)
            return
        state.outgoing.append(data)
        state.pending_bytes += len(data)
        try:
            self.selector.modify(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, None)
        except (KeyError, OSError):
            self._drop_client(sock)

    def _write_client(self, sock: socket.socket) -> None:
        state = self.clients.get(sock)
        if state is None:
            return
        while state.outgoing:
            data = state.outgoing[0]
            try:
                sent = sock.send(data)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                self._drop_client(sock)
                return
            if sent <= 0:
                self._drop_client(sock)
                return
            state.pending_bytes -= sent
            if sent < len(data):
                state.outgoing[0] = data[sent:]
                return
            state.outgoing.popleft()
        try:
            self.selector.modify(sock, selectors.EVENT_READ, None)
        except (KeyError, OSError):
            self._drop_client(sock)

    def _accept_client(self, server_sock: socket.socket) -> None:
        client_sock, addr = server_sock.accept()
        if len(self.clients) >= MAX_CLIENTS:
            client_sock.close()
            return
        client_sock.setblocking(False)
        client_id = self.next_client_id
        self.next_client_id += 1
        peer = self._format_peer(server_sock, addr)
        self.clients[client_sock] = ClientState(sock=client_sock, client_id=client_id, peer=peer)
        self.selector.register(client_sock, selectors.EVENT_READ, None)
        self._log_daemon(f"client connected id={client_id} peer={peer}")

    def _format_peer(self, server_sock: socket.socket, addr: Any) -> str:
        name = self.server_names.get(server_sock, "unknown")
        if isinstance(addr, tuple) and len(addr) >= 2:
            return f"{name}/{addr[0]}:{addr[1]}"
        return name

    def _read_client(self, client_sock: socket.socket) -> None:
        state = self.clients.get(client_sock)
        if state is None:
            return
        try:
            data = client_sock.recv(4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            self._drop_client(client_sock)
            return
        if not data:
            self._drop_client(client_sock)
            return
        state.last_activity = time.monotonic()
        if state.attached:
            self._handle_attached_input(state, data)
            return
        state.recv_buffer += data
        if len(state.recv_buffer) > MAX_REQUEST_BYTES:
            self._drop_client(client_sock)
            return
        while b"\n" in state.recv_buffer and client_sock in self.clients:
            line, state.recv_buffer = state.recv_buffer.split(b"\n", 1)
            if not line.strip():
                continue
            self._handle_command(client_sock, line.decode("utf-8", errors="replace"))
            if state.attached and state.recv_buffer:
                raw = state.recv_buffer
                state.recv_buffer = b""
                self._handle_attached_input(state, raw)
                return

    def _handle_command(self, client_sock: socket.socket, line: str) -> None:
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            self._send_json(client_sock, {"ok": False, "error": f"invalid-json: {exc}"})
            return

        if not isinstance(request, dict):
            self._send_json(client_sock, {"ok": False, "error": "request must be a JSON object"})
            return
        if self.config.auth_token is not None:
            supplied = request.get("token", "")
            if not isinstance(supplied, str) or not hmac.compare_digest(
                    supplied.encode("utf-8", errors="surrogatepass"),
                    self.config.auth_token.encode("utf-8", errors="surrogatepass")):
                self._send_json(client_sock, {"ok": False, "error": "unauthorized"})
                return
        try:
            self.clients[client_sock].has_requested = True
            self._handle_command_inner(client_sock, request)
        except (UartDaemonError, RuntimeError, UnicodeError) as exc:
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
                    "port": self.config.port if self.serial_port is not None else None,
                    "requested_port": self.config.port,
                    "baud": self.config.baud,
                    "serial_state": self.serial_state,
                    "last_serial_error": self.last_serial_error,
                    "session_generation": self.session_generation,
                    "instance_id": self.config.instance_id,
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
                    "command_busy": self.command_owner is not None,
                    "pending_writes": len(self.pending_writes),
                    "limits": {"response_bytes": MAX_RESPONSE_BYTES,
                               "text_bytes": MAX_TEXT_BYTES, "clients": MAX_CLIENTS,
                               "waiters": MAX_WAITERS, "expect_timeout": MAX_EXPECT_TIMEOUT},
                },
            )
            return

        if action == "list_ports":
            try:
                from serial.tools import list_ports
                ports = []
                for info in list_ports.comports():
                    ports.append({"device": info.device, "description": info.description,
                                  "hwid": info.hwid, "vid": info.vid, "pid": info.pid,
                                  "serial_number": info.serial_number})
            except Exception as exc:
                raise UartDaemonError(f"Failed to list serial ports: {exc}") from exc
            self._send_json(client_sock, {"ok": True, "ports": ports})
            return

        if action == "set_port":
            port = request.get("port")
            baud = request.get("baud", self.config.baud)
            force = request.get("force", False)
            if not isinstance(port, str) or not port.strip():
                raise UartDaemonError("port must be a non-empty string")
            if type(baud) is not int or baud <= 0:
                raise UartDaemonError("baud must be a positive integer")
            if type(force) is not bool:
                raise UartDaemonError("force must be boolean")
            self._send_json(client_sock, self._replace_port(port.strip(), baud, force))
            return

        if action == "disconnect_port":
            force = request.get("force", False)
            if type(force) is not bool:
                raise UartDaemonError("force must be boolean")
            self._send_json(client_sock, self._disconnect_port(force))
            return

        if action == "baud":
            baud = request.get("baud")
            if type(baud) is not int or baud <= 0:
                raise UartDaemonError("baud must be a positive integer")
            previous = self._change_baud(baud)
            self._send_json(client_sock, {"ok": True, "previous_baud": previous, "baud": baud,
                                          "pid": os.getpid(), "attached_clients": self._count_attached_clients()})
            return

        if action == "send":
            text = request.get("text", "")
            newline = self._resolve_newline(request.get("newline", False))
            if not isinstance(text, str):
                self._send_json(client_sock, {"ok": False, "error": "text must be string"})
                return
            payload = text + newline
            self._write_serial_bytes(payload.encode(self.config.encoding), source="json-api:send",
                client=client_sock, callback=lambda: self._send_json(
                client_sock,
                {
                    "ok": True,
                    "sent": payload,
                    "shared_write": True,
                    "active_attach_clients": self._count_attached_clients(),
                },
            ))
            return

        if action == "expect":
            if self.serial_port is None:
                raise UartDaemonError("Serial port not connected")
            pattern = request.get("pattern")
            timeout = request.get("timeout", 30)
            if not isinstance(pattern, str) or pattern == "":
                self._send_json(client_sock, {"ok": False, "error": "pattern must be non-empty string"})
                return
            self._validate_expect(timeout)

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
            self._validate_expect(timeout)
            exclusive = request.get("exclusive", True)
            if type(exclusive) is not bool:
                raise UartDaemonError("exclusive must be boolean")
            if exclusive and (self.command_owner is not None or self.pending_writes
                              or any(waiter.payload for waiter in self.waiters)
                              or self._count_attach_mode("rw")):
                raise UartDaemonError("UART busy: command/write or RW attach active")

            start_offset = self._resolve_start_offset(request, default_mode="now")
            payload = text + self._resolve_newline(request.get("newline", True))
            def written() -> None:
                self.waiters.append(ExpectWaiter(
                    client=client_sock,
                    pattern=pattern,
                    deadline=time.monotonic() + float(timeout),
                    start_offset=start_offset,
                    payload={
                        "sent": payload,
                        "expect": pattern,
                        "shared_write": not exclusive,
                        "exclusive": exclusive,
                        "active_attach_clients": self._count_attached_clients(),
                    },
                    include_output=True,
                    owns_lease=exclusive,
                ))
            self._write_serial_bytes(payload.encode(self.config.encoding), source="json-api:send_expect",
                                     client=client_sock, callback=written)
            if exclusive:
                self.command_owner = client_sock
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
            self.stop_requested_at = time.monotonic()
            return

        self._send_json(client_sock, {"ok": False, "error": f"unknown action: {action}"})

    def _handle_attach(self, client_sock: socket.socket, request: dict[str, Any]) -> None:
        state = self.clients[client_sock]
        mode = request.get("mode", "rw")
        if mode not in ("ro", "rw"):
            self._send_json(client_sock, {"ok": False, "error": "mode must be ro or rw"})
            return
        if mode == "rw" and self.command_owner is not None:
            raise UartDaemonError("UART busy: exclusive command pending; RO attach is available")

        default_backlog = 0 if mode == "rw" else 100
        backlog_lines = request.get("backlog_lines", default_backlog)
        if not isinstance(backlog_lines, int) or backlog_lines < 0:
            self._send_json(client_sock, {"ok": False, "error": "backlog_lines must be a non-negative integer"})
            return

        state.monitor = False
        state.attached = True
        state.attach_mode = mode
        state.recv_buffer = b""

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
                self._queue_data(client_sock, backlog.encode(self.config.encoding, errors="replace"))

    def _handle_attached_input(self, state: ClientState, data: bytes) -> None:
        if state.attach_mode == "ro":
            return
        try:
            self._write_serial_bytes(data, source=f"attach:{state.client_id}")
        except UartDaemonError as exc:
            self._log_daemon(f"attach write ignored id={state.client_id}: {exc}")

    def _receive_serial(self, chunk: bytes) -> None:
        decoded = self.decoder.decode(chunk)
        self.runtime_log_handle.write(decoded)
        self.buffer += decoded
        if len(self.buffer) > BUFFER_LIMIT:
            self.buffer = self.buffer[-BUFFER_LIMIT:]
        self.offset += len(decoded)
        for state in list(self.clients.values()):
            if state.attached:
                self._queue_data(state.sock, chunk)
            elif state.monitor and decoded:
                self._send_json(state.sock, {"type": "data", "data": decoded})

    def _write_serial_bytes(self, payload: bytes, source: str,
                            client: socket.socket | None = None, callback: Any = lambda: None) -> None:
        if self.serial_port is None or self.serial_io is None:
            raise UartDaemonError("Serial port not connected")
        if self.command_owner is not None:
            raise UartDaemonError("UART busy: exclusive command pending")
        if sum(p[2] for p in self.pending_writes.values()) + len(payload) > MAX_OUTGOING_BYTES:
            raise UartDaemonError("UART transmit queue full; retry after completion")
        self.next_write_id += 1
        ident = self.next_write_id
        self.pending_writes[ident] = (client, callback, len(payload), source)
        try:
            self.serial_io.tx.put_nowait((ident, payload))
        except queue.Full as exc:
            self.pending_writes.pop(ident)
            raise UartDaemonError("UART transmit queue full") from exc

    def _validate_expect(self, timeout: Any) -> None:
        if (type(timeout) not in (int, float) or not 0 <= timeout <= MAX_EXPECT_TIMEOUT
                or not math.isfinite(timeout)):
            raise UartDaemonError(f"timeout must be finite and between 0 and {MAX_EXPECT_TIMEOUT}")
        if len(self.waiters) + len(self.pending_writes) >= MAX_WAITERS:
            raise UartDaemonError("Too many pending expect/write requests")

    def _write_serial(self, payload: str, source: str) -> None:
        self._write_serial_bytes(payload.encode(self.config.encoding), source=source)

    def _check_waiters(self) -> None:
        now = time.monotonic()
        remaining: list[ExpectWaiter] = []
        for waiter in self.waiters:
            if waiter.client not in self.clients:
                continue
            matched = None
            if waiter.checked_offset != self.offset:
                matched = self._search_since(waiter.pattern, waiter.scan_offset
                                             if waiter.scan_offset is not None else waiter.start_offset)
                waiter.checked_offset = self.offset
                waiter.scan_offset = max(waiter.start_offset, self.offset - len(waiter.pattern) + 1)
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
                if waiter.owns_lease and self.command_owner is waiter.client:
                    self.command_owner = None
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
                if waiter.owns_lease and self.command_owner is waiter.client:
                    self.command_owner = None
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
        self.runtime_log_handle.flush()
        with self.config.runtime_log.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - MAX_TEXT_BYTES))
            text = handle.read(MAX_TEXT_BYTES).decode("utf-8", errors="replace")
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
        if value is False or value is None:
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
        payload = payload.copy()
        text_fields = ("output", "output_since_start", "tail", "backlog", "text", "sent")
        truncated = {}
        for key in text_fields:
            value = payload.get(key)
            if isinstance(value, str) and len(value.encode("utf-8")) > MAX_TEXT_BYTES:
                original = len(value.encode("utf-8"))
                payload[key] = value.encode("utf-8")[-MAX_TEXT_BYTES:].decode("utf-8", errors="ignore")
                truncated[key] = {"original_bytes": original, "retained": "suffix"}
        if truncated:
            payload["truncated"] = True
            payload["truncated_fields"] = truncated
        if any(key in payload for key in ("tail", "backlog", "text")):
            payload["tail_window_bytes"] = MAX_TEXT_BYTES
            payload["tail_window_limited"] = self.runtime_log_handle.size > MAX_TEXT_BYTES
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_RESPONSE_BYTES:
            # Control characters can expand sixfold when escaped as JSON.
            for key in text_fields:
                if isinstance(payload.get(key), str):
                    payload[key] = payload[key][-8192:]
            payload["truncated"] = True
            encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = b'{"ok":false,"error":"Response too large; request a smaller result"}\n'
        self._queue_data(client_sock, encoded)

    def _drop_client(self, client_sock: socket.socket) -> None:
        state = self.clients.get(client_sock)
        if state is None:
            return
        self.waiters = [item for item in self.waiters if item.client is not client_sock]
        if self.command_owner is client_sock and not any(p[0] is client_sock for p in self.pending_writes.values()):
            self.command_owner = None
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
        self._stop_serial_io(timeout=max(0.5, self.config.write_timeout + 0.5))
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
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.selector.close()
        self.wakeup_read.close()
        self.wakeup_write.close()
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


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _read_auth_token(token_file: str | None) -> str | None:
    if token_file:
        try:
            value = Path(token_file).read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise UartDaemonError(f"Cannot read token file {token_file}: {exc}") from exc
    else:
        value = os.environ.get("UARTD_TOKEN", "").strip()
    if not value:
        return None
    if len(value) < 4:
        raise UartDaemonError("Auth token must contain at least 4 characters")
    return value


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
    sub.add_argument("--no-serial", action="store_true", help="Start with no serial port attached")
    sub.add_argument("--instance-id", default=None, help="Stable instance name, e.g. board-a")
    sub.add_argument("--token-file", default=None, help="File containing access token (UTF-8)")


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
    stop_parser.add_argument("--token-file", default=None)

    status_parser = subparsers.add_parser("status")
    transport = status_parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None)
    transport.add_argument("--tcp", default=None)
    status_parser.add_argument("--token-file", default=None)
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
    name = (_sanitize_name(args.instance_id) if getattr(args, "instance_id", None)
            else f"uartd-{tcp_port}" if tcp_port is not None
            else _instance_name(args.port, tcp_port))
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
        port=None if args.no_serial else args.port,
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
        auth_token=_read_auth_token(args.token_file),
        instance_id=args.instance_id or f"uartd-{tcp_port if tcp_port is not None else _sanitize_name(args.port)}",
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


def _read_control_json(sock: socket.socket) -> dict[str, Any]:
    buf = bytearray()
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise UartDaemonError("uartd closed connection without a response")
        buf.extend(chunk)
        if len(buf) > MAX_REQUEST_BYTES:
            raise UartDaemonError("response too large")
    return json.loads(bytes(buf).split(b"\n", 1)[0].decode("utf-8"))


def ping_control(socket_path: Path | None = None, tcp: str | None = None, token: str | None = None) -> dict[str, Any] | None:
    if tcp is None:
        path = socket_path if socket_path is not None else DEFAULT_SOCKET_PATH
        if not path.exists():
            return None
    try:
        with connect_control(socket_path=socket_path, tcp=tcp, timeout=1.0) as sock:
            sock.settimeout(2.0)
            request: dict[str, Any] = {"action": "status"}
            if token is not None:
                request["token"] = token
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
            return _read_control_json(sock)
    except (OSError, ValueError, UartDaemonError):
        return None


def start_daemon(args: argparse.Namespace) -> int:
    tcp_host, tcp_port = resolve_tcp_args(args)
    tcp_endpoint = _control_endpoint_for_bind(tcp_host, tcp_port)
    socket_path, pid_path, runtime_log, daemon_log = _resolved_paths(args, tcp_port)

    token = _read_auth_token(args.token_file)
    if tcp_host is not None and not _is_loopback(tcp_host) and not token:
        raise UartDaemonError("External TCP bind requires --token-file or UARTD_TOKEN")
    status = ping_control(socket_path=None if os.name == "nt" else socket_path, tcp=tcp_endpoint, token=token)
    if status is not None and status.get("ok"):
        print(f"uartd already running on {status.get('port')} (tcp={status.get('tcp')} socket={status.get('socket')})")
        return 0

    cmd = ([sys.executable] if getattr(sys, "frozen", False)
           else [sys.executable, str(Path(__file__).resolve())]) + [
        "run",
        "--port",
        args.port,
        "--baud",
        str(args.baud),
        "--socket",
        str(socket_path.resolve()),
        "--pid-file",
        str(pid_path.resolve()),
        "--runtime-log",
        str(runtime_log.resolve()),
        "--daemon-log",
        str(daemon_log.resolve()),
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
    if args.no_serial:
        cmd.append("--no-serial")
    if args.instance_id:
        cmd.extend(["--instance-id", args.instance_id])
    if args.token_file:
        cmd.extend(["--token-file", str(Path(args.token_file).expanduser().resolve())])

    daemon_log.parent.mkdir(parents=True, exist_ok=True)
    with daemon_log.open("a", encoding="utf-8") as handle:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(REPO_ROOT),
            "stdout": handle,
            "stderr": handle,
        }
        if getattr(sys, "frozen", False):
            popen_kwargs["env"] = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        if os.name == "nt":
            # DETACHED_PROCESS lets a frozen console bootloader allocate a new
            # console. CREATE_NO_WINDOW suppresses it for the long-lived child too.
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            popen_kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **popen_kwargs)

    deadline = time.time() + 5
    while time.time() < deadline:
        status = ping_control(socket_path=None if os.name == "nt" else socket_path, tcp=tcp_endpoint, token=token)
        if status is not None and status.get("ok"):
            print(
                f"uartd started pid={status.get('pid')} tcp={status.get('tcp')} socket={status.get('socket')} "
                f"pid_file={pid_path} runtime_log={runtime_log} daemon_log={daemon_log}"
            )
            return 0
        time.sleep(0.1)
    raise UartDaemonError("uartd did not become ready in time")


def send_request(socket_path: Path | None, tcp: str | None, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    with connect_control(socket_path=socket_path, tcp=tcp) as sock:
        sock.settimeout(3.0)
        req = payload.copy()
        if token is not None:
            req["token"] = token
        sock.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        return _read_control_json(sock)


def stop_daemon(socket_path: Path | None = None, tcp: str | None = None, token: str | None = None) -> int:
    response = send_request(socket_path, tcp, {"action": "stop"}, token=token)
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
            return stop_daemon(socket_path=socket_path, tcp=tcp, token=_read_auth_token(args.token_file))
        if args.command == "status":
            socket_path = Path(args.socket) if args.socket else None
            tcp = args.tcp or (DEFAULT_TCP if os.name == "nt" and args.socket is None else None)
            status = ping_control(socket_path=socket_path, tcp=tcp, token=_read_auth_token(args.token_file))
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
