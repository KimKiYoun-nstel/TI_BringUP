#!/usr/bin/env python3
"""PySide6 UART manager with live UART receive and line-oriented transmit.

The GUI never opens a serial device itself; all operations target uartd over TCP.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import socket
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIntValidator, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
)

from uart_api import JsonSocketReader, UARTAPIError, parse_endpoint, request, require_ok


STYLESHEET = """
QWidget { font-family: 'Malgun Gothic', 'Segoe UI'; font-size: 13px; color: #202124; }
QMainWindow, QDialog, QWidget#root { background: #F5F6F8; }
QLabel { background: transparent; }
QLabel#subtitle { color: #505660; }
QLabel#indicator { font-weight: bold; }
QGroupBox { background: #FFFFFF; border: 1px solid #CFD3D9; border-radius: 5px;
            margin-top: 10px; padding: 12px 10px 8px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QListWidget {
    background: #FFFFFF; color: #202124; border: 1px solid #9DA4AE;
    border-radius: 3px; padding: 4px 6px; selection-background-color: #DCEAFF;
    selection-color: #123F75; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #202124;
    selection-background-color: #DCEAFF; selection-color: #123F75; outline: 0; }
QComboBox QAbstractItemView::item { min-height: 28px; }
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background: #DCEAFF; color: #123F75; }
QPushButton { background: #FFFFFF; color: #202124; border: 1px solid #9DA4AE;
    border-radius: 4px; padding: 5px 10px; }
QPushButton:hover { background: #EAF0F7; border-color: #4673A8; }
QPushButton#primary { background: #1764AE; color: #FFFFFF; border-color: #1764AE; font-weight: bold; }
QPushButton#primary:hover { background: #124F8B; }
QPushButton#danger { color: #A32323; }
QPushButton:disabled, QPushButton#primary:disabled { background: #ECEEF1; color: #626975; border-color: #CDD1D7; }
QTabWidget::pane { border: 1px solid #CFD3D9; background: #FFFFFF; }
QTabBar::tab { padding: 7px 14px; background: #E9ECF0; color: #343A43; }
QTabBar::tab:selected { background: #FFFFFF; color: #124F8B; }
QToolTip { background: #FFFFFF; color: #202124; border: 1px solid #9DA4AE; }
QStatusBar { background: #F5F6F8; color: #505660; }
"""


def configure_app(app: QApplication) -> None:
    """Set native popup/disabled colors too, independent of Windows dark mode."""
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in ((QPalette.Window, "#F5F6F8"), (QPalette.WindowText, "#202124"),
                        (QPalette.Base, "#FFFFFF"), (QPalette.AlternateBase, "#F0F2F5"),
                        (QPalette.Text, "#202124"), (QPalette.Button, "#FFFFFF"),
                        (QPalette.ButtonText, "#202124"), (QPalette.Highlight, "#DCEAFF"),
                        (QPalette.HighlightedText, "#123F75"),
                        (QPalette.ToolTipBase, "#FFFFFF"), (QPalette.ToolTipText, "#202124"),
                        (QPalette.PlaceholderText, "#626975")):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


class WorkerSignals(QObject):
    success = Signal(object)
    failure = Signal(str)


class Worker(QRunnable):
    """Run blocking networking/process calls away from the Qt UI thread."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.success.emit(self.fn())
        except Exception as exc:
            self.signals.failure.emit(str(exc))


class MonitorSignals(QObject):
    activity = Signal(object)


class UARTSender(QRunnable):
    """Ordered writes on a reusable TCP connection, independent of UI control jobs."""

    def __init__(self, endpoint: str, token: str) -> None:
        super().__init__()
        self.endpoint, self.token = endpoint, token
        self.signals = MonitorSignals()
        self.pending: queue.Queue[str] = queue.Queue(maxsize=100)
        self.stopped = threading.Event()
        self.sock: socket.socket | None = None

    def stop(self) -> None:
        self.stopped.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def run(self) -> None:
        error = ""
        sock = None
        reader = None
        try:
            while not self.stopped.is_set():
                try:
                    text = self.pending.get(timeout=0.1)
                except queue.Empty:
                    continue
                if sock is None:
                    sock = socket.create_connection(parse_endpoint(self.endpoint), timeout=3)
                    self.sock = sock
                    sock.settimeout(3)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    reader = JsonSocketReader(sock)
                if self.stopped.is_set():
                    break
                sock.sendall((json.dumps({"action": "send", "text": text, "newline": False,
                                          "token": self.token}) + "\n").encode())
                assert reader is not None
                require_ok(reader.recv_json())
                self.signals.activity.emit((self, "sent", text))
        except Exception as exc:
            error = str(exc)
        finally:
            if sock:
                sock.close()
            self.sock = None
            if not self.stopped.is_set():
                self.signals.activity.emit((self, "failed", error))
            self.signals.activity.emit((self, "closed", ""))


class TerminalInput(QLineEdit):
    """Keep a session-only command history; never persist UART input."""

    def __init__(self) -> None:
        super().__init__()
        self.history: list[str] = []
        self.position = 0
        self.draft = ""

    def remember(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
            self.history = self.history[-100:]
        self.position = len(self.history)
        self.draft = ""

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.history:
            if self.position == len(self.history):
                self.draft = self.text()
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            self.position = max(0, min(len(self.history), self.position + step))
            self.setText(self.history[self.position] if self.position < len(self.history) else self.draft)
            return
        super().keyPressEvent(event)


class UARTMonitor(QRunnable):
    """Read-only JSON tail stream; UART changes preserve this TCP connection."""

    def __init__(self, endpoint: str, token: str) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.token = token
        self.signals = MonitorSignals()
        self.stopped = threading.Event()
        self.sock: socket.socket | None = None
        self._rx_lock = threading.Lock()
        self._rx_pending = ""
        self._rx_dropped = 0

    def take_data(self) -> tuple[str, int]:
        with self._rx_lock:
            text, dropped = self._rx_pending, self._rx_dropped
            self._rx_pending, self._rx_dropped = "", 0
            return text, dropped

    def buffer_data(self, text: str) -> None:
        with self._rx_lock:
            combined = self._rx_pending + text
            self._rx_dropped += max(0, len(combined) - 262144)
            self._rx_pending = combined[-262144:]

    def stop(self) -> None:
        self.stopped.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def emit(self, kind: str, text: str = "") -> None:
        self.signals.activity.emit((self, kind, text))

    def run(self) -> None:
        error = ""
        try:
            with socket.create_connection(parse_endpoint(self.endpoint), timeout=3) as sock:
                self.sock = sock
                if self.stopped.is_set():
                    return
                sock.settimeout(0.3)
                sock.sendall((json.dumps({"action": "tail", "lines": 20, "token": self.token}) + "\n").encode())
                reader = JsonSocketReader(sock)
                ready = False
                while not self.stopped.is_set():
                    try:
                        message = reader.recv_json()
                    except socket.timeout:
                        continue
                    if not ready:
                        require_ok(message)
                        ready = True
                        self.emit("ready")
                        if message.get("backlog"):
                            self.emit("backlog", message["backlog"])
                    elif message.get("type") == "data":
                        self.buffer_data(message.get("data", ""))
        except Exception as exc:
            if not self.stopped.is_set():
                error = str(exc)
        finally:
            self.sock = None
            self.emit("closed", error)


class BaudComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.addItems([str(rate) for rate in (300, 600, 1200, 2400, 4800, 9600, 19200,
                      38400, 57600, 115200, 230400, 460800, 921600, 1000000, 2000000, 4000000)])
        self.setValidator(QIntValidator(300, 4000000, self))
        self.setToolTip("목록에서 선택하거나 300~4000000 범위의 속도를 직접 입력하세요.")
        self.setValue(115200)

    def value(self) -> int:
        return int(self.currentText())

    def setValue(self, value: int) -> None:
        self.setCurrentText(str(value))


class LocalStartDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("이 PC에 새 uartd 실행")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit("board-a")
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(17001)
        self.bind = QComboBox()
        self.bind.addItem("Local — 이 PC에서만 접속 (127.0.0.1)", "127.0.0.1")
        self.bind.addItem("External — 외부 PC 접속 허용 (0.0.0.0)", "0.0.0.0")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Local: 선택 / External: 필수 · 설정 시 4자 이상")
        form.addRow("서버 이름", self.name)
        form.addRow("서버 TCP 포트", self.port)
        form.addRow("접속 허용 범위", self.bind)
        form.addRow("접속 비밀번호", self.password)
        root.addLayout(form)
        note = QLabel("서버는 이 PC에서 실행됩니다. 실행 후 UART 장치를 연결하세요.\n"
                      "External 접속자는 이 PC의 실제 IP:포트와 같은 비밀번호를 사용합니다.\n"
                      "비밀번호는 파일에 저장하지 않습니다. 서버를 새로 실행할 때 다시 입력하세요.")
        note.setWordWrap(True)
        note.setObjectName("subtitle")
        root.addWidget(note)
        actions = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        actions.button(QDialogButtonBox.Ok).setText("서버 실행")
        actions.button(QDialogButtonBox.Cancel).setText("취소")
        actions.accepted.connect(self.validate_and_accept)
        actions.rejected.connect(self.reject)
        root.addWidget(actions)

    def validate_and_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "입력 확인", "서버 이름을 입력하세요.")
            return
        if self.bind.currentData() == "0.0.0.0" and not self.password.text().strip():
            QMessageBox.warning(self, "입력 확인", "External 접속에 사용할 비밀번호를 입력하세요.")
            return
        if self.password.text().strip() and len(self.password.text().strip()) < 4:
            QMessageBox.warning(self, "입력 확인", "접속 비밀번호는 4자 이상 입력하세요.")
            return
        self.accept()

    def options(self) -> dict[str, Any]:
        return {"id": self.name.text().strip(), "port": self.port.value(),
                "bind": self.bind.currentData(), "password": self.password.text().strip()}


def start_local_daemon(options: dict[str, Any]) -> dict[str, Any]:
    """A GUI process may be remote; this helper starts uartd only on *this* PC."""
    if getattr(sys, "frozen", False):
        binary = Path(sys.executable).with_name("uartd.exe" if sys.platform == "win32" else "uartd")
        if not binary.exists():
            raise RuntimeError(f"Companion uartd executable not found: {binary}")
        cmd = [str(binary)]
    else:
        script = Path(__file__).resolve().with_name("uartd.py")
        cmd = [sys.executable, str(script)]
    cmd.extend(["start", "--no-unix-socket", "--instance-id", options["id"],
                "--tcp", f'{options["bind"]}:{options["port"]}'])
    if options.get("device"):
        cmd.extend(["--port", options["device"], "--baud", str(options["baud"])])
    else:
        cmd.append("--no-serial")
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env.pop("UARTD_TOKEN", None)
    if options["password"]:
        env["UARTD_TOKEN"] = options["password"]
    try:
        output = subprocess.run(cmd, text=True, capture_output=True, timeout=15, check=False, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Local daemon start failed: {exc}") from exc
    if output.returncode:
        raise RuntimeError((output.stderr or output.stdout).strip() or "uartd start failed")
    return {"tcp": f'127.0.0.1:{options["port"]}', "message": output.stdout.strip(),
            "password": options["password"]}


def restart_local_daemon(endpoint: str, token: str, profile: dict[str, Any],
                         options: dict[str, Any]) -> dict[str, Any]:
    """Restart a managed process, or relaunch one explicitly stopped by Manager."""
    try:
        info = require_ok(request(endpoint, {"action": "status"}, token=token))
    except UARTAPIError as exc:
        if not profile.get("stopped") or not isinstance(exc.__cause__, ConnectionRefusedError):
            raise
        new = dict(options, device=profile.get("device"), baud=profile.get("baud", 115200))
        result = start_local_daemon(new)
        active = require_ok(request(result["tcp"], {"action": "status"}, token=new["password"]))
        result["profile"] = dict(new, pid=active["pid"])
        return result
    if (not profile.get("pid") or info.get("pid") != profile["pid"]
            or info.get("instance_id") != profile["id"]):
        raise RuntimeError("실행한 프로세스와 현재 서버가 다릅니다. 재시작을 중단했습니다.")
    if options["port"] != profile["port"] or options["bind"] != profile["bind"]:
        # A changed port can be checked before interrupting the current server.
        if options["port"] != profile["port"]:
            with socket.socket() as probe:
                probe.bind((options["bind"], options["port"]))
    old = dict(profile, password=token, device=info.get("port") if info.get("serial_state") == "connected" else None,
               baud=info.get("baud", 115200))
    new = dict(options, device=old["device"], baud=old["baud"])
    require_ok(request(endpoint, {"action": "stop"}, token=token))
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            request(endpoint, {"action": "status"}, token=token, timeout=0.3)
        except (OSError, UARTAPIError):
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("기존 서버 종료를 확인하지 못했습니다. 실행 상태를 확인하세요.")
    time.sleep(0.3)
    try:
        result = start_local_daemon(new)
        active = require_ok(request(result["tcp"], {"action": "status"}, token=new["password"]))
        result["profile"] = dict(new, pid=active["pid"])
        return result
    except Exception as exc:
        try:
            result = start_local_daemon(old)
            active = require_ok(request(endpoint, {"action": "status"}, token=token))
            result["profile"] = dict(old, pid=active["pid"])
            result["message"] = f"변경 실패: {exc}\n기존 설정으로 복구했습니다."
            return result
        except Exception as rollback:
            raise RuntimeError(f"변경 실패: {exc}\n기존 서버 복구 실패: {rollback}") from exc


class UartManager(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("uart-manager | 원격 UART 관리")
        self.resize(900, 740)
        self.setMinimumSize(800, 700)
        self.settings = QSettings("uartTool", "uart-manager")
        self.pool = QThreadPool.globalInstance()
        self.busy = False
        self._worker = None
        self._on_ok = None
        self.last_status: dict[str, Any] = {}
        self._ports_loaded = False
        self.credentials: dict[str, str] = {}
        self.local_profiles: dict[str, dict[str, Any]] = {}
        try:
            saved = json.loads(str(self.settings.value("local_profiles", "{}")))
            if isinstance(saved, dict):
                self.local_profiles = {key: value for key, value in saved.items()
                                       if isinstance(value, dict) and all(k in value for k in ("id", "port", "bind", "pid"))}
        except (ValueError, TypeError):
            pass
        self.instance_status: dict[str, dict[str, Any]] = {}
        self._active_endpoint = ""
        self._overview_worker = None
        self._build_ui()
        self._monitor: UARTMonitor | None = None
        self._monitor_workers: dict[int, UARTMonitor] = {}
        self._rx_chars = 0
        self._closing = False
        self._monitor_ready = False
        self._sender: UARTSender | None = None
        self._sender_workers: dict[int, UARTSender] = {}
        self._tx_pending = 0
        self.receive_timer = QTimer(self)
        self.receive_timer.setInterval(40)
        self.receive_timer.timeout.connect(self.flush_receive)
        self.receive_timer.start()
        self._load_endpoints()
        self.timer = QTimer(self)
        self.timer.setInterval(3500)
        self.timer.timeout.connect(lambda: self.refresh_status(background=True))
        self.timer.timeout.connect(self.refresh_instances)
        self.timer.start()
        self.refresh_status()
        self.refresh_instances()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)
        host_group = QGroupBox("1. uartd 인스턴스 — 행을 선택해 개별 관리")
        host_layout = QVBoxLayout(host_group)
        l_layout = QHBoxLayout()
        self.hosts = QComboBox()
        self.hosts.hide()
        self.hosts.setToolTip("장치가 연결된 PC의 uartd 주소를 선택하세요.")
        self.hosts.currentIndexChanged.connect(self.on_host_changed)
        self.instances = QTableWidget(0, 6)
        self.instances.setHorizontalHeaderLabels(["인스턴스", "접속 주소", "수신 범위", "COM", "Baud", "상태"])
        self.instances.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.instances.setSelectionMode(QAbstractItemView.SingleSelection)
        self.instances.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.instances.verticalHeader().hide()
        self.instances.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.instances.setMinimumHeight(125)
        self.instances.setMaximumHeight(150)
        self.instances.itemSelectionChanged.connect(self.select_instance)
        host_layout.addWidget(self.instances)
        self.hosts.model().rowsInserted.connect(self.sync_instances)
        self.hosts.model().rowsRemoved.connect(self.sync_instances)
        add_host = QPushButton("서버 주소 등록")
        add_host.setToolTip("기존 서버의 접속 주소만 등록합니다. 새 서버를 실행하지 않습니다.")
        add_host.clicked.connect(self.add_endpoint)
        remove_host = QPushButton("등록 해제")
        remove_host.setToolTip("주소록에서만 제거합니다. 서버는 종료하지 않습니다.")
        remove_host.clicked.connect(self.remove_endpoint)
        local_start = QPushButton("이 PC에 서버 실행")
        local_start.clicked.connect(self.start_local)
        l_layout.addWidget(add_host)
        l_layout.addWidget(remove_host)
        l_layout.addWidget(local_start)
        self.restart_btn = QPushButton("서버 설정 / 재시작")
        self.restart_btn.clicked.connect(self.restart_local)
        l_layout.addWidget(self.restart_btn)
        l_layout.addStretch()
        help_btn = QPushButton("도움말")
        help_btn.clicked.connect(self.show_help)
        host_layout.addLayout(l_layout)
        layout.addWidget(host_group)

        header = QHBoxLayout()
        self.connection_label = QLabel("연결 상태 확인 중")
        self.connection_label.setObjectName("indicator")
        self.target_label = QLabel("")
        self.target_label.setObjectName("subtitle")
        header.addWidget(self.connection_label)
        header.addStretch()
        header.addWidget(self.target_label)
        header.addWidget(help_btn)
        host_layout.addLayout(header)
        secret_row = QHBoxLayout()
        secret_row.addWidget(QLabel("접속 비밀번호"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("서버 실행 시 설정한 비밀번호 · 미설정 서버는 비워 둠")
        self.token_edit.returnPressed.connect(self.refresh_status)
        self.token_edit.textChanged.connect(self.remember_password)
        secret_row.addWidget(self.token_edit, 1)
        self.status_btn = QPushButton("접속 확인")
        self.status_btn.clicked.connect(self.refresh_status)
        secret_row.addWidget(self.status_btn)
        host_layout.addLayout(secret_row)
        auth_group = QWidget()
        auth_layout = QVBoxLayout(auth_group)
        self.status_fields: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        fields = [
            ("인스턴스", "instance_id"), ("프로세스 PID", "pid"),
            ("UART 상태", "serial_state"), ("현재 COM", "port"),
            ("Baudrate", "baud"), ("TCP 주소", "tcp"),
            ("RW / RO", "attached"), ("세션 번호", "session_generation"),
        ]
        for pos, (label, key) in enumerate(fields):
            r, c = divmod(pos, 2)
            label_widget = QLabel(label + "  ·", auth_group)
            value = QLabel("-", auth_group)
            for field in (label_widget, value):
                field.ensurePolished()
                field.setMinimumHeight(field.fontMetrics().height() + 8)
                field.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(label_widget, r, c * 2)
            grid.addWidget(value, r, c * 2 + 1)
            self.status_fields[key] = value
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        auth_layout.addLayout(grid)
        self.last_error = QLabel("")
        self.last_error.setStyleSheet("color: #A32323")
        self.last_error.setWordWrap(True)
        self.last_error.setVisible(False)
        host_layout.addWidget(self.last_error)
        auth_layout.addStretch()

        port_group = QGroupBox("2. 선택한 서버의 UART 장치")
        p_layout = QVBoxLayout(port_group)
        self.current_connection = QLabel("현재 연결: 확인 중")
        self.current_connection.setWordWrap(True)
        p_layout.addWidget(self.current_connection)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("장치"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.NoInsert)
        self.port_combo.setMinimumWidth(160)
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.port_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.port_combo.setMinimumContentsLength(18)
        self.port_combo.lineEdit().setPlaceholderText("장치 선택 또는 COM 번호 입력")
        self.port_combo.currentIndexChanged.connect(
            lambda _index: QTimer.singleShot(0, lambda: self.port_combo.lineEdit().setCursorPosition(0)))
        row1.addWidget(self.port_combo, 1)
        self.ports_btn = QPushButton("장치 새로고침")
        self.ports_btn.clicked.connect(self.refresh_ports)
        row1.addWidget(self.ports_btn)
        row1.addWidget(QLabel("Baud"))
        self.baud = BaudComboBox()
        row1.addWidget(self.baud)
        p_layout.addLayout(row1)
        row2 = QHBoxLayout()
        self.switch_btn = QPushButton("장치 연결")
        self.switch_btn.setObjectName("primary")
        self.switch_btn.clicked.connect(self.switch_port)
        row2.addWidget(self.switch_btn)
        self.change_baud_btn = QPushButton("속도만 적용")
        self.change_baud_btn.clicked.connect(self.change_baud)
        row2.addWidget(self.change_baud_btn)
        self.disconnect_btn = QPushButton("COM 연결 해제")
        self.disconnect_btn.clicked.connect(self.disconnect_port)
        row2.addWidget(self.disconnect_btn)
        p_layout.addLayout(row2)
        note = QLabel("장치와 속도를 선택한 뒤 ‘장치 연결’을 누르세요.")
        self.device_hint = note
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        p_layout.addWidget(note)
        layout.addWidget(port_group)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        logs_group = QWidget()
        logs_layout = QVBoxLayout(logs_group)
        logs_row = QHBoxLayout()
        self.live_check = QCheckBox("출력 ON")
        self.live_check.setToolTip("이 Manager의 실시간 UART 수신만 켜거나 끕니다. 송신·다른 클라이언트·서버 로그는 유지됩니다.")
        self.live_check.setChecked(True)
        self.live_check.toggled.connect(self.toggle_monitor)
        logs_row.addWidget(self.live_check)
        self.rx_label = QLabel("접속 확인 후 수신 대기")
        self.rx_label.setObjectName("subtitle")
        logs_row.addWidget(self.rx_label, 1)
        logs_row.addStretch()
        self.tail_btn = QPushButton("최근 80줄 조회")
        self.tail_btn.clicked.connect(self.fetch_tail)
        logs_row.addWidget(self.tail_btn)
        clear_btn = QPushButton("화면 지우기")
        clear_btn.clicked.connect(self.clear_receive)
        logs_row.addWidget(clear_btn)
        logs_layout.addLayout(logs_row)
        self.tail_text = QPlainTextEdit()
        self.tail_text.setReadOnly(True)
        self.tail_text.setMinimumHeight(60)
        self.tail_text.setMaximumBlockCount(2000)
        self.tail_text.setPlaceholderText("장치 연결 후 ‘Enter 전송’으로 프롬프트를 확인하세요. 아래 입력창에서 명령도 보낼 수 있습니다.")
        self.tail_text.setFont(QFont("Consolas", 10))
        logs_layout.addWidget(self.tail_text, 1)
        send_row = QHBoxLayout()
        self.send_edit = TerminalInput()
        self.send_edit.setPlaceholderText("선택한 서버의 UART에 보낼 내용 · Enter 키로 전송")
        self.send_edit.returnPressed.connect(self.send_terminal)
        send_row.addWidget(self.send_edit, 1)
        self.line_ending = QComboBox()
        for label, ending in (("Enter (CR)", "\r"), ("CRLF", "\r\n"), ("LF", "\n"), ("줄바꿈 없음", "")):
            self.line_ending.addItem(label, ending)
        send_row.addWidget(self.line_ending)
        self.send_btn = QPushButton("전송")
        self.send_btn.clicked.connect(self.send_terminal)
        send_row.addWidget(self.send_btn)
        self.enter_btn = QPushButton("Enter 전송")
        self.enter_btn.setToolTip("입력창 내용과 관계없이 CR(0x0D) 한 글자만 전송하여 프롬프트를 확인합니다.")
        self.enter_btn.clicked.connect(lambda: self.send_terminal(enter_only=True))
        send_row.addWidget(self.enter_btn)
        logs_layout.addLayout(send_row)
        self.tx_label = QLabel("Enter: 전송 · ↑/↓: 입력 기록 · 출력 OFF 중에도 전송 가능")
        self.tx_label.setObjectName("subtitle")
        logs_layout.addWidget(self.tx_label)
        self.tabs.addTab(logs_group, "UART 송수신 확인")
        self.tabs.addTab(auth_group, "서버 상세")
        foot = QHBoxLayout()
        self.tip = QLabel("창을 닫아도 서버와 장치 연결은 유지됩니다.")
        self.tip.setObjectName("subtitle")
        self.tip.setWordWrap(True)
        foot.addWidget(self.tip, 1)
        self.stop_btn = QPushButton("선택한 uartd 종료")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_daemon)
        l_layout.addWidget(self.stop_btn)
        auth_layout.addLayout(foot)
        self.statusBar().showMessage("준비됨")
        self.controls = [self.status_btn, self.ports_btn, self.switch_btn,
                         self.change_baud_btn, self.disconnect_btn, self.tail_btn, self.stop_btn,
                          self.hosts, self.instances, self.token_edit, self.restart_btn,
                           add_host, remove_host, local_start]

    def remember_password(self, value: str) -> None:
        self.stop_sender()
        self.stop_monitor()
        if self._active_endpoint:
            self.credentials[self._active_endpoint] = value.strip()
            self._ports_loaded = False

    def select_instance(self) -> None:
        row = self.instances.currentRow()
        if row >= 0:
            self.hosts.setCurrentIndex(row)

    def sync_instances(self, *_args: Any) -> None:
        self.instances.blockSignals(True)
        self.instances.setRowCount(self.hosts.count())
        for row in range(self.hosts.count()):
            endpoint = self.hosts.itemText(row)
            info = self.instance_status.get(endpoint, {})
            profile = self.local_profiles.get(endpoint, {})
            bind = str(info.get("tcp") or profile.get("bind") or "-")
            scope = "External" if "0.0.0.0" in bind else "Local" if "127.0.0.1" in bind else bind
            values = [info.get("instance_id") or profile.get("id") or "-", endpoint, scope,
                      info.get("port") or "-", info.get("baud") or "-",
                      info.get("error") or ({"connected": "연결됨", "disconnected": "장치 미연결"}.get(
                          str(info.get("serial_state", "")), info.get("serial_state")) or "확인 중")]
            for col, value in enumerate(values):
                item = self.instances.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.instances.setItem(row, col, item)
                if item.text() != str(value):
                    item.setText(str(value))
                item.setToolTip(str(value))
        self.instances.selectRow(self.hosts.currentIndex())
        self.instances.blockSignals(False)

    def refresh_instances(self) -> None:
        if self._overview_worker:
            return
        targets = [(self.hosts.itemText(i), self.credentials.get(self.hosts.itemText(i), ""))
                   for i in range(self.hosts.count())]
        def fetch(target: tuple[str, str]) -> tuple[str, str, dict[str, Any]]:
            endpoint, token = target
            try:
                info = require_ok(request(endpoint, {"action": "status"}, token=token, timeout=1))
            except Exception as exc:
                info = {"error": f"접속 실패: {exc}"}
            return endpoint, token, info
        def collect() -> list:
            with ThreadPoolExecutor(max_workers=8) as pool:
                return list(pool.map(fetch, targets))
        self._overview_worker = Worker(collect)
        self._overview_worker.signals.success.connect(self.overview_ready, Qt.QueuedConnection)
        self._overview_worker.signals.failure.connect(self.overview_failed, Qt.QueuedConnection)
        self.pool.start(self._overview_worker)

    @Slot(object)
    def overview_ready(self, results: list) -> None:
        self._overview_worker = None
        for endpoint, token, info in results:
            if token == self.credentials.get(endpoint, ""):
                self.instance_status[endpoint] = info
        self.sync_instances()

    @Slot(str)
    def overview_failed(self, _error: str) -> None:
        self._overview_worker = None

    def _load_endpoints(self) -> None:
        values = self.settings.value("endpoints", ["127.0.0.1:17001"])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            values = ["127.0.0.1:17001"]
        for item in values:
            try:
                parse_endpoint(item)
            except UARTAPIError:
                continue
            self.hosts.addItem(item)
        if self.hosts.count() == 0:
            self.hosts.addItem("127.0.0.1:17001")
        self.hosts.setCurrentIndex(0)

    def _save_endpoints(self) -> None:
        self.settings.setValue("endpoints", [self.hosts.itemText(i) for i in range(self.hosts.count())])
        self.settings.setValue("local_profiles", json.dumps({endpoint: {
            key: profile[key] for key in ("id", "port", "bind", "pid", "stopped", "device", "baud") if key in profile}
            for endpoint, profile in self.local_profiles.items()}))

    def selected_endpoint(self) -> str:
        return self.hosts.currentText()

    def on_host_changed(self, _row: int) -> None:
        self.stop_sender()
        self.send_edit.clear()
        self.send_edit.history.clear()
        self.send_edit.position = 0
        self.stop_monitor()
        self._ports_loaded = False
        self._active_endpoint = self.selected_endpoint()
        self.token_edit.setText(self.credentials.get(self._active_endpoint, ""))
        self.sync_instances()
        self.last_status.clear()
        self.tail_text.clear()
        self.port_combo.clear()
        self.port_combo.setEditText("")
        self.target_label.setText(self.selected_endpoint() or "")
        self._render_disconnected("상태 확인 필요")
        self.refresh_status()

    def add_endpoint(self) -> None:
        text, accepted = QInputDialog.getText(self, "기존 서버 주소 등록", "실행 중인 uartd의 접속 주소를 등록합니다 (새 서버 실행 아님).\n"
                                               "이 PC: 127.0.0.1:17001 / 다른 PC: 해당 PC의 IP:포트\n"
                                               "0.0.0.0은 접속 주소가 아닙니다. HOST:PORT:",
                                               text="192.168.0.100:17001")
        if not accepted or not text.strip():
            return
        endpoint = text.strip().removeprefix("tcp://")
        try:
            parse_endpoint(endpoint)
        except UARTAPIError as exc:
            QMessageBox.warning(self, "주소 확인", str(exc))
            return
        for i in range(self.hosts.count()):
            if self.hosts.itemText(i) == endpoint:
                self.hosts.setCurrentIndex(i)
                return
        self.hosts.addItem(endpoint)
        self._save_endpoints()
        self.hosts.setCurrentIndex(self.hosts.count() - 1)

    def remove_endpoint(self) -> None:
        row = self.hosts.currentIndex()
        if row < 0:
            return
        if self.hosts.count() == 1:
            QMessageBox.information(self, "호스트 삭제", "적어도 하나의 호스트는 유지합니다.")
            return
        self.hosts.removeItem(row)
        self._save_endpoints()
        self.hosts.setCurrentIndex(max(0, row - 1))

    def _run(self, fn: Callable[[], Any], on_ok: Callable[[Any], None], *, background: bool = False,
             on_error: Callable[[str], None] | None = None) -> None:
        if self.busy:
            if not background:
                QTimer.singleShot(100, lambda: self._run(fn, on_ok, on_error=on_error))
            return
        self.busy = True
        self._background = background
        self._worker_endpoint = self.selected_endpoint()
        if not background:
            for control in self.controls:
                control.setEnabled(False)
            self.statusBar().showMessage("요청 처리 중…")
        self._on_ok = on_ok
        self._on_error = on_error
        self._worker = Worker(fn)
        self._worker.signals.success.connect(self._success, Qt.QueuedConnection)
        self._worker.signals.failure.connect(self._failure, Qt.QueuedConnection)
        self.pool.start(self._worker)

    @Slot(object)
    def _success(self, result: Any) -> None:
        callback = self._on_ok
        self._done()
        if callback:
            callback(result)

    @Slot(str)
    def _failure(self, error: str) -> None:
        stale = self._background and self._worker_endpoint != self.selected_endpoint()
        callback = self._on_error
        self._done()
        if stale:
            return
        if callback:
            callback(error)
            return
        self._show_request_error(error)

    def _show_request_error(self, error: str) -> None:
        self.last_status.clear()
        self._render_disconnected("서버 접속 실패 · uartd 실행 여부 / 주소 / 비밀번호 확인")
        self.statusBar().showMessage(error, 10000)
        self.last_error.setText(error)
        self.last_error.setVisible(True)

    def _done(self) -> None:
        self.busy = False
        self._worker = None
        self._on_ok = None
        self._on_error = None
        if not self._background:
            for control in self.controls:
                control.setEnabled(True)
            connected = self.last_status.get("serial_state") == "connected"
            self.change_baud_btn.setEnabled(connected)
            self.disconnect_btn.setEnabled(connected)
        self._background = False

    def show_help(self) -> None:
        QMessageBox.information(self, "사용 방법 / 인증 안내",
            "1. ‘이 PC에 서버 실행’: Local(이 PC만) / External(외부 접속 허용) 선택 후 실행.\n"
            "2. ‘서버 주소 등록’: 기존 uartd의 IP:포트를 주소록에 추가합니다. 새 서버 실행이 아닙니다.\n"
            "   원격 PC의 uartd는 해당 PC에서 먼저 시작해야 합니다.\n"
            "3. 인증 사용 시: 서버 실행 때 설정한 접속 비밀번호를 입력 후 Enter.\n"
            "4. 장치 선택 → Baud 확인 → 장치 연결 (연결 후에는 연결 설정 적용).\n"
            "5. ‘UART 송수신 확인’에서 실시간 수신 / Enter 전송 / 명령 전송.\n"
            "   COM·Baud를 바꿔도 기존 uartctl attach는 유지됩니다.\n\n"
            "0.0.0.0은 모든 네트워크 인터페이스에서 접속을 받는 서버 설정입니다.\n"
            "External은 비밀번호가 필수이며 클라이언트는 서버의 실제 IP로 접속합니다.\n"
            "TCP는 암호화되지 않으므로 신뢰 LAN 또는 VPN/SSH 터널을 사용하세요.\n\n"
            "주소 삭제는 주소록만 삭제합니다. GUI를 닫아도 데몬은 유지됩니다.\n"
            "자세한 설명: docs/USER_GUIDE.md · PROTOCOL.md · MCP.md")

    def _request(self, payload: dict[str, Any], on_ok: Callable[[dict[str, Any]], None],
                 timeout: float = 3.0, *, background: bool = False,
                 on_error: Callable[[str], None] | None = None) -> None:
        endpoint = self.selected_endpoint()
        if not endpoint:
            return
        token = self.token_edit.text().strip()
        def call() -> dict[str, Any]:
            return require_ok(request(endpoint, payload, token=token, timeout=timeout))
        def current_only(info: dict[str, Any]) -> None:
            if endpoint == self.selected_endpoint() and token == self.token_edit.text().strip():
                on_ok(info)
        def current_error(error: str) -> None:
            if endpoint == self.selected_endpoint() and token == self.token_edit.text().strip():
                (on_error or self._show_request_error)(error)
        self._run(call, current_only, background=background, on_error=current_error)

    def _render_disconnected(self, message: str) -> None:
        self.connection_label.setText(message)
        self.connection_label.setStyleSheet("color: #805000")
        self.current_connection.setText("현재 연결: 확인되지 않음")
        for value in self.status_fields.values():
            value.setText("-")
        self.last_error.setText("")
        self.last_error.setVisible(False)

    def refresh_status(self, *, background: bool = False) -> None:
        if (self.busy and background) or not self.selected_endpoint():
            return
        endpoint = self.selected_endpoint()
        def update(info: dict[str, Any]) -> None:
            if endpoint != self.selected_endpoint():
                return
            previous_status = self.last_status
            self.last_status = info
            if previous_status and any(previous_status.get(k) != info.get(k) for k in ("session_generation", "baud")):
                self._rx_chars = 0
                self.rx_label.setText("설정 변경 · 새 수신 대기")
                self.append_receive(f'\n[UART 설정 변경: {info.get("port")} / {info.get("baud")} baud]\n')
            self.ensure_monitor()
            self.instance_status[endpoint] = info
            self.sync_instances()
            self.status_fields["instance_id"].setText(str(info.get("instance_id") or "-"))
            self.status_fields["pid"].setText(str(info.get("pid") or "-"))
            connected = info.get("serial_state") == "connected"
            self.connection_label.setText("호스트 접속됨")
            if self.connection_label.styleSheet() != "color: #21663B":
                self.connection_label.setStyleSheet("color: #21663B")
            self.current_connection.setText(
                f'현재 연결: {info.get("port")}  ·  {info.get("baud")} baud'
                if connected else "현재 연결: 장치 미연결 — 아래에서 장치를 선택하세요.")
            self.switch_btn.setText("연결 설정 적용" if connected else "장치 연결")
            self.device_hint.setText("변경할 장치 / 속도를 선택한 뒤 ‘연결 설정 적용’을 누르세요."
                                     if connected else "장치와 속도를 선택한 뒤 ‘장치 연결’을 누르세요.")
            self.change_baud_btn.setEnabled(connected)
            self.disconnect_btn.setEnabled(connected)
            for key in ("serial_state", "port", "baud", "tcp", "session_generation"):
                self.status_fields[key].setText(str(info.get(key) if info.get(key) is not None else "-"))
            self.status_fields["attached"].setText(
                f'{info.get("rw_attach_clients", 0)} / {info.get("ro_attach_clients", 0)}')
            self.last_error.setText(str(info.get("last_serial_error") or ""))
            self.last_error.setVisible(bool(self.last_error.text()))
            if not self.port_combo.currentText().strip() and info.get("port"):
                self.port_combo.setEditText(str(info["port"]))
            if info.get("baud") and (not previous_status or previous_status.get("baud") != info.get("baud")):
                self.baud.setValue(info["baud"])
            if not background:
                self.statusBar().showMessage(f'{endpoint}  ·  상태 조회 완료', 3500)
            if not self._ports_loaded:
                self.refresh_ports()
        self._request({"action": "status"}, update, background=background)

    def refresh_ports(self) -> None:
        def update(info: dict[str, Any]) -> None:
            self._ports_loaded = True
            previous = self.selected_port()
            self.port_combo.clear()
            for port in info.get("ports", []):
                name = port.get("device", "")
                if name:
                    description = str(port.get("description") or "")
                    self.port_combo.addItem(f"{name} — {description}" if description else name, name)
                    self.port_combo.setItemData(self.port_combo.count() - 1,
                                                str(port.get("description") or ""), Qt.ToolTipRole)
            index = self.port_combo.findData(previous)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
            elif previous:
                self.port_combo.setEditText(previous)
            self.port_combo.lineEdit().setCursorPosition(0)
            self.port_combo.lineEdit().setPlaceholderText("장치 선택 또는 COM 포트 직접 입력")
            self.last_error.clear()
            self.last_error.setVisible(False)
            self.statusBar().showMessage(f'호스트에서 {len(info.get("ports", []))}개 시리얼 포트 확인', 6000)
        def failed(error: str) -> None:
            self._ports_loaded = False
            message = ("COM 목록 조회 실패 — 서버 실행 상태와 접속 비밀번호를 확인한 뒤 "
                       "‘장치 새로고침’을 다시 누르세요.\n" + error)
            self.port_combo.lineEdit().setPlaceholderText("목록 조회 실패 · 서버 / 비밀번호 확인")
            self.last_error.setText(message)
            self.last_error.setVisible(True)
            self.statusBar().showMessage(message, 10000)
        self._request({"action": "list_ports"}, update, on_error=failed)

    def _force_needed(self, task: str) -> bool | None:
        count = int(self.last_status.get("rw_attach_clients", 0) or 0)
        if count == 0:
            return False
        answer = QMessageBox.question(
            self, "접속자 영향 확인", f'RW attach 접속자 {count}명이 있습니다.\n'
            f'{task}하면 전체 사용자의 UART 대상이 바뀝니다.\n'
            'attach 접속은 유지되며 다시 접속할 필요가 없습니다. 계속하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return True if answer == QMessageBox.Yes else None

    def switch_port(self) -> None:
        if not self.valid_baud():
            return
        target = self.selected_port()
        if not target:
            QMessageBox.warning(self, "포트 확인", "연결할 COM 또는 장치 경로를 입력하세요.")
            return
        force = self._force_needed("COM 포트를 변경")
        if force is None:
            return
        def update(info: dict[str, Any]) -> None:
            self.statusBar().showMessage(f'{info.get("previous_port")} → {info.get("port")}: 연결 완료', 6000)
            self.refresh_status()
        self._request({"action": "set_port", "port": target, "baud": self.baud.value(), "force": force}, update)

    def selected_port(self) -> str:
        index = self.port_combo.currentIndex()
        if index >= 0 and self.port_combo.currentText() == self.port_combo.itemText(index):
            return str(self.port_combo.itemData(index) or self.port_combo.currentText()).strip()
        return self.port_combo.currentText().strip()

    def change_baud(self) -> None:
        if not self.valid_baud():
            return
        def update(info: dict[str, Any]) -> None:
            self.statusBar().showMessage(f'Baudrate {info.get("previous_baud")} → {info.get("baud")}', 5000)
            self.refresh_status()
        self._request({"action": "baud", "baud": self.baud.value()}, update)

    def valid_baud(self) -> bool:
        if self.baud.lineEdit().hasAcceptableInput():
            return True
        QMessageBox.warning(self, "속도 확인", "Baudrate를 목록에서 선택하거나 300~4000000의 정수로 입력하세요.")
        self.baud.setFocus()
        return False

    def disconnect_port(self) -> None:
        force = self._force_needed("시리얼 연결을 해제")
        if force is None:
            return
        self._request({"action": "disconnect_port", "force": force}, lambda _info: self.refresh_status())

    def fetch_tail(self) -> None:
        def update(info: dict[str, Any]) -> None:
            self.append_receive("\n[이전 수신 로그 80줄 · 실시간 수신과 구분]\n" + info.get("text", ""))
        self._request({"action": "tail_once", "lines": 80}, update)

    def append_receive(self, text: str) -> None:
        # A line-oriented diagnostic view, not a full ANSI terminal emulator.
        text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", text)
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        cursor = self.tail_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        excess = self.tail_text.document().characterCount() - 262144
        if excess > 0:
            trim = QTextCursor(self.tail_text.document())
            trim.setPosition(0)
            trim.setPosition(excess, QTextCursor.KeepAnchor)
            trim.removeSelectedText()
        self.tail_text.setTextCursor(cursor)
        self.tail_text.ensureCursorVisible()

    def flush_receive(self) -> None:
        if not self._monitor:
            return
        text, dropped = self._monitor.take_data()
        if text or dropped:
            if dropped:
                self.append_receive(f"\n[화면 표시 {dropped}자 생략 · 서버 로그 별도 보존]\n")
            self.append_receive(text)
            self._rx_chars += len(text) + dropped
            self.rx_label.setText(f'실수신 {self._rx_chars}자 · {time.strftime("%H:%M:%S")}')

    def clear_receive(self) -> None:
        if self._monitor:
            self._monitor.take_data()
        self.tail_text.clear()
        self._rx_chars = 0
        self.rx_label.setText("새 수신 대기 · Enter 전송으로 확인")

    def stop_monitor(self) -> None:
        if self._monitor:
            self._monitor.stop()
        self._monitor = None
        self._monitor_ready = False
        self._rx_chars = 0
        self.rx_label.setText("출력 OFF · 송신과 서버 수신 로그는 계속 동작")

    def toggle_monitor(self, enabled: bool) -> None:
        self.live_check.setText("출력 ON" if enabled else "출력 OFF")
        if enabled:
            self.ensure_monitor()
        else:
            self.stop_monitor()

    def ensure_monitor(self) -> None:
        if self._closing or not self.live_check.isChecked() or not self.last_status.get("ok"):
            return
        endpoint, token = self.selected_endpoint(), self.token_edit.text().strip()
        if self._monitor and (self._monitor.endpoint, self._monitor.token) == (endpoint, token):
            return
        self.stop_monitor()
        monitor = UARTMonitor(endpoint, token)
        self._monitor = monitor
        self._monitor_workers[id(monitor)] = monitor
        monitor.signals.activity.connect(self.monitor_event, Qt.QueuedConnection)
        self.rx_label.setText("수신 스트림 연결 중…")
        self.pool.start(monitor)

    @Slot(object)
    def monitor_event(self, event: tuple[UARTMonitor, str, str]) -> None:
        monitor, kind, text = event
        if kind == "closed":
            self._monitor_workers.pop(id(monitor), None)
        if monitor is not self._monitor or self._closing:
            return
        if kind == "ready":
            self._monitor_ready = True
            self.rx_label.setText("새 수신 대기 · Enter 전송으로 확인")
        elif kind == "backlog" and text:
            self.append_receive("[이전 수신 로그 20줄 · 새 수신 아님]\n" + text + "\n[이후 실시간 수신]\n")
        elif kind == "data":
            self.append_receive(text)
            self._rx_chars += len(text)
            self.rx_label.setText(f'실수신 {self._rx_chars}자 · {time.strftime("%H:%M:%S")}')
        elif kind == "closed":
            self._monitor = None
            self._monitor_ready = False
            self.rx_label.setText("수신 끊김 · 접속 확인 / 자동 재연결 대기")
            self.rx_label.setToolTip(text)

    def send_terminal(self, _checked: bool = False, *, enter_only: bool = False) -> None:
        if self.last_status.get("serial_state") != "connected":
            self.statusBar().showMessage("먼저 COM 장치를 연결하세요.", 6000)
            return
        original = None if enter_only else self.send_edit.text()
        text = "\r" if enter_only else (original or "") + str(self.line_ending.currentData())
        if not text:
            return
        self._transmit_text(text, original)

    def _transmit_text(self, text: str, original: str | None) -> None:
        endpoint, token = self.selected_endpoint(), self.token_edit.text().strip()
        if not self._sender or (self._sender.endpoint, self._sender.token) != (endpoint, token):
            self.stop_sender()
            sender = UARTSender(endpoint, token)
            self._sender = sender
            self._sender_workers[id(sender)] = sender
            sender.signals.activity.connect(self.sender_event, Qt.QueuedConnection)
            self.pool.start(sender)
        try:
            self._sender.pending.put_nowait(text)
        except queue.Full:
            self.tx_label.setText("송신 대기열이 가득 찼습니다. 입력을 유지합니다.")
            return
        self._tx_pending += 1
        if original is not None:
            self.send_edit.remember(original)
            self.send_edit.clear()
        self.send_edit.setFocus()
        self.tx_label.setText(f"송신 대기 {self._tx_pending}건")

    def stop_sender(self) -> None:
        if self._sender:
            self._sender.stop()
        self._sender = None
        self._tx_pending = 0
        self.tx_label.setText("Enter: 전송 · ↑/↓: 입력 기록 · 출력 OFF 중에도 전송 가능")

    @Slot(object)
    def sender_event(self, event: tuple[UARTSender, str, str]) -> None:
        sender, kind, text = event
        if kind == "closed":
            self._sender_workers.pop(id(sender), None)
        if sender is not self._sender or self._closing:
            return
        if kind == "sent":
            self._tx_pending -= 1
            self.tx_label.setText(f"송신 대기 {self._tx_pending}건" if self._tx_pending else "송신 완료 · 다음 입력 가능")
        elif kind == "failed":
            self.tx_label.setText(f"송신 확인 실패 ({self._tx_pending}건 미확인): {text}")
            self.tx_label.setToolTip("이미 전송됐을 수 있습니다. 중복 실행 방지를 위해 자동 재전송하지 않습니다.")
            self._sender = None
            self._tx_pending = 0

    def closeEvent(self, event: Any) -> None:
        self._closing = True
        self.timer.stop()
        self.receive_timer.stop()
        self.stop_sender()
        self.stop_monitor()
        super().closeEvent(event)

    def stop_daemon(self) -> None:
        endpoint = self.selected_endpoint()
        if not endpoint:
            return
        answer = QMessageBox.question(
            self, "uartd 프로세스 종료", f'{endpoint}에 실행 중인 uartd를 종료합니다.\n'
            '원격 attach/MCP 접속도 끊깁니다. 종료하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        def update(_info: dict[str, Any]) -> None:
            if endpoint in self.local_profiles:
                self.local_profiles[endpoint].update(stopped=True,
                    device=self.last_status.get("port") if self.last_status.get("serial_state") == "connected" else None,
                    baud=self.last_status.get("baud", 115200))
                self._save_endpoints()
            self.instance_status[endpoint] = {"error": "종료 요청됨"}
            self.sync_instances()
            self.last_status.clear()
            self._render_disconnected("uartd 종료 요청 완료")
            self.statusBar().showMessage("uartd 종료 요청이 전달되었습니다.", 6000)
        self._request({"action": "stop"}, update)

    def start_local(self) -> None:
        dialog = LocalStartDialog(self)
        used = {parse_endpoint(self.hosts.itemText(i))[1] for i in range(self.hosts.count())}
        port = next((p for p in range(17001, 65536) if p not in used), 17001)
        dialog.port.setValue(port)
        dialog.name.setText(f"board-{port}")
        if dialog.exec() != QDialog.Accepted:
            return
        opts = dialog.options()
        def launch() -> dict[str, Any]:
            with socket.socket() as probe:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind((opts["bind"], opts["port"]))
            result = start_local_daemon(opts)
            info = require_ok(request(result["tcp"], {"action": "status"}, token=opts["password"]))
            result["profile"] = dict(opts, pid=info["pid"])
            return result
        self._run(launch, self.local_started)

    def restart_local(self) -> None:
        endpoint = self.selected_endpoint()
        profile = self.local_profiles.get(endpoint)
        if not profile:
            QMessageBox.information(self, "로컬 인스턴스 관리", "이 Manager에서 실행 이력을 보관한 로컬 서버만 재시작할 수 있습니다.\n"
                                    "기존·원격 서버의 COM과 Baud는 아래 UART 설정에서 변경하세요.")
            return
        dialog = LocalStartDialog(self)
        dialog.setWindowTitle("선택한 서버 설정 변경 / 재시작")
        dialog.name.setText(profile["id"])
        dialog.port.setValue(profile["port"])
        dialog.bind.setCurrentIndex(dialog.bind.findData(profile["bind"]))
        dialog.password.setText(self.credentials.get(endpoint, ""))
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).setText("설정 적용 / 재시작")
        if dialog.exec() != QDialog.Accepted:
            return
        if QMessageBox.question(self, "서버 재시작", f"{endpoint} 서버를 재시작합니다.\n"
                                "접속 중인 클라이언트는 끊어지며, 현재 COM / Baud로 다시 연결합니다.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        opts = dialog.options()
        token = self.credentials.get(endpoint, "")
        def update(result: dict[str, Any]) -> None:
            self.local_profiles.pop(endpoint, None)
            self.instance_status.pop(endpoint, None)
            if result["tcp"] != endpoint:
                self.hosts.removeItem(self.hosts.findText(endpoint))
                self.credentials.pop(endpoint, None)
            self.local_started(result)
        self._run(lambda: restart_local_daemon(endpoint, token, profile, opts), update)

    def local_started(self, result: dict[str, Any]) -> None:
        self.local_profiles[result["tcp"]] = result["profile"]
        self.credentials[result["tcp"]] = result["password"]
        def update(result: dict[str, Any]) -> None:
            endpoint = result["tcp"]
            for i in range(self.hosts.count()):
                if self.hosts.itemText(i) == endpoint:
                    self.hosts.setCurrentIndex(i)
                    break
            else:
                self.hosts.addItem(endpoint)
                self._save_endpoints()
                self.hosts.setCurrentIndex(self.hosts.count() - 1)
            self.token_edit.setText(result["password"])
            self.statusBar().showMessage(result["message"], 7000)
            # 주소 선택 시 발생한 이전 조회 요청이 끝나면 토큰이 반영된 상태로 갱신한다.
            QTimer.singleShot(1200, self.refresh_status)
        update(result)
        self._save_endpoints()
        self.sync_instances()


def main() -> int:
    app = QApplication(sys.argv)
    configure_app(app)
    manager = UartManager()
    manager.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
