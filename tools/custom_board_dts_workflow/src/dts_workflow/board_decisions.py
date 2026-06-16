from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .pinmux_db import normalize_name


@dataclass
class BoardDecisions:
    raw: dict[str, Any]
    mux_by_key: dict[tuple[str, str, str], dict[str, Any]]
    controller_by_node: dict[str, dict[str, Any]]
    external_by_bus: dict[str, list[dict[str, Any]]]


def load_board_decisions(path: Path) -> BoardDecisions:
    if not path.exists():
        return BoardDecisions(raw={}, mux_by_key={}, controller_by_node={}, external_by_bus={})

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        return BoardDecisions(raw={}, mux_by_key={}, controller_by_node={}, external_by_bus={})

    mux_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in data.get("mux_decisions", []) or []:
        if not isinstance(item, dict):
            continue
        soc_ref = str(item.get("soc_ref", "")).upper()
        ball = str(item.get("ball", "")).upper()
        symbol_pin = normalize_name(item.get("symbol_pin_name", ""))
        if soc_ref and ball and symbol_pin:
            mux_by_key[(soc_ref, ball, symbol_pin)] = item

    controller_by_node: dict[str, dict[str, Any]] = {}
    for item in data.get("controller_decisions", []) or []:
        if not isinstance(item, dict):
            continue
        node = str(item.get("dts_node", "")).strip()
        controller = str(item.get("controller", "")).strip()
        if node:
            controller_by_node[node.lstrip("&")] = item
        elif controller:
            controller_by_node[controller] = item

    external_by_bus: dict[str, list[dict[str, Any]]] = {}
    for item in data.get("external_device_decisions", []) or []:
        if not isinstance(item, dict):
            continue
        keys: set[str] = set()
        bus = str(item.get("bus", "")).strip().upper()
        parent = str(item.get("dts_parent", "")).strip().upper().lstrip("&")
        if bus:
            keys.add(bus)
        if parent:
            keys.add(parent)
        if not keys:
            continue
        for key in keys:
            external_by_bus.setdefault(key, []).append(item)

    return BoardDecisions(
        raw=data,
        mux_by_key=mux_by_key,
        controller_by_node=controller_by_node,
        external_by_bus=external_by_bus,
    )
