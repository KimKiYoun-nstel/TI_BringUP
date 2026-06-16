from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .board_decisions import BoardDecisions
from .config import WorkflowConfig
from .netlist_parser import NetNode, NetlistData
from .pinmux_lookup import LookupResult
from .board_reference import BoardReference
from .soc_reference import SocReference


def _slug(value: str) -> str:
    return value.lower().replace("_", "-")


def _offset_sort_key(value: str) -> tuple[int, str]:
    text = (value or "").strip().lower()
    if text.startswith("0x"):
        return (0, f"{int(text, 16):08x}")
    return (1, text)


def _signal_suffix(signal_name: str) -> str:
    parts = signal_name.split("_")
    return parts[-1] if parts else signal_name


def _interface_category(interface_key: str) -> str:
    if not interface_key:
        return "unknown"
    if interface_key.startswith("DDR"):
        return "ddr"
    if interface_key.startswith("USB"):
        return "usb"
    if interface_key.startswith("SERDES"):
        return "serdes"
    if interface_key.startswith("MCU_OSC") or interface_key.endswith("_OSC0"):
        return "clock"
    if interface_key.startswith("GPMC"):
        return "gpmc"
    if interface_key.startswith("PRU_ICSSG"):
        return "pru"
    if interface_key.endswith("DEBUG0"):
        return "debug"
    if interface_key.endswith("SYSTEM0"):
        return "system"
    if "UART" in interface_key:
        return "uart"
    if "I2C" in interface_key:
        return "i2c"
    if re.match(r"^(MCU_)?SPI\d+$", interface_key):
        return "spi"
    if interface_key.startswith("OSPI"):
        return "ospi"
    if interface_key.startswith("MMC"):
        return "mmc"
    if interface_key.startswith("MCAN"):
        return "mcan"
    if interface_key.startswith("MDIO"):
        return "mdio"
    if interface_key.startswith("RGMII") or interface_key.startswith("RMII"):
        return "ethernet"
    return "unknown"


def _default_interface_mapping(interface_key: str) -> dict[str, Any] | None:
    category = _interface_category(interface_key)
    lower = interface_key.lower()
    is_mcu = interface_key.startswith("MCU_")
    domain = "MCU_WKUP" if is_mcu else "MAIN"

    if category == "uart":
        return {
            "node": lower if is_mcu else f"main_{lower}",
            "pinctrl_label": f"{lower}_pins_default" if is_mcu else f"main_{lower}_pins_default",
            "domain": domain,
            "required_signals": [f"{interface_key}_RXD", f"{interface_key}_TXD"],
        }
    if category == "i2c":
        return {
            "node": lower if is_mcu else f"main_{lower}",
            "pinctrl_label": f"{lower}_pins_default" if is_mcu else f"main_{lower}_pins_default",
            "domain": domain,
            "required_signals": [f"{interface_key}_SCL", f"{interface_key}_SDA"],
        }
    if category == "spi":
        return {
            "node": lower if is_mcu else f"main_{lower}",
            "pinctrl_label": f"{lower}_pins_default" if is_mcu else f"main_{lower}_pins_default",
            "domain": domain,
        }
    if category == "mcan":
        return {
            "node": f"main_{lower}",
            "pinctrl_label": f"main_{lower}_pins_default",
            "domain": "MAIN",
            "required_signals": [f"{interface_key}_RX", f"{interface_key}_TX"],
        }
    if category == "mmc":
        index = re.search(r"(\d+)$", interface_key)
        if not index:
            return None
        value = index.group(1)
        return {
            "node": f"sdhci{value}",
            "pinctrl_label": f"main_mmc{value}_pins_default",
            "domain": "MAIN",
        }
    if category == "ospi":
        index = re.search(r"(\d+)$", interface_key)
        suffix = index.group(1) if index else "0"
        return {
            "node": f"ospi{suffix}",
            "pinctrl_label": f"ospi{suffix}_pins_default",
            "domain": "MAIN",
        }
    if category == "mdio":
        return {
            "node": "cpsw3g_mdio",
            "pinctrl_label": "mdio0_pins_default",
            "domain": "MAIN",
        }
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _build_interface_mapping(config: WorkflowConfig) -> dict[str, dict[str, Any]]:
    mapping = _load_yaml(config.platform_config_dir / "peripheral_node_map.yaml")
    normalized = {key.upper(): value for key, value in mapping.items()}
    return normalized


def _build_part_compatible_map(config: WorkflowConfig) -> dict[str, dict[str, Any]]:
    mapping = _load_yaml(config.platform_config_dir / "part_compatible_map.yaml")
    return {key.upper(): value for key, value in mapping.items()}


def _workflow_section(config: WorkflowConfig, name: str) -> dict[str, Any]:
    section = config.workflow_defaults.get(name, {})
    return section if isinstance(section, dict) else {}


def _base_defaults(config: WorkflowConfig) -> dict[str, Any]:
    return _workflow_section(config, "base_defaults")


def _linux_base(config: WorkflowConfig) -> dict[str, Any]:
    return _workflow_section(config, "linux_base")


def _controller_enabled(config: WorkflowConfig, category: str) -> bool:
    mapping = {
        "uart": "enable_detected_uart",
        "i2c": "enable_detected_i2c",
        "spi": "enable_detected_spi",
        "mcan": "enable_detected_mcan",
        "mmc": "enable_detected_mmc",
        "ospi": "enable_detected_ospi",
        "ethernet": "enable_detected_ethernet_stub",
    }
    key = mapping.get(category)
    if not key:
        return True
    return bool(_base_defaults(config).get("controller_enable", {}).get(key, True))


def _relative_include(base_file: Path, target_file: Path) -> str:
    return os.path.relpath(target_file, start=base_file.parent)


def _alias_preference(config: WorkflowConfig) -> dict[str, str]:
    data = _base_defaults(config).get("alias_preference", {})
    return data if isinstance(data, dict) else {}


def _stdout_preference(config: WorkflowConfig) -> list[str]:
    value = _base_defaults(config).get("stdout_preference", [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _uboot_stdout_preference(config: WorkflowConfig) -> list[str]:
    value = _base_defaults(config).get("uboot_stdout_preference", _stdout_preference(config))
    return [str(item) for item in value] if isinstance(value, list) else []


def _uboot_boot_media_preference(config: WorkflowConfig) -> list[str]:
    value = _base_defaults(config).get("uboot_boot_media_preference", ["MMC0", "MMC1", "OSPI0"])
    return [str(item) for item in value] if isinstance(value, list) else []


def _flag_for_signal(signal_name: str) -> tuple[str, bool]:
    signal = signal_name.upper()
    if signal.endswith("_SCL") or signal.endswith("_SDA"):
        return "PIN_INPUT_PULLUP", False
    if signal.endswith(("_RXD", "_RX", "_CTS", "_INT", "_IRQ", "_IRQN")) or signal.endswith("_IN"):
        return "PIN_INPUT", False
    if signal.endswith(("_TXD", "_TX", "_RTS", "_CMD", "_CLK", "_CS0", "_CS1", "_CSN0", "_CSN1", "_RESETN", "_RESET")):
        return "PIN_OUTPUT", False
    return "PIN_INPUT", True


def _group_results(results: list[LookupResult]) -> dict[str, list[LookupResult]]:
    grouped: dict[str, list[LookupResult]] = defaultdict(list)
    for result in results:
        if result.interface_key:
            grouped[result.interface_key].append(result)
    for key in grouped:
        grouped[key].sort(
            key=lambda item: (
                _offset_sort_key(item.db_row.get("dts_offset", "") if item.db_row else ""),
                item.soc_pin.ball,
                item.soc_pin.soc_pin_name,
            )
        )
    return dict(grouped)


def _interface_stats(results: list[LookupResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "pinctrl_facts": sum(result.classification == "PINMUX_DTS" for result in results),
        "controller_dts": sum(result.classification == "CONTROLLER_DTS" for result in results),
        "non_pinctrl_hw": sum(result.classification == "NON_PINCTRL_HW" for result in results),
        "pre_linux": sum(result.classification == "PRE_LINUX_CONFIG" for result in results),
        "gpio_candidate": sum(result.classification == "GPIO_CANDIDATE" for result in results),
        "alt_function_review": sum(result.classification == "ALT_FUNCTION_REVIEW" for result in results),
        "out_of_scope": sum(result.classification == "OUT_OF_SCOPE" for result in results),
        "unmatched_or_conflict": sum(
            result.classification == "UNMATCHED_OR_CONFLICT" or result.status == "CONFLICT"
            for result in results
        ),
        "valid_pin_count": sum(result.classification == "PINMUX_DTS" and result.has_valid_offset for result in results),
    }


def _is_pinctrl_fact(result: LookupResult) -> bool:
    return result.classification == "PINMUX_DTS" and result.db_row is not None and result.has_valid_offset


def _is_soc_symbol_functional(result: LookupResult) -> bool:
    return result.classification != "OUT_OF_SCOPE"


def _explicit_external_decisions(board_decisions: BoardDecisions, bus_name: str) -> list[dict[str, Any]]:
    return list(board_decisions.external_by_bus.get(bus_name.upper().lstrip("&"), []))


def _gpio_phandle_tuple(selected_function: str) -> tuple[str, int] | None:
    text = selected_function.upper()
    match = re.match(r"^(MCU_GPIO\d+)_(\d+)$", text)
    if match:
        return f"&{match.group(1).lower()}", int(match.group(2))
    match = re.match(r"^(GPIO\d+)_(\d+)$", text)
    if match:
        return f"&main_{match.group(1).lower()}", int(match.group(2))
    return None


def _build_controller_decision(
    config: WorkflowConfig,
    interface_key: str,
    results: list[LookupResult],
    interface_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
    board_reference: BoardReference,
    board_decisions: BoardDecisions,
) -> dict[str, Any]:
    mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key) or {}
    category = _interface_category(interface_key)
    ready, ready_reason = _controller_ready(interface_key, results)
    node = str(mapping.get("node", ""))
    pinctrl_label = str(mapping.get("pinctrl_label", f"{interface_key.lower()}_pins_default"))
    default_enabled = _controller_enabled(config, category)
    node_exists = bool(node) and soc_reference.has_label(node)
    has_valid_pins = any(_is_pinctrl_fact(result) for result in results)
    reference_has_pinctrl = board_reference.node_has_pinctrl(node) if node else None
    use_pinctrl = has_valid_pins and reference_has_pinctrl is not False
    emitted = bool(mapping) and default_enabled and node_exists
    explicit = board_decisions.controller_by_node.get(node)
    if explicit:
        enabled = explicit.get("enabled")
        if enabled is False:
            emitted = False
            default_enabled = False
        elif enabled is True:
            emitted = node_exists
            default_enabled = True

    notes: list[str] = []
    if not default_enabled:
        notes.append("disabled by workflow defaults")
    if not node_exists:
        notes.append("node label missing in SoC DTSI")
    if reference_has_pinctrl is False:
        notes.append("reference DTS uses node without pinctrl-0")
    elif not has_valid_pins:
        notes.append("no pinctrl facts available")
    if not ready:
        notes.append(f"incomplete signals: {ready_reason}")

    return {
        "interface_key": interface_key,
        "category": category,
        "node": node,
        "pinctrl_label": pinctrl_label,
        "mapping": mapping,
        "ready": ready,
        "ready_reason": ready_reason,
        "default_enabled": default_enabled,
        "node_exists": node_exists,
        "has_valid_pins": has_valid_pins,
        "reference_has_pinctrl": reference_has_pinctrl,
        "use_pinctrl": emitted and use_pinctrl,
        "emitted": emitted,
        "stats": _interface_stats(results),
        "notes": notes,
        "explicit": explicit,
    }


def _controller_decisions(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
    board_reference: BoardReference,
    board_decisions: BoardDecisions,
) -> list[dict[str, Any]]:
    decisions = [
        _build_controller_decision(
            config,
            interface_key,
            grouped[interface_key],
            interface_map,
            soc_reference,
            board_reference,
            board_decisions,
        )
        for interface_key in sorted(grouped)
    ]
    return decisions


def _controller_ready(interface_key: str, results: list[LookupResult]) -> tuple[bool, str]:
    signals = {
        result.db_row.get("signal_name", "").upper()
        for result in results
        if result.db_row and result.classification in {"PINMUX_DTS", "CONTROLLER_DTS"}
    }
    category = _interface_category(interface_key)

    if category == "uart":
        ready = any(name.endswith("_RXD") for name in signals) and any(name.endswith("_TXD") for name in signals)
        return ready, "RXD/TXD required"
    if category == "i2c":
        ready = any(name.endswith("_SCL") for name in signals) and any(name.endswith("_SDA") for name in signals)
        return ready, "SCL/SDA required"
    if category == "spi":
        ready = any(name.endswith("_CLK") for name in signals) and sum(name.endswith(("_D0", "_D1", "_CS0", "_CS1", "_CSN0", "_CSN1")) for name in signals) >= 2
        return ready, "CLK plus data/CS pins required"
    if category == "mcan":
        ready = any(name.endswith("_RX") for name in signals) and any(name.endswith("_TX") for name in signals)
        return ready, "RX/TX required"
    if category == "mmc":
        ready = any(name.endswith("_CLK") for name in signals) and any(name.endswith("_CMD") for name in signals) and any("_DAT0" in name for name in signals)
        return ready, "CLK/CMD/DAT0 required"
    if category == "ospi":
        ready = any(name.endswith("_CLK") for name in signals) and any("_CSN0" in name for name in signals) and any(name.endswith("_D0") for name in signals)
        return ready, "CLK/CSN0/D0 required"
    if category == "mdio":
        ready = any(name.endswith("_MDC") for name in signals) and any(name.endswith("_MDIO") for name in signals)
        return ready, "MDC/MDIO required"
    return False, "No readiness rule"


def _other_nodes_for_net(netlist_data: NetlistData, net_name: str, soc_refdes: str) -> list[NetNode]:
    for net in netlist_data.nets:
        if net.name == net_name:
            return [node for node in net.nodes if node.refdes != soc_refdes]
    return []


def _bus_component_candidates(nodes: list[NetNode]) -> dict[str, list[NetNode]]:
    grouped: dict[str, list[NetNode]] = defaultdict(list)
    for node in nodes:
        if node.refdes.startswith(("R", "C", "L", "FB", "TP", "Y", "X", "DNP")):
            continue
        grouped[node.refdes].append(node)
    return dict(grouped)


def _pick_part_compatible(parttype: str, part_map: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    key = parttype.upper()
    if key in part_map:
        return key, part_map[key]
    for candidate, value in part_map.items():
        if key.startswith(candidate):
            return candidate, value
    return "", None


def write_outputs(
    config: WorkflowConfig,
    netlist_data: NetlistData,
    lookup_results: list[LookupResult],
    soc_reference: SocReference,
    board_reference: BoardReference,
    board_decisions: BoardDecisions,
) -> None:
    interface_map = _build_interface_mapping(config)
    part_map = _build_part_compatible_map(config)
    grouped = _group_results(lookup_results)
    decisions = _controller_decisions(config, grouped, interface_map, soc_reference, board_reference, board_decisions)

    _write_soc_symbol_quality_report(config, netlist_data, lookup_results)
    _write_soc_pin_net_table(config, netlist_data)
    _write_pinmux_lookup_report(config, lookup_results)
    _write_interface_facts(config, grouped, interface_map)
    _write_pinmux_dtsi(config, grouped, interface_map)
    _write_controller_dtsi(config, grouped, decisions)
    _write_device_stubs(config, netlist_data, grouped, interface_map, part_map, soc_reference, board_decisions)
    _write_maximal_dts(config, grouped, interface_map, soc_reference)
    _write_peripheral_inventory(config, grouped, interface_map)
    _write_todo_report(config, lookup_results, soc_reference, board_reference)
    _write_uboot_spl_outputs(config, grouped, lookup_results, interface_map, soc_reference, board_reference)


def _write_soc_symbol_quality_report(
    config: WorkflowConfig,
    netlist_data: NetlistData,
    results: list[LookupResult],
) -> None:
    path = config.report_facts_dir / "soc_symbol_quality_report.md"
    soc_part_record = netlist_data.parts.get(config.soc_refdes)
    soc_part = soc_part_record.parttype if soc_part_record else ""
    functional = [result for result in results if _is_soc_symbol_functional(result)]
    recognized = [
        result
        for result in functional
        if result.classification
        in {
            "PINMUX_DTS",
            "CONTROLLER_DTS",
            "NON_PINCTRL_HW",
            "PRE_LINUX_CONFIG",
            "GPIO_CANDIDATE",
            "ALT_FUNCTION_REVIEW",
        }
    ]
    ratio = (len(recognized) / len(functional)) if functional else 0.0
    part_ok = config.soc_name.upper() in soc_part.upper() or config.soc_family.upper() in soc_part.upper()
    quality = "PASS" if part_ok and ratio >= 0.90 else "REVIEW"

    lines = ["# SoC Symbol Quality Report", ""]
    lines.append(f"- soc_refdes: `{config.soc_refdes}`")
    lines.append(f"- soc_parttype: `{soc_part}`")
    lines.append(f"- expected_soc_name: `{config.soc_name}`")
    lines.append(f"- expected_soc_family: `{config.soc_family}`")
    lines.append(f"- total_soc_pins: `{len(results)}`")
    lines.append(f"- functional_soc_pins: `{len(functional)}`")
    lines.append(f"- recognized_functional_pins: `{len(recognized)}`")
    lines.append(f"- recognized_ratio: `{ratio:.3f}`")
    lines.append(f"- quality_gate: `{quality}`")
    lines.append("")
    lines.append("## Basis")
    lines.append("")
    lines.append("- U1 parttype should match configured SoC name/family.")
    lines.append("- Functional U1 pins should mostly classify into DB-backed or reviewable results.")
    if quality != "PASS":
        lines.append("")
        lines.append("## Review Required")
        lines.append("")
        lines.append("- Verify active SoC profile, U1 symbol, and package ball naming.")
    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_soc_pin_net_table(config: WorkflowConfig, netlist_data: NetlistData) -> None:
    path = config.facts_soc_pin_net_table_path
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "soc_refdes",
                "soc_part",
                "ball",
                "soc_pin_name",
                "raw_soc_pin_name",
                "source_line",
                "net_name",
                "connected_nodes",
                "component_refs",
                "connected_pin_names",
                "connection_count",
            ],
        )
        writer.writeheader()
        for row in netlist_data.soc_pins:
            writer.writerow(
                {
                    "soc_refdes": row.soc_refdes,
                    "soc_part": row.soc_part,
                    "ball": row.ball,
                    "soc_pin_name": row.soc_pin_name,
                    "raw_soc_pin_name": row.raw_soc_pin_name,
                    "source_line": row.source_line,
                    "net_name": row.net_name,
                    "connected_nodes": row.connected_nodes,
                    "component_refs": row.component_refs,
                    "connected_pin_names": row.connected_pin_names,
                    "connection_count": row.connection_count,
                }
            )


def _write_pinmux_lookup_report(config: WorkflowConfig, results: list[LookupResult]) -> None:
    path = config.facts_lookup_report_path
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "status",
                "ball",
                "soc_pin_name",
                "net_name",
                "candidate_signals",
                "source_line",
                "match_reason",
                "interface_key",
                "db_signal_name",
                "db_device_pin_name",
                "db_interface_name",
                "dts_offset",
                "mux_mode",
                "linux_macro",
                "result",
                "confidence",
            ],
        )
        writer.writeheader()
        for result in results:
            row = result.db_row or {}
            writer.writerow(
                {
                    "status": result.status,
                    "ball": result.soc_pin.ball,
                    "soc_pin_name": result.soc_pin.soc_pin_name,
                    "net_name": result.soc_pin.net_name,
                    "candidate_signals": "; ".join(result.candidate_signals),
                    "source_line": result.soc_pin.source_line,
                    "match_reason": result.match_reason,
                    "interface_key": result.interface_key,
                    "db_signal_name": row.get("signal_name", ""),
                    "db_device_pin_name": row.get("device_pin_name", ""),
                    "db_interface_name": row.get("interface_name", ""),
                    "dts_offset": row.get("dts_offset", ""),
                    "mux_mode": row.get("mux_mode", ""),
                    "linux_macro": row.get("linux_macro", ""),
                    "result": result.classification,
                    "confidence": result.confidence,
                }
            )


def _write_interface_facts(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
) -> None:
    path = config.facts_interface_summary_path
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "interface_key",
                "category",
                "node_name",
                "detected_signals",
                "total_pin_facts",
                "pinctrl_fact_count",
                "controller_dts_count",
                "non_pinctrl_hw_count",
                "pre_linux_count",
                "gpio_candidate_count",
                "alt_function_review_count",
                "out_of_scope_count",
                "unmatched_or_conflict_count",
                "pinctrl_fact_possible",
            ],
        )
        writer.writeheader()
        for interface_key in sorted(grouped):
            mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key) or {}
            stats = _interface_stats(grouped[interface_key])
            signals = sorted(
                result.db_row["signal_name"]
                for result in grouped[interface_key]
                if result.db_row and result.db_row.get("signal_name")
            )
            writer.writerow(
                {
                    "interface_key": interface_key,
                    "category": _interface_category(interface_key),
                    "node_name": mapping.get("node", ""),
                    "detected_signals": "; ".join(signals),
                    "total_pin_facts": stats["total"],
                    "pinctrl_fact_count": stats["pinctrl_facts"],
                    "controller_dts_count": stats["controller_dts"],
                    "non_pinctrl_hw_count": stats["non_pinctrl_hw"],
                    "pre_linux_count": stats["pre_linux"],
                    "gpio_candidate_count": stats["gpio_candidate"],
                    "alt_function_review_count": stats["alt_function_review"],
                    "out_of_scope_count": stats["out_of_scope"],
                    "unmatched_or_conflict_count": stats["unmatched_or_conflict"],
                    "pinctrl_fact_possible": "yes" if stats["valid_pin_count"] else "no",
                }
            )


def _write_pinmux_dtsi(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
) -> None:
    path = config.pinmux_facts_path
    lines: list[str] = []
    lines.append("/* Hardware facts pinmux generated from .NET + SoC SysConfig DB. */")
    lines.append("/* This file should contain only entries with valid offset + mux lookup. */")
    lines.append("")

    domain_groups = {"MAIN": [], "MCU_WKUP": []}
    for interface_key, results in grouped.items():
        if not any(_is_pinctrl_fact(result) for result in results):
            continue
        mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key)
        domain = (mapping or {}).get("domain") or (results[0].db_row or {}).get("domain") or "MAIN"
        domain_groups.setdefault(domain, []).append((interface_key, results, mapping or {}))

    for domain, controller in (("MAIN", "&main_pmx0"), ("MCU_WKUP", "&wkup_pmx0")):
        if not domain_groups.get(domain):
            continue
        lines.append(f"{controller} {{")
        for interface_key, results, mapping in sorted(domain_groups[domain], key=lambda item: item[0]):
            label = mapping.get("pinctrl_label") or f"{interface_key.lower()}_pins_default"
            node_name = _slug(label)
            lines.append(f"\t{label}: {node_name} {{")
            lines.append("\t\tpinctrl-single,pins = <")
            for result in results:
                if not _is_pinctrl_fact(result):
                    continue
                signal_name = result.db_row["signal_name"]
                flag, todo_flag = _flag_for_signal(signal_name)
                macro = result.db_row["linux_macro"]
                offset = result.db_row["dts_offset"]
                mode = result.db_row["mux_mode"]
                todo = " TODO: review flag" if todo_flag else ""
                lines.append(
                    f"\t\t\t{macro}({offset}, {flag}, {mode}) /* ({result.soc_pin.ball}) {signal_name} net={result.soc_pin.net_name}{todo} */"
                )
            lines.append("\t\t>;")
            lines.append("\t};")
        lines.append("};")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_controller_dtsi(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    decisions: list[dict[str, Any]],
) -> None:
    path = config.controller_candidates_path
    lines = ["/* Controller candidates generated from hardware facts + SK reference + workflow defaults. */", ""]

    for decision in decisions:
        if not decision["emitted"]:
            continue
        interface_key = str(decision["interface_key"])
        category = str(decision["category"])
        node = str(decision["node"])
        pinctrl_label = str(decision["pinctrl_label"])
        ready = bool(decision["ready"])
        reason = str(decision["ready_reason"])
        use_pinctrl = bool(decision["use_pinctrl"])
        reference_has_pinctrl = decision["reference_has_pinctrl"]
        explicit = decision.get("explicit") or {}

        lines.append(f"&{node} {{")
        if explicit.get("enabled") is False:
            lines.append('\tstatus = "disabled";')
        else:
            lines.append('\tstatus = "okay";')
        if use_pinctrl:
            lines.append('\tpinctrl-names = "default";')
            lines.append(f"\tpinctrl-0 = <&{pinctrl_label}>;")
        elif reference_has_pinctrl is False:
            lines.append(f"\t/* Reference DTS precedent: &{node} is typically used without pinctrl-0 */")
        else:
            lines.append(f"\t/* No valid generated pinctrl entries for {pinctrl_label} */")

        if category == "i2c":
            lines.append(f"\tclock-frequency = <{int(config.defaults.get('i2c_clock_frequency', 400000))}>;")
        elif category == "spi":
            lines.append(f"\tspi-max-frequency = <{int(config.defaults.get('spi_max_frequency', 10000000))}>;")
        elif category == "mmc":
            dat_lines = [
                result
                for result in grouped[interface_key]
                if _is_pinctrl_fact(result) and result.db_row is not None and "_DAT" in result.db_row.get("signal_name", "")
            ]
            if dat_lines:
                width = max(
                    int(_signal_suffix(result.db_row["signal_name"])[3:])
                    for result in dat_lines
                    if result.db_row is not None
                ) + 1
                lines.append(f"\tbus-width = <{width}>;")
            if explicit.get("bus_width"):
                lines.append(f"\tbus-width = <{int(explicit['bus_width'])}>;")
            if explicit.get("non_removable") is True:
                lines.append("\tnon-removable;")
            lines.append("\t/* TODO: confirm card-detect, write-protect, removable policy */")
        elif category == "ospi":
            if explicit.get("bus_width"):
                lines.append(f"\t/* explicit bus width candidate: {explicit['bus_width']} */")
            lines.append("\t/* TODO: confirm flash compatible, partitions, and PHY timing */")
        elif category == "mcan":
            lines.append("\t/* TODO: confirm transceiver standby and termination policy */")

        if not ready:
            lines.append(f"\t/* TODO: controller candidate incomplete: {reason} */")
        lines.append("};")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_device_stubs(
    config: WorkflowConfig,
    netlist_data: NetlistData,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
    part_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
    board_decisions: BoardDecisions,
) -> None:
    path = config.device_candidates_path
    lines = ["/* Device candidates generated from hardware facts + SK reference + workflow defaults. */", "/* This file may require resolver data before production use. */", ""]
    unknown_compatible = str(_linux_base(config).get("unknown_compatible", config.defaults.get("unknown_compatible", "unknown,device")))
    mux_decisions = board_decisions.raw.get("mux_decisions", []) or []

    led_decisions = [item for item in mux_decisions if isinstance(item, dict) and str(item.get("dts_usage", "")).lower() == "gpio-led"]
    if led_decisions:
        lines.append("/ {")
        lines.append("\tled-controller {")
        lines.append('\t\tcompatible = "gpio-leds";')
        for index, item in enumerate(led_decisions):
            selected = str(item.get("selected_function", ""))
            gpio = _gpio_phandle_tuple(selected)
            if not gpio:
                continue
            phandle, line_no = gpio
            label = _slug(str(item.get("net", item.get("id", f"led{index}"))))
            active = str(item.get("active_level", "active_high")).lower()
            active_macro = "GPIO_ACTIVE_LOW" if "low" in active else "GPIO_ACTIVE_HIGH"
            default_state = str(item.get("default_state", "off")).lower()
            lines.append(f"\t\t{label} {{")
            lines.append(f"\t\t\tgpios = <{phandle} {line_no} {active_macro}>;")
            lines.append(f'\t\t\tdefault-state = "{default_state if default_state in {"on", "off", "keep"} else "off"}";')
            lines.append("\t\t};")
        lines.append("\t};")
        lines.append("};")
        lines.append("")

    for interface_key in sorted(grouped):
        category = _interface_category(interface_key)
        mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key)
        if not mapping or category not in {"i2c", "mdio"}:
            continue
        if not soc_reference.has_label(mapping["node"]):
            continue

        bus_nodes: list[NetNode] = []
        for result in grouped[interface_key]:
            if result.classification not in {"PINMUX_DTS", "CONTROLLER_DTS"}:
                continue
            bus_nodes.extend(_other_nodes_for_net(netlist_data, result.soc_pin.net_name, config.soc_refdes))

        candidates = _bus_component_candidates(bus_nodes)
        if not candidates:
            candidates = {}

        lines.append(f"&{mapping['node']} {{")
        explicit_entries = _explicit_external_decisions(board_decisions, interface_key)
        explicit_entries.extend(_explicit_external_decisions(board_decisions, mapping["node"]))
        seen_explicit_refdes: set[str] = set()
        for explicit in explicit_entries:
            refdes = str(explicit.get("refdes", "")).lower()
            if refdes in seen_explicit_refdes:
                continue
            seen_explicit_refdes.add(refdes)
            compatible = str(explicit.get("compatible", "unknown,device"))
            reg = explicit.get("reg")
            if isinstance(reg, int):
                reg_text = hex(reg)
            else:
                reg_text = str(reg) if reg is not None else "0x00"
            lines.append(f"\t{refdes}: {refdes}@{reg_text.replace('0x', '')} {{")
            lines.append(f'\t\tcompatible = "{compatible}";')
            lines.append(f"\t\treg = <{reg_text}>;")
            if explicit.get("purpose"):
                lines.append(f"\t\t/* purpose: {explicit['purpose']} */")
            lines.append("\t};")

        for refdes in sorted(candidates):
            if any(str(item.get("refdes", "")).upper() == refdes.upper() for item in explicit_entries):
                continue
            part = netlist_data.parts.get(refdes)
            parttype = part.parttype if part else refdes
            _, compat_info = _pick_part_compatible(parttype, part_map)
            compatible = compat_info.get("compatible") if compat_info else unknown_compatible

            if category == "i2c":
                lines.append(f"\t{_slug(refdes)}: {refdes.lower()}@0 {{")
                lines.append(f'\t\tcompatible = "{compatible}";')
                lines.append("\t\treg = <0x00>; /* TODO: resolve I2C address */")
                lines.append(f"\t\t/* TODO: confirm part {parttype} and bus attachment */")
                lines.append("\t};")
            else:
                lines.append(f"\t{refdes.lower()}: ethernet-phy@0 {{")
                lines.append(f'\t\tcompatible = "{compatible}";')
                lines.append("\t\treg = <0>; /* TODO: resolve PHY address */")
                lines.append(f"\t\t/* TODO: confirm part {parttype} and RGMII/RMII delay policy */")
                lines.append("\t};")
        lines.append("};")
        lines.append("")

    if len(lines) == 2:
        lines.append("/* No external device stubs were derived with current rules. */")

    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_maximal_dts(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
) -> None:
    path = config.base_linux_dts_path
    lines = ["/dts-v1/;", ""]
    include_base = str(_linux_base(config).get("include_soc_dtsi", config.soc_dtsi[-1] if config.soc_dtsi else "k3-am642.dtsi"))
    pinmux_include = _relative_include(path, config.pinmux_facts_path)
    controllers_include = _relative_include(path, config.controller_candidates_path)
    devices_include = _relative_include(path, config.device_candidates_path)
    lines.append(f'#include "{include_base}"')
    lines.append(f'#include "{pinmux_include}"')
    lines.append(f'#include "{controllers_include}"')
    lines.append(f'#include "{devices_include}"')
    lines.append("")
    lines.append("/ {")
    lines.append(f'\tmodel = "{config.model}";')
    lines.append(f'\tcompatible = "{config.vendor_compatible}", "ti,am642";')
    lines.append('\t/* Base DTS composed from hardware facts and candidate layers. */')
    lines.append("")

    alias_lines: list[str] = []
    chosen_stdout = ""
    alias_pref = _alias_preference(config)
    alias_order = [
        ("serial0", alias_pref.get("serial0", "MCU_UART0")),
        ("serial2", alias_pref.get("serial2", "UART0")),
        ("i2c0", alias_pref.get("i2c0", "I2C0")),
        ("i2c1", alias_pref.get("i2c1", "I2C1")),
        ("mmc0", alias_pref.get("mmc0", "MMC0")),
        ("mmc1", alias_pref.get("mmc1", "MMC1")),
        ("spi0", alias_pref.get("spi0", "OSPI0")),
    ]
    for alias_name, preferred in alias_order:
        if preferred not in grouped:
            continue
        mapping = interface_map.get(preferred) or _default_interface_mapping(preferred)
        if not mapping:
            continue
        if not soc_reference.has_label(mapping["node"]):
            continue
        alias_lines.append(f"\t\t{alias_name} = &{mapping['node']};")

    for preferred in _stdout_preference(config):
        if preferred not in grouped:
            continue
        mapping = interface_map.get(preferred) or _default_interface_mapping(preferred)
        if mapping and soc_reference.has_label(mapping["node"]):
            chosen_stdout = mapping["node"]
            break

    if alias_lines:
        lines.append("\taliases {")
        lines.extend(alias_lines)
        lines.append("\t};")
        lines.append("")

    if chosen_stdout:
        lines.append("\tchosen {")
        lines.append(f"\t\tstdout-path = &{chosen_stdout};")
        lines.append("\t};")

    lines.append("};")
    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_peripheral_inventory(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
) -> None:
    path = config.facts_inventory_path
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "interface_key",
                "category",
                "detected_signals",
                "valid_pin_count",
                "controller_ready",
                "node_name",
                "notes",
            ],
        )
        writer.writeheader()
        for interface_key in sorted(grouped):
            mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key) or {}
            ready, note = _controller_ready(interface_key, grouped[interface_key])
            signals = sorted(
                result.db_row["signal_name"]
                for result in grouped[interface_key]
                if result.db_row and result.db_row.get("signal_name")
            )
            writer.writerow(
                {
                    "interface_key": interface_key,
                    "category": _interface_category(interface_key),
                    "detected_signals": "; ".join(signals),
                    "valid_pin_count": sum(result.has_valid_offset for result in grouped[interface_key]),
                    "controller_ready": "yes" if ready else "no",
                    "node_name": mapping.get("node", ""),
                    "notes": note,
                }
            )


def _classify_missing_offset(result: LookupResult, soc_reference: SocReference) -> str:
    row = result.db_row or {}
    signal = row.get("signal_name", result.soc_pin.soc_pin_name)
    interface = row.get("interface_name", result.interface_key)
    text = signal.upper()

    if signal in soc_reference.no_padconfig_signals:
        return "SoC DTSI comment says no padconfig"
    if text.startswith("DDR0_"):
        return "DDR bootloader/DDR init domain, not Linux board pinctrl"
    if text.startswith("USB0_"):
        return "USB PHY/controller domain, not regular Linux padconfig"
    if text.startswith("SERDES0_"):
        return "SERDES/PHY reference domain, not regular Linux padconfig"
    if text.startswith("MCU_OSC0_"):
        return "Clock input domain, not Linux board pinctrl"
    if interface.upper() == "MMC0":
        return "Controller-only DTS path or no padconfig case"
    return "Manual review required"


def _classify_missing_offset_with_reference(
    result: LookupResult,
    soc_reference: SocReference,
    board_reference: BoardReference,
) -> str:
    row = result.db_row or {}
    signal = row.get("signal_name", result.soc_pin.soc_pin_name)
    interface = row.get("interface_name", result.interface_key)
    signal_upper = signal.upper()

    if signal in board_reference.no_padconfig_signals:
        return "Reference DTS comment says no padconfig"
    if interface.upper() == "MMC0" and board_reference.node_has_pinctrl("sdhci0") is False:
        return "Reference DTS precedent: &sdhci0 is enabled without pinctrl-0"
    if signal_upper.startswith("USB0_"):
        if board_reference.signal_has_pinctrl_precedent("USB0_DRVVBUS") and not board_reference.signal_has_pinctrl_precedent(signal):
            return "Reference DTS precedent: USB pinctrl uses USB0_DRVVBUS only"
    if signal_upper.startswith("SERDES0_"):
        if board_reference.node_has_pinctrl("serdes0") is False or board_reference.node_has_pinctrl("serdes0") is None:
            return "Reference DTS precedent: SERDES is handled by serdes/PHY nodes, not pinctrl"
    if signal_upper.startswith("DDR0_") and not any(name.startswith("DDR0_") for name in board_reference.pinctrl_signals):
        return "Reference DTS precedent: DDR pins do not appear in Linux board pinctrl"

    return _classify_missing_offset(result, soc_reference)


def _missing_offset_group(
    result: LookupResult,
    soc_reference: SocReference,
    board_reference: BoardReference,
) -> str:
    note = _classify_missing_offset_with_reference(result, soc_reference, board_reference)
    if "DDR" in note:
        return "DDR / Bootloader Domain"
    if "USB" in note:
        return "USB / PHY Domain"
    if "SERDES" in note:
        return "SERDES / PHY Domain"
    if "Clock input" in note:
        return "Clock / Reference Input"
    if "sdhci0" in note or "no padconfig" in note or "Controller-only" in note:
        return "Controller-Only Linux DTS"
    return "Manual Review Required"


def _out_of_scope_group(result: LookupResult) -> str:
    signal = result.soc_pin.soc_pin_name.upper()
    if signal.startswith(("VSS", "VDD", "VDDA", "VDDS", "VDDSHV", "VMON", "VPP")):
        return "Power / Ground / Monitor"
    if signal.startswith(("SERDES", "USB0_RCALIB", "USB1_REXT")):
        return "PHY / Analog Reference"
    if signal.startswith(("ADC", "CAP_")):
        return "Analog / Reference"
    return "Other Non-Mux"


def _write_todo_report(
    config: WorkflowConfig,
    results: list[LookupResult],
    soc_reference: SocReference,
    board_reference: BoardReference,
) -> None:
    path = config.todo_report_path
    unmatched = [result for result in results if result.classification == "UNMATCHED_OR_CONFLICT" and result.status == "UNMATCHED"]
    out_of_scope = [result for result in results if result.classification == "OUT_OF_SCOPE"]
    conflicts = [result for result in results if result.status == "CONFLICT"]
    non_pinctrl = [result for result in results if result.classification in {"NON_PINCTRL_HW", "PRE_LINUX_CONFIG", "CONTROLLER_DTS"}]
    alt_reviews = [result for result in results if result.classification in {"ALT_FUNCTION_REVIEW", "GPIO_CANDIDATE"}]

    lines = ["# Manual Review Report", ""]
    lines.append("이 파일은 facts/candidates/base 출력만으로 확정할 수 없는 항목을 모은다.")
    lines.append("")
    lines.append(f"- unmatched soc pins: {len(unmatched)}")
    lines.append(f"- out-of-scope non-mux pins: {len(out_of_scope)}")
    lines.append(f"- conflicting DB lookups: {len(conflicts)}")
    lines.append(f"- non-pinctrl or pre-Linux hardware facts: {len(non_pinctrl)}")
    lines.append(f"- alternate function or GPIO review items: {len(alt_reviews)}")
    lines.append("")

    if unmatched:
        lines.append("## Unmatched")
        for result in unmatched[:40]:
            lines.append(
                f"- {result.soc_pin.ball} {result.soc_pin.soc_pin_name} net={result.soc_pin.net_name} candidates={', '.join(result.candidate_signals)}"
            )
        lines.append("")

    if conflicts:
        lines.append("## Conflicts")
        for result in conflicts[:40]:
            lines.append(
                f"- {result.soc_pin.ball} {result.soc_pin.soc_pin_name} net={result.soc_pin.net_name} alternatives={result.alternatives}"
            )
        lines.append("")

    if non_pinctrl:
        grouped_non_pinctrl: dict[str, list[LookupResult]] = defaultdict(list)
        for result in non_pinctrl:
            grouped_non_pinctrl[_missing_offset_group(result, soc_reference, board_reference)].append(result)

        lines.append("## Non-Pinctrl / Pre-Linux Hardware Facts")
        for group_name in sorted(grouped_non_pinctrl):
            lines.append(f"### {group_name}")
            lines.append(f"- count: {len(grouped_non_pinctrl[group_name])}")
            for result in grouped_non_pinctrl[group_name][:40]:
                row = result.db_row or {}
                lines.append(
                    f"- {result.soc_pin.ball} {row.get('signal_name', result.soc_pin.soc_pin_name)} source=`{result.soc_pin.source_line}` note={result.match_reason}"
                )
            lines.append("")

    if alt_reviews:
        lines.append("## Alternate Function / GPIO Review")
        for result in alt_reviews:
            row = result.db_row or {}
            lines.append(
                f"- {result.soc_pin.ball} {result.soc_pin.soc_pin_name} net={result.soc_pin.net_name} result={result.classification} db_signal={row.get('signal_name', '')} reason={result.match_reason}"
            )
        lines.append("")

    if out_of_scope:
        grouped_out_of_scope: dict[str, list[LookupResult]] = defaultdict(list)
        for result in out_of_scope:
            grouped_out_of_scope[_out_of_scope_group(result)].append(result)

        lines.append("## Out Of Scope Summary")
        for group_name in sorted(grouped_out_of_scope):
            lines.append(f"### {group_name}")
            lines.append(f"- count: {len(grouped_out_of_scope[group_name])}")
            sample = ", ".join(
                f"{item.soc_pin.ball}:{item.soc_pin.soc_pin_name}"
                for item in grouped_out_of_scope[group_name][:8]
            )
            if sample:
                lines.append(f"- sample: {sample}")
            lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_uboot_spl_outputs(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    results: list[LookupResult],
    interface_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
    board_reference: BoardReference,
) -> None:
    _write_uboot_early_facts(config, grouped, interface_map)
    _write_uboot_boot_media_candidates(config, grouped)
    _write_uboot_ddr_candidates(config, results)
    _write_uboot_base_layer(config, grouped, interface_map, soc_reference, board_reference)


def _write_uboot_early_facts(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
) -> None:
    path = config.uboot_early_facts_path
    lines = [
        "/* Early boot hardware facts for U-Boot/SPL candidate use. */",
        "/* This file contains only valid offset-based facts from .NET + SoC DB. */",
        "",
    ]

    domain_groups = {"MAIN": [], "MCU_WKUP": []}
    for interface_key in ["MCU_UART0", "UART0", "MMC0", "MMC1", "OSPI0"]:
        results = grouped.get(interface_key, [])
        valid = [result for result in results if _is_pinctrl_fact(result)]
        if not valid:
            continue
        mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key) or {}
        domain = (mapping.get("domain") or (valid[0].db_row or {}).get("domain") or "MAIN")
        domain_groups.setdefault(domain, []).append((interface_key, valid))

    for domain, controller in (("MAIN", "&main_pmx0"), ("MCU_WKUP", "&wkup_pmx0")):
        entries = domain_groups.get(domain, [])
        if not entries:
            continue
        lines.append(f"{controller} {{")
        for interface_key, valid in entries:
            label = f"uboot_{interface_key.lower()}_early_pins_default"
            node_name = _slug(label)
            lines.append(f"\t{label}: {node_name} {{")
            lines.append("\t\tpinctrl-single,pins = <")
            for result in valid:
                signal_name = result.db_row["signal_name"]
                flag, _ = _flag_for_signal(signal_name)
                lines.append(
                    f"\t\t\t{result.db_row['linux_macro']}({result.db_row['dts_offset']}, {flag}, {result.db_row['mux_mode']}) /* ({result.soc_pin.ball}) {signal_name} */"
                )
            lines.append("\t\t>;")
            lines.append("\t};")
        lines.append("};")
        lines.append("")

    if len(lines) == 3:
        lines.append("/* No early boot pinmux facts were derived by current rules. */")

    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_uboot_boot_media_candidates(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
) -> None:
    path = config.uboot_boot_media_candidates_path
    lines = ["# Boot Media Candidates", ""]
    lines.append("이 파일은 hardware facts와 기본 규칙을 기준으로 U-Boot/SPL boot media 후보를 기록한다.")
    lines.append("")
    for interface_key in _uboot_boot_media_preference(config):
        if interface_key not in grouped:
            continue
        ready, reason = _controller_ready(interface_key, grouped[interface_key])
        lines.append(f"## {interface_key}")
        lines.append("- detected: yes")
        lines.append(f"- controller_ready_from_facts: {'yes' if ready else 'no'}")
        lines.append(f"- readiness_rule: {reason}")
        lines.append("")
    if len(lines) == 4:
        lines.append("- No boot media candidate was detected by current rules.")
    path.write_text("\n".join(lines).rstrip() + "\n")


def _write_uboot_ddr_candidates(config: WorkflowConfig, results: list[LookupResult]) -> None:
    path = config.uboot_ddr_candidates_path
    ddr_lines = ["# DDR Candidate Note", ""]
    ddr_hits = [
        result
        for result in results
        if "DDR" in result.soc_pin.soc_pin_name.upper() or "LPDDR" in result.soc_pin.net_name.upper()
    ]
    if ddr_hits:
        ddr_lines.append("- DDR-related nets were detected in the netlist.")
        ddr_lines.append("- Linux DTS should not attempt to encode DDR training/timing policy.")
        ddr_lines.append("- U-Boot/SPL/DDR tool flow review is required.")
    else:
        ddr_lines.append("- No DDR-related nets were detected by current rules.")
    path.write_text("\n".join(ddr_lines).rstrip() + "\n")


def _write_uboot_base_layer(
    config: WorkflowConfig,
    grouped: dict[str, list[LookupResult]],
    interface_map: dict[str, dict[str, Any]],
    soc_reference: SocReference,
    board_reference: BoardReference,
) -> None:
    dtsi_path = config.uboot_spl_base_path
    summary_path = config.uboot_spl_summary_path
    early_include = _relative_include(dtsi_path, config.uboot_early_facts_path)
    boot_media_rel = _relative_include(summary_path, config.uboot_boot_media_candidates_path)
    ddr_rel = _relative_include(summary_path, config.uboot_ddr_candidates_path)

    console_iface = ""
    console_node = ""
    for preferred in _uboot_stdout_preference(config):
        results = grouped.get(preferred, [])
        if not any(_is_pinctrl_fact(result) for result in results):
            continue
        mapping = interface_map.get(preferred) or _default_interface_mapping(preferred)
        if mapping and soc_reference.has_label(mapping["node"]):
            console_iface = preferred
            console_node = mapping["node"]
            break

    boot_media_candidates: list[tuple[str, str, bool, str, str, bool]] = []
    for interface_key in _uboot_boot_media_preference(config):
        if interface_key not in grouped:
            continue
        mapping = interface_map.get(interface_key) or _default_interface_mapping(interface_key) or {}
        node = str(mapping.get("node", ""))
        if not node or not soc_reference.has_label(node):
            continue
        ready, reason = _controller_ready(interface_key, grouped[interface_key])
        valid_pins = any(_is_pinctrl_fact(result) for result in grouped[interface_key])
        ref_has_pinctrl = board_reference.node_has_pinctrl(node)
        use_pinctrl = valid_pins and ref_has_pinctrl is not False
        boot_media_candidates.append((interface_key, node, ready, reason, f"uboot_{interface_key.lower()}_early_pins_default", use_pinctrl))

    lines = [
        "/* U-Boot/SPL base layer composed from hardware facts and candidate rules. */",
        f'#include "{early_include}"',
        "",
    ]

    if console_node:
        console_label = f"uboot_{console_iface.lower()}_early_pins_default"
        lines.append(f"&{console_node} {{")
        lines.append('\tstatus = "okay";')
        lines.append('\tpinctrl-names = "default";')
        lines.append(f"\tpinctrl-0 = <&{console_label}>;")
        lines.append('\t/* Default U-Boot console candidate */')
        lines.append("};")
        lines.append("")

    for interface_key, node, ready, reason, pinctrl_label, use_pinctrl in boot_media_candidates:
        if not ready:
            continue
        lines.append(f"&{node} {{")
        lines.append('\tstatus = "okay";')
        if use_pinctrl:
            lines.append('\tpinctrl-names = "default";')
            lines.append(f"\tpinctrl-0 = <&{pinctrl_label}>;")
        else:
            lines.append(f"\t/* Reference/default precedent: {interface_key} candidate without pinctrl-0 */")
        lines.append(f"\t/* Default U-Boot boot media candidate: {reason} */")
        lines.append("};")
        lines.append("")

    if len(lines) == 3:
        lines.append("/* No U-Boot/SPL base nodes were produced by current rules. */")

    dtsi_path.write_text("\n".join(lines).rstrip() + "\n")

    summary_lines = ["# U-Boot/SPL Base Summary", ""]
    summary_lines.append(f"- early pinmux facts: `{config.uboot_early_facts_path.name}`")
    summary_lines.append(f"- boot media candidates: `{boot_media_rel}`")
    summary_lines.append(f"- ddr candidate note: `{ddr_rel}`")
    summary_lines.append(f"- base dtsi: `{config.uboot_spl_base_path.name}`")
    summary_lines.append(f"- default console candidate: `{console_iface or 'none'}`")
    summary_lines.append("")
    summary_lines.append("## Boot Media Candidates")
    summary_lines.append("")
    for interface_key, node, ready, reason, _label, use_pinctrl in boot_media_candidates:
        summary_lines.append(f"- {interface_key}: node={node}, ready={ready}, use_pinctrl={use_pinctrl}, rule={reason}")
    summary_path.write_text("\n".join(summary_lines).rstrip() + "\n")
