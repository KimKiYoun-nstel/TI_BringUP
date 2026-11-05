"""Bounded UART I/O worker and rotating text logs (no GUI dependencies)."""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any, Callable


class SerialIO:
    """Only this thread reads/writes a live handle; notify wakes the TCP reactor."""

    def __init__(self, port: Any, notify: Callable[[], None]) -> None:
        self.port = port
        self.notify = notify
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=256)
        self.tx: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=100)
        self.stopped = threading.Event()
        self.writing = threading.Event()
        self.close_port = True
        self.thread = threading.Thread(target=self._run, name="uart-io", daemon=True)
        # Short reads keep queued writes responsive; control sockets never wait here.
        port.timeout = max(0.001, min(port.timeout if port.timeout is not None else 0.02, 0.02))

    def start(self) -> None:
        self.thread.start()

    def _emit(self, kind: str, value: Any) -> None:
        while not self.stopped.is_set():
            try:
                self.events.put((kind, value), timeout=0.05)
                self.notify()
                return
            except queue.Full:
                # Backpressure, never silently discard serial bytes.
                continue

    def _run(self) -> None:
        try:
            while not self.stopped.is_set():
                try:
                    ident, data = self.tx.get_nowait()
                except queue.Empty:
                    pass
                else:
                    self.writing.set()
                    try:
                        offset = 0
                        while offset < len(data) and not self.stopped.is_set():
                            written = self.port.write(data[offset:])
                            if not written:
                                raise OSError("Serial write made no progress")
                            offset += written
                    finally:
                        self.writing.clear()
                    if not self.stopped.is_set():
                        # ACK means accepted by serial.write, not drained on the wire.
                        # Unconditional flush can wait indefinitely in some drivers.
                        self._emit("written", ident)
                waiting = getattr(self.port, "in_waiting", 0)
                chunk = self.port.read(min(max(waiting, 1), 4096))
                if chunk:
                    self._emit("rx", chunk)
        except Exception as exc:
            self._emit("error", exc)
        finally:
            if self.close_port:
                try:
                    self.port.close()
                except OSError:
                    pass

    def stop(self, *, close: bool = True, timeout: float = 0.5) -> None:
        self.close_port = close
        self.stopped.set()
        for method in ("cancel_read", "cancel_write"):
            if method == "cancel_write" and not self.writing.is_set():
                continue
            cancel = getattr(self.port, method, None)
            if cancel:
                try:
                    cancel()
                except (OSError, AttributeError):
                    pass
        self.thread.join(timeout=timeout)
        if self.thread.is_alive():
            raise RuntimeError("UART worker did not stop; refusing concurrent handle access")


class RotatingTextLog:
    """Bounded append log; small writes are buffered and periodically flushed."""

    def __init__(self, path: Path, max_bytes: int = 10 * 1024 * 1024, backups: int = 3) -> None:
        self.path, self.max_bytes, self.backups = path, max_bytes, backups
        path.parent.mkdir(parents=True, exist_ok=True)
        self.size = path.stat().st_size if path.exists() else 0
        self.handle = path.open("a", encoding="utf-8", newline="")

    def write(self, text: str) -> None:
        size = len(text.encode("utf-8"))
        if self.size and self.size + size > self.max_bytes:
            self.handle.close()
            for index in range(self.backups, 0, -1):
                source = self.path if index == 1 else Path(f"{self.path}.{index - 1}")
                target = Path(f"{self.path}.{index}")
                if source.exists():
                    source.replace(target)
            self.handle = self.path.open("a", encoding="utf-8", newline="")
            self.size = 0
        self.handle.write(text)
        self.size += size

    def flush(self) -> None:
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()
