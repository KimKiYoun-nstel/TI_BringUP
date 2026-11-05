"""uartd TCP JSON client shared by GUI and integrations.

Transport: one UTF-8 JSON object per LF line; attach response is followed by raw bytes.
Credentials are passed per request and must not be persisted by this module.
"""
from __future__ import annotations

import json
import socket
from typing import Any

MAX_RESPONSE_BYTES = 1024 * 1024


class UARTAPIError(Exception):
    """Remote uartd reported an error or the protocol was invalid."""


def parse_endpoint(endpoint: str) -> tuple[str, int]:
    raw = endpoint.removeprefix("tcp://").strip()
    if raw.count(":") != 1:
        raise UARTAPIError("TCP endpoint must be HOST:PORT (IPv4 or hostname)")
    host, port_text = raw.rsplit(":", 1)
    if not host:
        raise UARTAPIError("TCP host cannot be empty")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise UARTAPIError("TCP port must be integer") from exc
    if not 1 <= port <= 65535:
        raise UARTAPIError("TCP port must be between 1 and 65535")
    return host, port


class JsonSocketReader:
    """Preserve bytes after a JSON line for tail/attach streaming protocols."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.remaining = bytearray()

    def recv_json(self) -> dict[str, Any]:
        while b"\n" not in self.remaining:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise UARTAPIError("uartd closed the connection")
            self.remaining.extend(chunk)
            if len(self.remaining) > MAX_RESPONSE_BYTES:
                raise UARTAPIError("JSON response is too large")
        raw, _, remainder = self.remaining.partition(b"\n")
        self.remaining = bytearray(remainder)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UARTAPIError(f"invalid JSON response: {exc}") from exc
        if not isinstance(obj, dict):
            raise UARTAPIError("JSON response must be an object")
        return obj

    def take_remaining(self) -> bytes:
        data = bytes(self.remaining)
        self.remaining.clear()
        return data


def request(endpoint: str, payload: dict[str, Any], token: str = "", timeout: float = 3.0) -> dict[str, Any]:
    """Send one JSON command to uartd over TCP, returning the reply object."""
    host, port = parse_endpoint(endpoint)
    body = payload.copy()
    if token:
        body["token"] = token
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8"))
            return JsonSocketReader(sock).recv_json()
    except (OSError, TimeoutError) as exc:
        raise UARTAPIError(f"Cannot communicate with {endpoint}: {exc}") from exc


def require_ok(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("ok") is not True:
        raise UARTAPIError(str(response.get("error", "uartd request failed")))
    return response
