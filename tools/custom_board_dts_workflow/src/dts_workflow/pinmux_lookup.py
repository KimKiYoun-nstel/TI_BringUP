from __future__ import annotations

import re
from dataclasses import dataclass

from .board_decisions import BoardDecisions
from .netlist_parser import SocPinRecord
from .pinmux_db import PinmuxDB, normalize_name


INTERFACE_SIGNAL_RE = re.compile(
    r"^(MCU_UART\d+|UART\d+|MCU_I2C\d+|I2C\d+|MCU_SPI\d+|SPI\d+|OSPI\d+|MMC\d+|MCAN\d+|MDIO\d+|GPIO\d+|MCU_GPIO\d+|RGMII\d+|RMII\d+)"
)
GENERIC_NET_RE = re.compile(r"^(N\d+|GND|VCC.*|VDD.*|3V3.*|1V8.*|VBAT.*)$")
OUT_OF_SCOPE_PIN_RE = re.compile(
    r"^(VSS|VDD|VDDA|VDDS|VDDSHV|VMON|CAP_|VPP|VREF|SERDES|ANA_|USB1_REXT|ADC\d+_REF)"
)
GPIO_HINT_RE = re.compile(r"(LED|RESET|RST|INT|IRQ|EN|PWR|OE|STAT|FAULT)")
NON_PINCTRL_SIGNAL_RE = re.compile(r"(POR|RESET|RESETSTAT|SAFETY_ERROR|EMU|TCK|TMS|TDI|TDO|TRST)")


@dataclass
class LookupResult:
    soc_pin: SocPinRecord
    status: str
    classification: str
    confidence: str
    match_reason: str
    interface_key: str
    db_row: dict[str, str] | None
    candidate_signals: list[str]
    alternatives: int

    @property
    def has_valid_offset(self) -> bool:
        if not self.db_row:
            return False
        value = (self.db_row.get("dts_offset") or "").strip().lower()
        return value.startswith("0x")


def _is_meaningful_net_name(value: str) -> bool:
    text = normalize_name(value)
    return bool(text) and not GENERIC_NET_RE.match(text)


def _candidate_signals(soc_pin: SocPinRecord) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    candidates.append(("soc_pin_name", normalize_name(soc_pin.soc_pin_name)))
    candidates.append(("raw_soc_pin_name", normalize_name(soc_pin.raw_soc_pin_name)))

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, candidate in candidates:
        if candidate and candidate not in seen:
            unique.append((source, candidate))
            seen.add(candidate)
    return unique


def _row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("ball", ""),
        row.get("signal_name", ""),
        row.get("interface_name", ""),
        row.get("mux_mode", ""),
        row.get("dts_offset", ""),
    )


def _source_score(source: str, match_kind: str) -> int:
    base = {
        "soc_pin_name": 300,
        "raw_soc_pin_name": 250,
    }.get(source, 100)
    if match_kind == "device_pin":
        base -= 50
    return base


def _is_out_of_scope_soc_pin(soc_pin: SocPinRecord) -> bool:
    signal = normalize_name(soc_pin.soc_pin_name)
    return bool(OUT_OF_SCOPE_PIN_RE.match(signal))


def _decision_confidence(status: str) -> str:
    return {
        "confirmed_by_schematic": "HIGH",
        "derived_from_schematic": "MEDIUM",
        "needs_hw_confirmation": "LOW",
    }.get(status, "MEDIUM")


def _classify_override(decision: dict[str, str], row: dict[str, str]) -> str:
    usage = str(decision.get("dts_usage", "")).strip().lower()
    signal = normalize_name(row.get("signal_name", ""))
    interface = normalize_name(row.get("interface_name", ""))
    offset = (row.get("dts_offset") or "").strip().lower()

    if usage in {"gpio-led", "reset-gpio", "interrupt-gpio", "pinctrl"} and offset.startswith("0x"):
        return "PINMUX_DTS"
    if signal.startswith("MMC0_") or interface == "MMC0":
        return "CONTROLLER_DTS"
    if signal.startswith(("USB0_", "SERDES0_", "DDR0_")):
        return "PRE_LINUX_CONFIG"
    return "PINMUX_DTS" if offset.startswith("0x") else "UNMATCHED_OR_CONFLICT"


def _board_mux_override(
    soc_pin: SocPinRecord,
    pinmux_db: PinmuxDB,
    board_decisions: BoardDecisions,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    key = (soc_pin.soc_refdes.upper(), soc_pin.ball.upper(), normalize_name(soc_pin.soc_pin_name))
    decision = board_decisions.mux_by_key.get(key)
    if not decision:
        return None, None

    selected = normalize_name(str(decision.get("selected_function", "")))
    rows = pinmux_db.rows_by_ball_signal.get((soc_pin.ball.upper(), selected), [])
    if not rows:
        rows = [
            row
            for row in pinmux_db.rows_by_ball.get(soc_pin.ball.upper(), [])
            if normalize_name(row.get("signal_name", "")) == selected or normalize_name(row.get("device_pin_name", "")) == selected
        ]
    if len(rows) == 1:
        return decision, rows[0]
    return decision, None


def _net_hint(soc_pin: SocPinRecord) -> str:
    return normalize_name(soc_pin.net_name) if _is_meaningful_net_name(soc_pin.net_name) else ""


def _is_gpio_candidate(soc_pin: SocPinRecord, best_row: dict[str, str]) -> bool:
    signal = normalize_name(best_row.get("signal_name", ""))
    if signal.startswith("GPIO") or signal.startswith("MCU_GPIO"):
        return False

    texts = [soc_pin.net_name, soc_pin.connected_pin_names, soc_pin.component_refs]
    return any(GPIO_HINT_RE.search((text or "").upper()) for text in texts)


def _classify_lookup(
    soc_pin: SocPinRecord,
    best_row: dict[str, str],
    pinmux_db: PinmuxDB,
) -> tuple[str, str, str]:
    signal = normalize_name(best_row.get("signal_name", ""))
    device_pin = normalize_name(best_row.get("device_pin_name", ""))
    interface_name = normalize_name(best_row.get("interface_name", ""))
    offset = (best_row.get("dts_offset") or "").strip().upper()
    net_hint = _net_hint(soc_pin)
    alt_rows = pinmux_db.rows_by_ball_signal.get((soc_pin.ball.upper(), net_hint), []) if net_hint else []

    if _is_out_of_scope_soc_pin(soc_pin):
        return "OUT_OF_SCOPE", "HIGH", "power/ground/analog class pin"

    if interface_name in {"DDR0", "USB0", "SERDES0", "PCIE0"} or signal.startswith(("DDR0_", "USB0_", "SERDES0_")):
        return "PRE_LINUX_CONFIG", "HIGH", "pre-Linux controller or PHY domain"

    if interface_name in {"SYSTEM0", "MCU_SYSTEM0", "MCU_DEBUG0", "MCU_OSC0"} or NON_PINCTRL_SIGNAL_RE.search(signal):
        return "NON_PINCTRL_HW", "HIGH", "system/reset/debug/clock hardware fact"

    if _is_gpio_candidate(soc_pin, best_row):
        return "GPIO_CANDIDATE", "MEDIUM", "net or connected circuit suggests GPIO-style usage"

    if net_hint and net_hint not in {signal, device_pin} and alt_rows:
        return "ALT_FUNCTION_REVIEW", "MEDIUM", "alternate function hinted by net name on same ball"

    if offset.startswith("0X"):
        return "PINMUX_DTS", "HIGH", "ball + TI symbol pin name matched SysConfig DB"

    if signal.startswith("MMC0_") or interface_name == "MMC0":
        return "CONTROLLER_DTS", "HIGH", "controller-only DTS path without padconfig"

    return "UNMATCHED_OR_CONFLICT", "LOW", "matched row lacks usable pinctrl offset"


def derive_interface_key(row: dict[str, str]) -> str:
    signal_name = normalize_name(row.get("signal_name", ""))
    match = INTERFACE_SIGNAL_RE.match(signal_name)
    if match:
        return match.group(1)

    interface_name = (row.get("interface_name", "") or "").strip().upper()
    if interface_name.startswith("MCU_USART"):
        return interface_name.replace("MCU_USART", "MCU_UART")
    if interface_name.startswith("USART"):
        return interface_name.replace("USART", "UART")
    return interface_name


def run_pinmux_lookup(
    soc_pins: list[SocPinRecord],
    pinmux_db: PinmuxDB,
    board_decisions: BoardDecisions,
) -> list[LookupResult]:
    results: list[LookupResult] = []

    for soc_pin in soc_pins:
        ball = soc_pin.ball.upper()
        decision, override_row = _board_mux_override(soc_pin, pinmux_db, board_decisions)
        if decision is not None:
            if override_row is None:
                results.append(
                    LookupResult(
                        soc_pin=soc_pin,
                        status="UNMATCHED_OR_CONFLICT",
                        classification="UNMATCHED_OR_CONFLICT",
                        confidence=_decision_confidence(str(decision.get("status", ""))),
                        match_reason=f"board_mux_decision:{decision.get('id', '')}; selected_function not valid in SysConfig DB",
                        interface_key="",
                        db_row=None,
                        candidate_signals=[normalize_name(str(decision.get("selected_function", "")))],
                        alternatives=0,
                    )
                )
                continue

            classification = _classify_override(decision, override_row)
            results.append(
                LookupResult(
                    soc_pin=soc_pin,
                    status="MATCHED" if classification == "PINMUX_DTS" else classification,
                    classification=classification,
                    confidence=_decision_confidence(str(decision.get("status", ""))),
                    match_reason=f"board_mux_decision:{decision.get('id', '')}; explicit board-level override",
                    interface_key=derive_interface_key(override_row),
                    db_row=override_row,
                    candidate_signals=[normalize_name(str(decision.get("selected_function", "")))],
                    alternatives=1,
                )
            )
            continue

        candidates = _candidate_signals(soc_pin)
        scored_matches: list[tuple[int, str, dict[str, str]]] = []
        seen_rows: set[tuple[str, str, str, str, str]] = set()

        for source, candidate in candidates:
            for row in pinmux_db.rows_by_ball_signal.get((ball, candidate), []):
                row_key = _row_key(row)
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                scored_matches.append((_source_score(source, "signal"), f"{source}:{candidate}", row))

        for source, candidate in candidates:
            for row in pinmux_db.rows_by_ball_device.get((ball, candidate), []):
                row_key = _row_key(row)
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                scored_matches.append((_source_score(source, "device_pin"), f"{source}:{candidate}", row))

        if not scored_matches:
            status = "OUT_OF_SCOPE" if _is_out_of_scope_soc_pin(soc_pin) else "UNMATCHED"
            results.append(
                LookupResult(
                    soc_pin=soc_pin,
                    status=status,
                    classification=status,
                    confidence="LOW" if status == "UNMATCHED" else "HIGH",
                    match_reason="no DB row",
                    interface_key="",
                    db_row=None,
                    candidate_signals=[candidate for _, candidate in candidates],
                    alternatives=0,
                )
            )
            continue

        scored_matches.sort(key=lambda item: item[0], reverse=True)
        best_score, reason, best_row = scored_matches[0]
        same_best = [item for item in scored_matches if item[0] == best_score]

        if len({_row_key(item[2]) for item in same_best}) > 1:
            results.append(
                LookupResult(
                    soc_pin=soc_pin,
                    status="CONFLICT",
                    classification="UNMATCHED_OR_CONFLICT",
                    confidence="LOW",
                    match_reason="multiple top-ranked rows",
                    interface_key="",
                    db_row=None,
                    candidate_signals=[candidate for _, candidate in candidates],
                    alternatives=len(same_best),
                )
            )
            continue

        classification, confidence, reason_text = _classify_lookup(soc_pin, best_row, pinmux_db)
        status = "MATCHED" if classification == "PINMUX_DTS" else classification

        results.append(
            LookupResult(
                soc_pin=soc_pin,
                status=status,
                classification=classification,
                confidence=confidence,
                match_reason=f"{reason}; {reason_text}",
                interface_key=derive_interface_key(best_row),
                db_row=best_row,
                candidate_signals=[candidate for _, candidate in candidates],
                alternatives=len(scored_matches),
            )
        )

    return results
