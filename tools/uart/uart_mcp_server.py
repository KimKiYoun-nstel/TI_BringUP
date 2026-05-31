#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOCKET = Path(os.environ.get("UARTD_SOCKET", REPO_ROOT / "logs" / "uartd.sock"))
DEFAULT_TIMEOUT = float(os.environ.get("UART_MCP_DEFAULT_TIMEOUT", "10"))
DEFAULT_NEWLINE = os.environ.get("UART_MCP_DEFAULT_NEWLINE", "crlf")
PROTOCOL_VERSION = "2024-11-05"


class UartMcpError(Exception):
    pass


@dataclass
class UartdClient:
    socket_path: Path

    def request(self, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT + 3
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(effective_timeout)
            sock.connect(str(self.socket_path))
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            response = self._recv_json(sock)
        return response

    def _recv_json(self, sock: socket.socket) -> dict[str, Any]:
        buffer = ""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                raise UartMcpError("uartd closed the connection")
            buffer += chunk.decode("utf-8", errors="replace")
            if "\n" not in buffer:
                continue
            line, _rest = buffer.split("\n", 1)
            if line.strip():
                return json.loads(line)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UART MCP stdio adapter")
    parser.add_argument("--socket", default=str(DEFAULT_SOCKET))
    parser.add_argument("--default-timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--default-newline", default=DEFAULT_NEWLINE)
    return parser


def detect_state_hint(text: str) -> str:
    stripped = text.rstrip()
    if stripped.endswith("=>"):
        return "uboot"
    if stripped.endswith("#"):
        return "linux_root"
    if stripped.endswith("$"):
        return "linux_user"
    if "Password:" in text:
        return "password_prompt"
    if "login:" in text:
        return "linux_login"
    return "unknown"


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "uart_status",
            "description": "Check the persistent UART daemon status, including serial port, baudrate, active clients, current RX offset, and recent writer metadata. Use this before interacting with a real board over UART.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "uart_tail",
            "description": "Read recent UART console output from the daemon buffer or runtime log. Use this first when you need to understand whether the board is in U-Boot, Linux login, Linux shell, booting, or an unknown state. This is read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lines": {"type": "integer", "default": 120, "minimum": 1, "maximum": 1000}
                },
            },
        },
        {
            "name": "uart_sendline",
            "description": "Send one line of text to the UART console through the persistent daemon without waiting for output. Use this for login input, boot countdown interruption, interactive prompts, or cases where waiting is handled separately by uart_expect.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "line": {"type": "string"},
                    "newline": {"type": "string", "enum": ["lf", "crlf", "cr", "none"], "default": DEFAULT_NEWLINE},
                },
                "required": ["line"],
            },
        },
        {
            "name": "uart_expect",
            "description": "Wait for a string pattern to appear in UART output. Use this after sending input, during boot, or when waiting for U-Boot/Linux shell prompts such as '=> ', 'login:', '# ', or '$ '.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "timeout": {"type": "number", "default": DEFAULT_TIMEOUT},
                    "from": {"type": "string", "enum": ["now", "buffer"], "default": "now"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "uart_command",
            "description": "Send a command line to the UART console and wait until an expected prompt or pattern appears. Use this for normal U-Boot or Linux shell commands after identifying the current prompt with uart_tail.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "line": {"type": "string"},
                    "expect": {"type": "string"},
                    "timeout": {"type": "number", "default": DEFAULT_TIMEOUT},
                    "newline": {"type": "string", "enum": ["lf", "crlf", "cr", "none"], "default": DEFAULT_NEWLINE},
                },
                "required": ["line", "expect"],
            },
        },
        {
            "name": "uart_reboot_to_uboot",
            "description": "From a Linux shell or login prompt, reboot the board and stop at the U-Boot prompt using a single managed flow over uartd.sock. Use this when you need reliable self-reboot to U-Boot entry without manually chaining separate send/expect steps.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "login_user": {"type": "string", "default": "root"},
                    "shell_prompt": {"type": "string", "default": "# "},
                    "login_prompt": {"type": "string", "default": "login:"},
                    "password_prompt": {"type": "string", "default": "Password:"},
                    "reboot_command": {"type": "string", "default": "reboot"},
                    "autoboot_prompt": {"type": "string", "default": "Hit any key to stop autoboot"},
                    "uboot_prompt": {"type": "string", "default": "=> "},
                    "shell_timeout": {"type": "number", "default": 10},
                    "reboot_timeout": {"type": "number", "default": 60},
                    "uboot_timeout": {"type": "number", "default": 5},
                    "newline": {"type": "string", "enum": ["lf", "crlf", "cr", "none"], "default": DEFAULT_NEWLINE}
                }
            },
        },
    ]


def make_tool_result(payload: dict[str, Any], text: str, is_error: bool = False) -> dict[str, Any]:
    result = {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
    }
    if is_error:
        result["isError"] = True
    return result


def summarize_status(data: dict[str, Any]) -> str:
    return (
        f"uartd port={data.get('port')} baud={data.get('baud')} clients={data.get('clients')} "
        f"attach_clients={data.get('attach_clients', data.get('attached_clients', 0))} offset={data.get('offset')}"
    )


def normalize_tail(data: dict[str, Any]) -> dict[str, Any]:
    text = data.get("text", "")
    return {
        "ok": data.get("ok", False),
        "lines": data.get("lines"),
        "offset": data.get("offset"),
        "state_hint": detect_state_hint(text),
        "text": text,
    }


def normalize_expect(data: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    if data.get("ok"):
        return {
            "ok": True,
            "matched": True,
            "pattern": data.get("pattern", data.get("expect", data.get("matched"))),
            "output": data.get("output", ""),
            "start_offset": data.get("start_offset"),
            "end_offset": data.get("end_offset", data.get("offset")),
            "elapsed_ms": elapsed_ms,
        }
    return {
        "ok": False,
        "error": data.get("error", "timeout"),
        "matched": False,
        "pattern": data.get("pattern", data.get("expect")),
        "output": data.get("output_since_start", data.get("output", "")),
        "tail": data.get("tail", ""),
        "elapsed_ms": elapsed_ms,
        "suggestion": "Check the current console state with uart_tail before retrying.",
    }


def normalize_command(data: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    text = data.get("output", data.get("output_since_start", ""))
    if data.get("ok"):
        return {
            "ok": True,
            "matched": True,
            "state_hint": detect_state_hint(text),
            "sent": data.get("sent", ""),
            "expect": data.get("expect", data.get("pattern", data.get("matched"))),
            "output": text,
            "start_offset": data.get("start_offset"),
            "end_offset": data.get("end_offset", data.get("offset")),
            "elapsed_ms": elapsed_ms,
            "active_attach_clients": data.get("active_attach_clients"),
            "shared_write": data.get("shared_write", True),
        }
    return {
        "ok": False,
        "error": data.get("error", "timeout"),
        "matched": False,
        "expect": data.get("expect", data.get("pattern")),
        "output_since_command": data.get("output_since_start", text),
        "tail": data.get("tail", ""),
        "start_offset": data.get("start_offset"),
        "end_offset": data.get("offset"),
        "elapsed_ms": elapsed_ms,
        "suggestion": "The prompt may be different. Use uart_tail to inspect the current state.",
        "active_attach_clients": data.get("active_attach_clients"),
        "shared_write": data.get("shared_write", True),
    }


def normalize_reboot_flow(data: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    return {
        "ok": data.get("ok", False),
        "state_before": data.get("state_before"),
        "steps": data.get("steps", []),
        "final_prompt": data.get("final_prompt"),
        "elapsed_ms": elapsed_ms,
    }


def handle_tool_call(client: UartdClient, name: str, arguments: dict[str, Any], default_timeout: float, default_newline: str) -> dict[str, Any]:
    start = time.monotonic()

    if name == "uart_status":
        raw = client.request({"action": "status"}, timeout=default_timeout + 3)
        return make_tool_result(raw, summarize_status(raw), is_error=not raw.get("ok"))

    if name == "uart_tail":
        lines = int(arguments.get("lines", 120))
        raw = client.request({"action": "tail_once", "lines": lines}, timeout=default_timeout + 3)
        normalized = normalize_tail(raw)
        return make_tool_result(normalized, normalized.get("text", ""), is_error=not normalized.get("ok"))

    if name == "uart_sendline":
        line = arguments.get("line")
        if not isinstance(line, str):
            raise UartMcpError("uart_sendline requires string field 'line'")
        newline = arguments.get("newline", default_newline)
        raw = client.request({"action": "send", "text": line, "newline": newline}, timeout=default_timeout + 3)
        return make_tool_result(raw, f"sent {raw.get('sent', '')!r}", is_error=not raw.get("ok"))

    if name == "uart_expect":
        pattern = arguments.get("pattern")
        if not isinstance(pattern, str):
            raise UartMcpError("uart_expect requires string field 'pattern'")
        timeout = float(arguments.get("timeout", default_timeout))
        from_mode = arguments.get("from", "now")
        raw = client.request({"action": "expect", "pattern": pattern, "timeout": timeout, "from": from_mode}, timeout=timeout + 3)
        normalized = normalize_expect(raw, int((time.monotonic() - start) * 1000))
        return make_tool_result(normalized, normalized.get("output", normalized.get("error", "")), is_error=not normalized.get("ok"))

    if name == "uart_command":
        line = arguments.get("line")
        expect = arguments.get("expect")
        if not isinstance(line, str) or not isinstance(expect, str):
            raise UartMcpError("uart_command requires string fields 'line' and 'expect'")
        timeout = float(arguments.get("timeout", default_timeout))
        newline = arguments.get("newline", default_newline)
        raw = client.request(
            {"action": "send_expect", "text": line, "expect": expect, "timeout": timeout, "newline": newline},
            timeout=timeout + 3,
        )
        normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
        return make_tool_result(normalized, normalized.get("output", normalized.get("output_since_command", normalized.get("error", ""))), is_error=not normalized.get("ok"))

    if name == "uart_reboot_to_uboot":
        login_user = arguments.get("login_user", "root")
        shell_prompt = arguments.get("shell_prompt", "# ")
        login_prompt = arguments.get("login_prompt", "login:")
        password_prompt = arguments.get("password_prompt", "Password:")
        reboot_command = arguments.get("reboot_command", "reboot")
        autoboot_prompt = arguments.get("autoboot_prompt", "Hit any key to stop autoboot")
        uboot_prompt = arguments.get("uboot_prompt", "=> ")
        shell_timeout = float(arguments.get("shell_timeout", 10))
        reboot_timeout = float(arguments.get("reboot_timeout", 60))
        uboot_timeout = float(arguments.get("uboot_timeout", 5))
        newline = arguments.get("newline", default_newline)

        for value, label in [
            (login_user, "login_user"),
            (shell_prompt, "shell_prompt"),
            (login_prompt, "login_prompt"),
            (password_prompt, "password_prompt"),
            (reboot_command, "reboot_command"),
            (autoboot_prompt, "autoboot_prompt"),
            (uboot_prompt, "uboot_prompt"),
            (newline, "newline"),
        ]:
            if not isinstance(value, str):
                raise UartMcpError(f"uart_reboot_to_uboot requires string field '{label}'")

        tail = normalize_tail(client.request({"action": "tail_once", "lines": 40}, timeout=default_timeout + 3))
        state_before = tail.get("state_hint", "unknown")
        steps: list[dict[str, Any]] = []

        if state_before == "password_prompt":
            raw = client.request({"action": "send_expect", "text": "", "expect": login_prompt, "timeout": shell_timeout, "newline": newline, "from": "fresh"}, timeout=shell_timeout + 3)
            steps.append({"name": "password_to_login", **normalize_command(raw, int((time.monotonic() - start) * 1000))})
            state_before = "linux_login"

        if state_before == "linux_login":
            raw = client.request({"action": "send_expect", "text": login_user, "expect": shell_prompt, "timeout": shell_timeout, "newline": newline, "from": "fresh"}, timeout=shell_timeout + 3)
            normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
            steps.append({"name": "login_to_shell", **normalized})
            if not normalized.get("ok"):
                result = normalize_reboot_flow({"ok": False, "state_before": state_before, "steps": steps, "final_prompt": None}, int((time.monotonic() - start) * 1000))
                return make_tool_result(result, normalized.get("output_since_command", normalized.get("error", "")), is_error=True)
            state_before = "linux_root"

        if state_before != "linux_root":
            raise UartMcpError(f"uart_reboot_to_uboot requires Linux shell/login state, got '{state_before}'")

        raw = client.request({"action": "send_expect", "text": reboot_command, "expect": autoboot_prompt, "timeout": reboot_timeout, "newline": newline, "from": "fresh"}, timeout=reboot_timeout + 3)
        normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
        steps.append({"name": "reboot_to_autoboot", **normalized})
        if not normalized.get("ok"):
            result = normalize_reboot_flow({"ok": False, "state_before": state_before, "steps": steps, "final_prompt": None}, int((time.monotonic() - start) * 1000))
            return make_tool_result(result, normalized.get("output_since_command", normalized.get("error", "")), is_error=True)

        raw = client.request({"action": "send_expect", "text": "", "expect": uboot_prompt, "timeout": uboot_timeout, "newline": newline, "from": "fresh"}, timeout=uboot_timeout + 3)
        normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
        steps.append({"name": "interrupt_to_uboot", **normalized})

        result = normalize_reboot_flow({"ok": normalized.get("ok", False), "state_before": "linux_root", "steps": steps, "final_prompt": uboot_prompt if normalized.get("ok") else None}, int((time.monotonic() - start) * 1000))
        text = normalized.get("output", normalized.get("output_since_command", normalized.get("error", "")))
        return make_tool_result(result, text, is_error=not normalized.get("ok"))

    raise UartMcpError(f"unknown tool: {name}")


def read_message(stdin) -> dict[str, Any] | None:
    while True:
        line = stdin.buffer.readline()
        if not line:
            return None

        line = line.strip()
        if not line:
            continue

        return json.loads(line.decode("utf-8"))


def write_message(stdout, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stdout.buffer.write(body + b"\n")
    stdout.buffer.flush()


def make_success_response(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def make_error_response(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def serve(args: argparse.Namespace) -> int:
    client = UartdClient(Path(args.socket))

    while True:
        message = read_message(sys.stdin)
        if message is None:
            return 0

        method = message.get("method")
        message_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                requested_version = params.get("protocolVersion", PROTOCOL_VERSION)
                response = make_success_response(
                    message_id,
                    {
                        "protocolVersion": requested_version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "uart", "version": "0.1.0"},
                    },
                )
                write_message(sys.stdout, response)
                continue

            if method == "notifications/initialized":
                continue

            if method == "ping":
                if message_id is not None:
                    write_message(sys.stdout, make_success_response(message_id, {}))
                continue

            if method == "tools/list":
                write_message(sys.stdout, make_success_response(message_id, {"tools": tool_definitions()}))
                continue

            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not isinstance(name, str):
                    raise UartMcpError("tools/call requires string param 'name'")
                if not isinstance(arguments, dict):
                    raise UartMcpError("tools/call requires object param 'arguments'")
                result = handle_tool_call(client, name, arguments, args.default_timeout, args.default_newline)
                write_message(sys.stdout, make_success_response(message_id, result))
                continue

            write_message(sys.stdout, make_error_response(message_id, -32601, f"Method not found: {method}"))
        except (UartMcpError, OSError, json.JSONDecodeError, socket.timeout) as exc:
            if message_id is None:
                continue
            write_message(sys.stdout, make_error_response(message_id, -32000, str(exc)))


def main() -> int:
    args = build_parser().parse_args()
    return serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
