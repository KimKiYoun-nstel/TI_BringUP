from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PartRecord:
    designator: str
    footprint: str
    parttype: str
    description: str
    fields: dict[str, str]


@dataclass
class NetNode:
    refdes: str
    pin: str
    pin_name: str
    electrical_type: str
    raw: str


@dataclass
class NetRecord:
    name: str
    nodes: list[NetNode]


@dataclass
class SocPinRecord:
    ball: str
    soc_refdes: str
    soc_part: str
    soc_pin_name: str
    raw_soc_pin_name: str
    net_name: str
    connected_nodes: str
    component_refs: str
    connected_pin_names: str
    connection_count: int
    source_line: str


@dataclass
class NetlistData:
    parts: dict[str, PartRecord]
    nets: list[NetRecord]
    soc_pins: list[SocPinRecord]


def _normalize_soc_signal(raw_name: str, soc_name: str) -> str:
    text = raw_name.strip()
    prefix = f"{soc_name}-"
    if text.startswith(prefix):
        return text[len(prefix) :]
    if "-" in text:
        return text.split("-", 1)[1]
    return text


def _parse_part_block(block_lines: list[str]) -> PartRecord:
    fields: dict[str, str] = {}
    index = 0
    while index + 1 < len(block_lines):
        key = block_lines[index].strip()
        value = block_lines[index + 1].strip()
        fields[key] = value
        index += 2

    return PartRecord(
        designator=fields.get("DESIGNATOR", ""),
        footprint=fields.get("FOOTPRINT", ""),
        parttype=fields.get("PARTTYPE", ""),
        description=fields.get("DESCRIPTION", ""),
        fields=fields,
    )


def _parse_net_node(line: str) -> NetNode | None:
    parts = line.split()
    if len(parts) < 3 or "-" not in parts[0]:
        return None

    refdes, pin = parts[0].split("-", 1)
    pin_name = parts[1]
    electrical_type = " ".join(parts[2:])
    return NetNode(refdes=refdes, pin=pin, pin_name=pin_name, electrical_type=electrical_type, raw=line)


def parse_protel_netlist(netlist_path: Path, soc_refdes: str, soc_name: str) -> NetlistData:
    lines = netlist_path.read_text(errors="replace").splitlines()

    parts: dict[str, PartRecord] = {}
    nets: list[NetRecord] = []
    soc_pins: list[SocPinRecord] = []

    index = 0
    while index < len(lines):
        line = lines[index].strip()

        if line == "[":
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "]":
                block.append(lines[index])
                index += 1
            part = _parse_part_block(block)
            if part.designator:
                parts[part.designator] = part

        elif line == "(":
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != ")":
                block.append(lines[index].strip())
                index += 1

            if block:
                net_name = block[0]
                nodes = [node for node in (_parse_net_node(entry) for entry in block[1:]) if node]
                net = NetRecord(name=net_name, nodes=nodes)
                nets.append(net)

                for node in nodes:
                    if node.refdes != soc_refdes:
                        continue

                    other_nodes = [other for other in nodes if other.refdes != soc_refdes]
                    connected_nodes = "; ".join(
                        f"{other.refdes}-{other.pin}:{other.pin_name}" for other in other_nodes
                    )
                    component_refs = "; ".join(sorted({other.refdes for other in other_nodes}))
                    connected_pin_names = "; ".join(sorted({other.pin_name for other in other_nodes if other.pin_name}))
                    soc_part_record = parts.get(soc_refdes)
                    soc_part = soc_part_record.parttype if soc_part_record else soc_name
                    soc_pins.append(
                        SocPinRecord(
                            ball=node.pin,
                            soc_refdes=soc_refdes,
                            soc_part=soc_part,
                            soc_pin_name=_normalize_soc_signal(node.pin_name, soc_name),
                            raw_soc_pin_name=node.pin_name,
                            net_name=net_name,
                            connected_nodes=connected_nodes,
                            component_refs=component_refs,
                            connected_pin_names=connected_pin_names,
                            connection_count=len(other_nodes),
                            source_line=node.raw,
                        )
                    )

        index += 1

    soc_pins.sort(key=lambda row: (row.ball, row.soc_pin_name, row.net_name))
    return NetlistData(parts=parts, nets=nets, soc_pins=soc_pins)
