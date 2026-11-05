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

if __package__:
    from .endpoint import (DEFAULT_TARGETS_FILE, Endpoint, EndpointConfigError,
                                available_targets, default_target_name,
                                endpoint_from_options, resolve_token)
    from .distribution import uart_api
else:
    from endpoint import (DEFAULT_TARGETS_FILE, Endpoint, EndpointConfigError,
                               available_targets, default_target_name,
                               endpoint_from_options, resolve_token)
    from distribution import uart_api


JsonSocketReader = uart_api.JsonSocketReader
UARTAPIError = uart_api.UARTAPIError
api_request = uart_api.request

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMEOUT = float(os.environ.get("UART_MCP_DEFAULT_TIMEOUT", "10"))
DEFAULT_NEWLINE = os.environ.get("UART_MCP_DEFAULT_NEWLINE", "crlf")
PROTOCOL_VERSION = "2024-11-05"


class UartMcpError(Exception):
    pass


@dataclass
class UartdClient:
    endpoint: Endpoint
    token_file: str | None = None

    def request(self, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT + 6
        token = resolve_token(self.endpoint, self.token_file)
        if self.endpoint.kind == "tcp":
            return api_request(self.endpoint.description, payload, token=token,
                               timeout=effective_timeout)

        # The official API is TCP-only; retain the local Unix socket adapter.
        payload = dict(payload)
        if token:
            payload["token"] = token
        with self._connect(effective_timeout) as sock:
            sock.settimeout(effective_timeout)
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            response = self._recv_json(sock)
        return response

    def _connect(self, timeout: float) -> socket.socket:
        if not hasattr(socket, "AF_UNIX"):
            raise UartMcpError("Unix socket transport is not available on this platform. Use TCP target profiles instead.")
        assert self.endpoint.socket_path is not None
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            sock.connect(str(self.endpoint.socket_path))
        except OSError:
            sock.close()
            raise
        return sock

    def _recv_json(self, sock: socket.socket) -> dict[str, Any]:
        return JsonSocketReader(sock).recv_json()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UART MCP stdio adapter")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--socket", default=None)
    transport.add_argument("--tcp", default=None)
    parser.add_argument("--target", default=None, help="Named UART target from tools/uart/config/targets.json")
    parser.add_argument("--targets-file", default=str(DEFAULT_TARGETS_FILE), help="UART target profile JSON path")
    parser.add_argument("--default-timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--default-newline", default=DEFAULT_NEWLINE)
    parser.add_argument("--token-file", default=None, help="Override target authentication token file")
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


def target_input_schema(default_target: str, targets: list[str]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "string",
        "description": f"UART target name. Default: {default_target}.",
        "default": default_target,
    }
    if targets:
        schema["enum"] = targets
    return schema


def tool_definitions(default_target: str, targets: list[str]) -> list[dict[str, Any]]:
    target_schema = target_input_schema(default_target, targets)
    return [
        {
            "name": "uart_send",
            "description": "Send text without waiting. No newline by default; supports raw control characters.",
            "inputSchema": {"type": "object", "properties": {
                "target": target_schema, "text": {"type": "string"},
                "newline": {"enum": [False, True, "lf", "crlf", "cr", "none"], "default": False},
            }, "required": ["text"]},
        },
        {
            "name": "uart_list_ports",
            "description": "List serial ports on the remote daemon host. Read-only.",
            "inputSchema": {"type": "object", "properties": {"target": target_schema}},
        },
        {
            "name": "uart_set_port",
            "description": "Connect or switch the daemon UART without restarting TCP. Affects all clients; force permits switching with RW attach clients.",
            "inputSchema": {"type": "object", "properties": {
                "target": target_schema, "port": {"type": "string"},
                "baud": {"type": "integer", "minimum": 1},
                "force": {"type": "boolean", "default": False},
            }, "required": ["port"]},
        },
        {
            "name": "uart_disconnect",
            "description": "Disconnect UART while keeping the daemon and TCP connections alive. Affects all clients.",
            "inputSchema": {"type": "object", "properties": {
                "target": target_schema, "force": {"type": "boolean", "default": False},
            }},
        },
        {
            "name": "uart_baud",
            "description": "Change the daemon UART baud rate for all clients.",
            "inputSchema": {"type": "object", "properties": {
                "target": target_schema, "baud": {"type": "integer", "minimum": 1},
            }, "required": ["baud"]},
        },
        {
            "name": "uart_status",
            "description": "Check the persistent UART daemon status, including serial port, baudrate, active clients, current RX offset, and recent writer metadata. Use this before interacting with a real board over UART.",
            "inputSchema": {"type": "object", "properties": {"target": target_schema}},
        },
        {
            "name": "uart_tail",
            "description": "Read recent UART console output from the daemon buffer or runtime log. Use this first when you need to understand whether the board is in U-Boot, Linux login, Linux shell, booting, or an unknown state. This is read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": target_schema,
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
                    "target": target_schema,
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
                    "target": target_schema,
                    "pattern": {"type": "string"},
                    "timeout": {"type": "number", "default": DEFAULT_TIMEOUT},
                    "from": {"type": "string", "enum": ["now", "fresh", "buffer"], "default": "now"},
                    "from_offset": {"type": "integer", "minimum": 0},
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
                    "target": target_schema,
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
            "description": "From a Linux shell or login prompt, reboot the board and stop at the U-Boot prompt using a single managed flow over the persistent UART daemon. Use this when you need reliable self-reboot to U-Boot entry without manually chaining separate send/expect steps.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": target_schema,
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
        f"uartd target={data.get('target')} endpoint={data.get('endpoint')} port={data.get('port')} baud={data.get('baud')} clients={data.get('clients')} "
        f"serial_state={data.get('serial_state')} generation={data.get('session_generation')} "
        f"attach_clients={data.get('attach_clients', data.get('attached_clients', 0))} offset={data.get('offset')} "
        f"error={data.get('error', data.get('last_serial_error'))}"
    )


def normalize_tail(data: dict[str, Any]) -> dict[str, Any]:
    text = data.get("text", "")
    return {
        "ok": data.get("ok", False),
        "error": data.get("error"),
        "target": data.get("target"),
        "endpoint": data.get("endpoint"),
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
            "target": data.get("target"),
            "endpoint": data.get("endpoint"),
            "pattern": data.get("pattern", data.get("expect", data.get("matched"))),
            "output": data.get("output", ""),
            "start_offset": data.get("start_offset"),
            "end_offset": data.get("end_offset", data.get("offset")),
            "elapsed_ms": elapsed_ms,
        }
    return {
        "ok": False,
        "target": data.get("target"),
        "endpoint": data.get("endpoint"),
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
            "target": data.get("target"),
            "endpoint": data.get("endpoint"),
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
        "target": data.get("target"),
        "endpoint": data.get("endpoint"),
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
        "target": data.get("target"),
        "endpoint": data.get("endpoint"),
        "state_before": data.get("state_before"),
        "steps": data.get("steps", []),
        "final_prompt": data.get("final_prompt"),
        "elapsed_ms": elapsed_ms,
    }


def attach_endpoint_metadata(payload: dict[str, Any], endpoint: Endpoint) -> dict[str, Any]:
    data = dict(payload)
    data.setdefault("target", endpoint.target)
    data.setdefault("endpoint", endpoint.description)
    return data


def client_from_request(args: argparse.Namespace, arguments: dict[str, Any]) -> UartdClient:
    target = arguments.get("target")
    if target is not None and not isinstance(target, str):
        raise UartMcpError("tool field 'target' must be a string")
    if target and (args.socket or args.tcp):
        raise UartMcpError("MCP server is pinned to an explicit endpoint; per-call target override is unavailable")
    try:
        endpoint = endpoint_from_options(
            tcp=args.tcp,
            socket_path=args.socket,
            target=target or args.target,
            targets_file=args.targets_file,
        )
    except EndpointConfigError as exc:
        raise UartMcpError(str(exc)) from exc
    return UartdClient(endpoint=endpoint, token_file=getattr(args, "token_file", None))


def handle_tool_call(args: argparse.Namespace, name: str, arguments: dict[str, Any], default_timeout: float, default_newline: str) -> dict[str, Any]:
    start = time.monotonic()
    client = client_from_request(args, arguments)

    management_actions = {
        "uart_list_ports": "list_ports", "uart_set_port": "set_port",
        "uart_disconnect": "disconnect_port", "uart_baud": "baud",
    }
    if name in management_actions:
        payload: dict[str, Any] = {"action": management_actions[name]}
        if name == "uart_set_port":
            port = arguments.get("port")
            if not isinstance(port, str) or not port.strip():
                raise UartMcpError("uart_set_port requires a non-empty port")
            payload["port"] = port
        if name == "uart_baud" or "baud" in arguments:
            baud = arguments.get("baud")
            if isinstance(baud, bool) or not isinstance(baud, int) or baud <= 0:
                raise UartMcpError("baud must be a positive integer")
            payload["baud"] = baud
        if name in {"uart_set_port", "uart_disconnect"}:
            force = arguments.get("force", False)
            if not isinstance(force, bool):
                raise UartMcpError("force must be boolean")
            payload["force"] = force
        raw = attach_endpoint_metadata(client.request(payload, timeout=default_timeout + 6), client.endpoint)
        return make_tool_result(raw, json.dumps(raw, ensure_ascii=False), is_error=not raw.get("ok"))

    if name == "uart_status":
        raw = attach_endpoint_metadata(client.request({"action": "status"}, timeout=default_timeout + 6), client.endpoint)
        return make_tool_result(raw, summarize_status(raw), is_error=not raw.get("ok"))

    if name == "uart_tail":
        lines = int(arguments.get("lines", 120))
        raw = attach_endpoint_metadata(client.request({"action": "tail_once", "lines": lines}, timeout=default_timeout + 6), client.endpoint)
        normalized = normalize_tail(raw)
        return make_tool_result(normalized, normalized.get("text") or normalized.get("error") or "", is_error=not normalized.get("ok"))

    if name in {"uart_send", "uart_sendline"}:
        field = "text" if name == "uart_send" else "line"
        line = arguments.get(field)
        if not isinstance(line, str):
            raise UartMcpError(f"{name} requires string field '{field}'")
        newline = arguments.get("newline", False if name == "uart_send" else default_newline)
        if newline not in (False, True, "lf", "crlf", "cr", "none"):
            raise UartMcpError("unsupported newline")
        raw = attach_endpoint_metadata(client.request({"action": "send", "text": line, "newline": newline}, timeout=default_timeout + 6), client.endpoint)
        return make_tool_result(raw, f"sent {raw.get('sent', '')!r}" if raw.get("ok") else raw.get("error", "send failed"), is_error=not raw.get("ok"))

    if name == "uart_expect":
        pattern = arguments.get("pattern")
        if not isinstance(pattern, str):
            raise UartMcpError("uart_expect requires string field 'pattern'")
        timeout = float(arguments.get("timeout", default_timeout))
        from_mode = arguments.get("from", "now")
        payload = {"action": "expect", "pattern": pattern, "timeout": timeout, "from": from_mode}
        if "from_offset" in arguments:
            payload["from_offset"] = arguments["from_offset"]
        raw = attach_endpoint_metadata(client.request(payload, timeout=timeout + 6), client.endpoint)
        normalized = normalize_expect(raw, int((time.monotonic() - start) * 1000))
        return make_tool_result(normalized, normalized.get("output", normalized.get("error", "")), is_error=not normalized.get("ok"))

    if name == "uart_command":
        line = arguments.get("line")
        expect = arguments.get("expect")
        if not isinstance(line, str) or not isinstance(expect, str):
            raise UartMcpError("uart_command requires string fields 'line' and 'expect'")
        timeout = float(arguments.get("timeout", default_timeout))
        newline = arguments.get("newline", default_newline)
        raw = attach_endpoint_metadata(client.request(
            {"action": "send_expect", "text": line, "expect": expect, "timeout": timeout, "newline": newline},
            timeout=timeout + 6,
        ), client.endpoint)
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

        tail = normalize_tail(attach_endpoint_metadata(client.request({"action": "tail_once", "lines": 40}, timeout=default_timeout + 6), client.endpoint))
        state_before = tail.get("state_hint", "unknown")
        steps: list[dict[str, Any]] = []

        if state_before == "password_prompt":
            raw = attach_endpoint_metadata(client.request({"action": "send_expect", "text": "", "expect": login_prompt, "timeout": shell_timeout, "newline": newline, "from": "fresh"}, timeout=shell_timeout + 6), client.endpoint)
            steps.append({"name": "password_to_login", **normalize_command(raw, int((time.monotonic() - start) * 1000))})
            state_before = "linux_login"

        if state_before == "linux_login":
            raw = attach_endpoint_metadata(client.request({"action": "send_expect", "text": login_user, "expect": shell_prompt, "timeout": shell_timeout, "newline": newline, "from": "fresh"}, timeout=shell_timeout + 6), client.endpoint)
            normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
            steps.append({"name": "login_to_shell", **normalized})
            if not normalized.get("ok"):
                result = normalize_reboot_flow({"ok": False, "state_before": state_before, "steps": steps, "final_prompt": None}, int((time.monotonic() - start) * 1000))
                return make_tool_result(result, normalized.get("output_since_command", normalized.get("error", "")), is_error=True)
            state_before = "linux_root"

        if state_before != "linux_root":
            raise UartMcpError(f"uart_reboot_to_uboot requires Linux shell/login state, got '{state_before}'")

        raw = attach_endpoint_metadata(client.request({"action": "send_expect", "text": reboot_command, "expect": autoboot_prompt, "timeout": reboot_timeout, "newline": newline, "from": "fresh"}, timeout=reboot_timeout + 6), client.endpoint)
        normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
        steps.append({"name": "reboot_to_autoboot", **normalized})
        if not normalized.get("ok"):
            result = normalize_reboot_flow({"ok": False, "state_before": state_before, "steps": steps, "final_prompt": None}, int((time.monotonic() - start) * 1000))
            return make_tool_result(result, normalized.get("output_since_command", normalized.get("error", "")), is_error=True)

        raw = attach_endpoint_metadata(client.request({"action": "send_expect", "text": "", "expect": uboot_prompt, "timeout": uboot_timeout, "newline": newline, "from": "fresh"}, timeout=uboot_timeout + 6), client.endpoint)
        normalized = normalize_command(raw, int((time.monotonic() - start) * 1000))
        steps.append({"name": "interrupt_to_uboot", **normalized})

        result = normalize_reboot_flow({"ok": normalized.get("ok", False), "target": client.endpoint.target, "endpoint": client.endpoint.description, "state_before": "linux_root", "steps": steps, "final_prompt": uboot_prompt if normalized.get("ok") else None}, int((time.monotonic() - start) * 1000))
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
    known_targets = available_targets(Path(args.targets_file))
    default_target = args.target or default_target_name(Path(args.targets_file))

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
                write_message(sys.stdout, make_success_response(message_id, {"tools": tool_definitions(default_target, known_targets)}))
                continue

            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not isinstance(name, str):
                    raise UartMcpError("tools/call requires string param 'name'")
                if not isinstance(arguments, dict):
                    raise UartMcpError("tools/call requires object param 'arguments'")
                result = handle_tool_call(args, name, arguments, args.default_timeout, args.default_newline)
                write_message(sys.stdout, make_success_response(message_id, result))
                continue

            write_message(sys.stdout, make_error_response(message_id, -32601, f"Method not found: {method}"))
        except (EndpointConfigError, UARTAPIError, UartMcpError, OSError, ValueError) as exc:
            if message_id is None:
                continue
            write_message(sys.stdout, make_error_response(message_id, -32000, str(exc)))


def main() -> int:
    args = build_parser().parse_args()
    return serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
