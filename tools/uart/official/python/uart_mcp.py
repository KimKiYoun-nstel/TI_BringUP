"""Optional MCP stdio bridge. Configure UARTD_ENDPOINT and UARTD_TOKEN_FILE."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from uart_api import request, require_ok

mcp = FastMCP("uartd")


def call(payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    endpoint = os.environ.get("UARTD_ENDPOINT", "127.0.0.1:17001")
    token_file = os.environ.get("UARTD_TOKEN_FILE", "")
    token = (Path(token_file).read_text(encoding="utf-8-sig").strip()
             if token_file else os.environ.get("UARTD_TOKEN", "").strip())
    return require_ok(request(endpoint, payload, token=token, timeout=timeout))


@mcp.tool()
def uart_status() -> dict[str, Any]:
    """Get daemon, serial connection and attached client status."""
    return call({"action": "status"})


@mcp.tool()
def uart_list_ports() -> dict[str, Any]:
    """List serial ports on the daemon host."""
    return call({"action": "list_ports"})


@mcp.tool()
def uart_set_port(port: str, baud: int = 115200, force: bool = False) -> dict[str, Any]:
    """Connect/switch UART for all clients. Force permits switching with RW clients."""
    return call({"action": "set_port", "port": port, "baud": baud, "force": force})


@mcp.tool()
def uart_disconnect(force: bool = False) -> dict[str, Any]:
    """Close UART for all clients, keeping the daemon alive."""
    return call({"action": "disconnect_port", "force": force})


@mcp.tool()
def uart_baud(baud: int) -> dict[str, Any]:
    """Change UART baudrate for all clients."""
    return call({"action": "baud", "baud": baud})


@mcp.tool()
def uart_send(text: str, newline: bool = False) -> dict[str, Any]:
    """Write text to UART; newline=True appends LF."""
    return call({"action": "send", "text": text, "newline": newline})


@mcp.tool()
def uart_command(text: str, expect: str, timeout: float = 10.0,
                 newline: bool = True) -> dict[str, Any]:
    """Send text then wait for a literal substring in fresh UART output (0..120s)."""
    if not 0 <= timeout <= 120:
        raise ValueError("timeout must be between 0 and 120 seconds")
    return call({"action": "send_expect", "text": text, "expect": expect,
                 "timeout": timeout, "newline": newline}, timeout=timeout + 5)


@mcp.tool()
def uart_tail(lines: int = 80) -> dict[str, Any]:
    """Read a snapshot of recent UART receive logs (1..1000 lines)."""
    if not 1 <= lines <= 1000:
        raise ValueError("lines must be between 1 and 1000")
    return call({"action": "tail_once", "lines": lines})


if __name__ == "__main__":
    mcp.run(transport="stdio")
