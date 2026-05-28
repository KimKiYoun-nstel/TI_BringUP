from __future__ import annotations

import json
import queue
import socket
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import tools.uart.uartd as uartd


class FakeSerial:
    def __init__(self, *args, **kwargs) -> None:
        self.read_queue: queue.Queue[bytes] = queue.Queue()
        self.writes: list[bytes] = []
        self.closed = False

    def read(self, _size: int) -> bytes:
        try:
            return self.read_queue.get(timeout=0.05)
        except queue.Empty:
            return b""

    def write(self, payload: bytes) -> int:
        self.writes.append(payload)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class DaemonHarness:
    def __init__(self, tmp_path: Path) -> None:
        self.fake_serial = FakeSerial()
        self.patch = patch.object(uartd, "serial", SimpleNamespace(Serial=lambda **kwargs: self.fake_serial))
        self.patch.start()
        self.config = uartd.DaemonConfig(
            port="/dev/ttyUSB1",
            baud=115200,
            socket_path=tmp_path / "uartd.sock",
            pid_path=tmp_path / "uartd.pid",
            runtime_log=tmp_path / "runtime_log",
            daemon_log=tmp_path / "uartd.log",
            read_timeout=0.05,
            write_timeout=0.05,
            encoding="utf-8",
            exclusive=False,
        )
        self.daemon = uartd.UartDaemon(self.config)
        self.thread = threading.Thread(target=self.daemon.run_loop, daemon=True)

    def start(self) -> None:
        self.daemon._write_pid()
        self.daemon._setup_serial()
        self.daemon._setup_socket()
        self.thread.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.config.socket_path.exists():
                return
            time.sleep(0.05)
        raise AssertionError("uartd socket was not created")

    def close(self) -> None:
        try:
            try:
                response = self.request({"action": "stop"})
                assert response["ok"] is True
            except Exception:
                self.daemon.running = False
            self.thread.join(timeout=5)
        finally:
            self.daemon.cleanup()
            self.patch.stop()

    def request(self, payload: dict) -> dict:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(self.config.socket_path))
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            return self._recv_json(sock)

    def open_stream(self, payload: dict) -> tuple[socket.socket, dict]:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(self.config.socket_path))
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        return sock, self._recv_json(sock)

    def _recv_json(self, sock: socket.socket) -> dict:
        buffer = ""
        deadline = time.time() + 5
        while time.time() < deadline:
            chunk = sock.recv(4096)
            if not chunk:
                raise AssertionError("socket closed before JSON response")
            buffer += chunk.decode("utf-8", errors="replace")
            if "\n" not in buffer:
                continue
            line, _rest = buffer.split("\n", 1)
            if line.strip():
                return json.loads(line)
        raise AssertionError("timed out waiting for JSON response")


class UartDaemonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory(prefix="uartd-test-")
        self.harness = DaemonHarness(Path(self.temp_dir.name))
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.close()
        self.temp_dir.cleanup()

    def test_baseline_status_send_expect_tail(self) -> None:
        status = self.harness.request({"action": "status"})
        self.assertTrue(status["ok"])
        self.assertEqual(status["port"], "/dev/ttyUSB1")

        self.harness.fake_serial.read_queue.put(b"U-Boot SPL 2026.01\r\n")
        expect = self.harness.request({"action": "expect", "pattern": "U-Boot SPL", "timeout": 1})
        self.assertTrue(expect["ok"])

        send = self.harness.request({"action": "send", "text": "boot", "newline": True})
        self.assertTrue(send["ok"])
        self.assertEqual(self.harness.fake_serial.writes[-1], b"boot\n")

        def delayed_prompt() -> None:
            time.sleep(0.2)
            self.harness.fake_serial.read_queue.put(b"=> ")

        prompt_thread = threading.Thread(target=delayed_prompt, daemon=True)
        prompt_thread.start()
        command = self.harness.request(
            {"action": "send_expect", "text": "printenv", "expect": "=> ", "timeout": 2, "newline": True}
        )
        self.assertTrue(command["ok"])
        self.assertEqual(command["matched"], "=> ")
        self.assertIn("=> ", command["output"])
        self.assertEqual(command["expect"], "=> ")
        self.assertTrue(command["shared_write"])
        prompt_thread.join(timeout=1)

        tail_sock, response = self.harness.open_stream({"action": "tail", "lines": 20})
        try:
            self.assertTrue(response["ok"])
            self.assertIn("U-Boot SPL 2026.01", response["backlog"])
            self.harness.fake_serial.read_queue.put(b"login: ")
            event = self.harness._recv_json(tail_sock)
            self.assertEqual(event["type"], "data")
            self.assertEqual(event["data"], "login: ")
        finally:
            tail_sock.close()

        text = self.harness.config.runtime_log.read_text(encoding="utf-8", errors="replace")
        self.assertIn("U-Boot SPL 2026.01", text)
        self.assertIn("=> ", text)

    def test_send_expect_timeout_returns_tail_and_output(self) -> None:
        def delayed_boot_output() -> None:
            time.sleep(0.05)
            self.harness.fake_serial.read_queue.put(b"starting boot...\r\n")

        output_thread = threading.Thread(target=delayed_boot_output, daemon=True)
        output_thread.start()
        response = self.harness.request(
            {"action": "send_expect", "text": "boot", "expect": "login:", "timeout": 0.6, "newline": True}
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["expect"], "login:")
        self.assertIn("output_since_start", response)
        self.assertIn("starting boot...", response["tail"])
        output_thread.join(timeout=1)

    def test_attach_and_watch_streams(self) -> None:
        self.harness.fake_serial.read_queue.put(b"booting...\r\n")
        watch_sock, watch_response = self.harness.open_stream({"action": "attach", "mode": "ro", "backlog_lines": 10})
        try:
            self.assertTrue(watch_response["ok"])
            self.assertEqual(watch_response["mode"], "ro")
            watch_data = watch_sock.recv(4096)
            self.assertIn(b"booting...", watch_data)

            watch_sock.sendall(b"ignored")
            time.sleep(0.1)
            self.assertEqual(self.harness.fake_serial.writes, [])
        finally:
            watch_sock.close()

        attach_sock, attach_response = self.harness.open_stream({"action": "attach", "mode": "rw", "backlog_lines": 0})
        try:
            self.assertTrue(attach_response["ok"])
            self.assertEqual(attach_response["mode"], "rw")

            self.harness.fake_serial.read_queue.put(b"=> ")
            attach_data = attach_sock.recv(4096)
            self.assertEqual(attach_data, b"=> ")

            attach_sock.sendall(b"printenv\r")
            deadline = time.time() + 2
            while time.time() < deadline:
                if self.harness.fake_serial.writes:
                    break
                time.sleep(0.05)
            self.assertEqual(self.harness.fake_serial.writes[-1], b"printenv\r")
        finally:
            attach_sock.close()

        status = self.harness.request({"action": "status"})
        self.assertIn("attached_clients", status)
        self.assertTrue(status["shared_write"])


if __name__ == "__main__":
    unittest.main()
