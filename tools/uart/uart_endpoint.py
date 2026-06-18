#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2] if len(Path(__file__).resolve().parents) >= 3 else Path.cwd()
DEFAULT_SOCKET_PATH = REPO_ROOT / "logs" / "uartd.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 17001
DEFAULT_TCP = f"{DEFAULT_TCP_HOST}:{DEFAULT_TCP_PORT}"
DEFAULT_TARGETS_FILE = Path(os.environ.get("UART_TARGETS_FILE", Path(__file__).with_name("targets.json")))


class EndpointConfigError(Exception):
    pass


@dataclass(frozen=True)
class Endpoint:
    kind: str  # "unix" or "tcp"
    socket_path: Path | None = None
    host: str | None = None
    port: int | None = None
    target: str | None = None

    @property
    def description(self) -> str:
        if self.kind == "tcp":
            return f"tcp://{self.host}:{self.port}"
        return f"unix://{self.socket_path}"


def parse_tcp_endpoint(value: str) -> tuple[str, int]:
    text = value.strip()
    if text.startswith("tcp://"):
        text = text[len("tcp://") :]
    if ":" not in text:
        raise EndpointConfigError("TCP endpoint must be HOST:PORT")
    host, port_text = text.rsplit(":", 1)
    if not host:
        host = DEFAULT_TCP_HOST
    try:
        port = int(port_text)
    except ValueError as exc:
        raise EndpointConfigError("TCP port must be an integer") from exc
    if not (1 <= port <= 65535):
        raise EndpointConfigError("TCP port must be in 1..65535")
    return host, port


def default_target_name(targets_file: Path | None = None) -> str:
    return os.environ.get("UART_TARGET") or load_targets(targets_file).get("default_target", "sk")


def available_targets(targets_file: Path | None = None) -> list[str]:
    return sorted(load_targets(targets_file).get("targets", {}).keys())


def load_targets(targets_file: Path | None = None) -> dict[str, Any]:
    path = Path(targets_file) if targets_file is not None else DEFAULT_TARGETS_FILE
    if not path.exists():
        return {
            "default_target": "sk",
            "targets": {
                "sk": {
                    "transport": "tcp",
                    "tcp": DEFAULT_TCP,
                    "socket": str(DEFAULT_SOCKET_PATH),
                    "description": "Local SK-AM64B uartd",
                }
            },
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EndpointConfigError(f"Failed to load UART targets file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EndpointConfigError(f"UART targets file {path} must contain a JSON object")
    data.setdefault("default_target", "sk")
    data.setdefault("targets", {})
    if not isinstance(data["targets"], dict):
        raise EndpointConfigError(f"UART targets file {path} field 'targets' must be an object")
    data["_path"] = path
    return data


def resolve_target_endpoint(target: str, targets_file: Path | None = None) -> Endpoint:
    data = load_targets(targets_file)
    targets = data.get("targets", {})
    raw = targets.get(target)
    if not isinstance(raw, dict):
        names = ", ".join(sorted(targets.keys())) or "none"
        raise EndpointConfigError(f"Unknown UART target '{target}'. Available targets: {names}")

    transport = str(raw.get("transport", "tcp")).strip().lower()
    base_path = Path(data.get("_path", DEFAULT_TARGETS_FILE)).parent

    if transport == "tcp":
        tcp_value = raw.get("tcp", DEFAULT_TCP)
        if not isinstance(tcp_value, str):
            raise EndpointConfigError(f"UART target '{target}' field 'tcp' must be a string")
        host, port = parse_tcp_endpoint(tcp_value)
        return Endpoint(kind="tcp", host=host, port=port, target=target)

    if transport == "unix":
        socket_value = raw.get("socket", str(DEFAULT_SOCKET_PATH))
        if not isinstance(socket_value, str):
            raise EndpointConfigError(f"UART target '{target}' field 'socket' must be a string")
        socket_path = Path(socket_value)
        if not socket_path.is_absolute():
            socket_path = (base_path / socket_path).resolve()
        return Endpoint(kind="unix", socket_path=socket_path, target=target)

    raise EndpointConfigError(f"UART target '{target}' transport must be 'tcp' or 'unix'")


def endpoint_from_options(
    *,
    tcp: str | None = None,
    socket_path: str | Path | None = None,
    target: str | None = None,
    targets_file: str | Path | None = None,
) -> Endpoint:
    if tcp:
        host, port = parse_tcp_endpoint(tcp)
        return Endpoint(kind="tcp", host=host, port=port)

    if socket_path:
        return Endpoint(kind="unix", socket_path=Path(socket_path))

    target_name = target or default_target_name(Path(targets_file) if targets_file is not None else None)
    return resolve_target_endpoint(target_name, Path(targets_file) if targets_file is not None else None)
