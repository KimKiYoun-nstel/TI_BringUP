#!/usr/bin/env python3

from __future__ import annotations

import argparse
import codecs
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

try:
    import serial
except ImportError:
    serial = None


DEFAULT_READ_TIMEOUT = 0.2
DEFAULT_EXPECT_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 5.0
DEFAULT_LINE_ENDING = "\n"
DEFAULT_UBOOT_BREAK_TEXT = "Hit any key to stop autoboot"
DEFAULT_UBOOT_PROMPT = "=> "
BUFFER_TRIM_THRESHOLD = 1024 * 1024
BUFFER_TRIM_KEEP_TAIL = 4096


class UartExpectError(Exception):
    pass


@dataclass
class LegacyStep:
    kind: str
    value: str


@dataclass
class MatchPattern:
    name: str
    text: str


@dataclass
class MatchResult:
    name: str
    text: str
    end_offset: int


def decode_escapes(value: str) -> str:
    if "\\" not in value:
        return value
    return codecs.decode(value, "unicode_escape")


def parse_legacy_step(raw_step: str) -> LegacyStep:
    if ":" not in raw_step:
        raise argparse.ArgumentTypeError(
            f"Invalid step '{raw_step}'. Expected '<kind>:<value>'."
        )

    kind, raw_value = raw_step.split(":", 1)
    kind = kind.strip().lower()

    if kind not in {"expect", "send", "sendline", "sleep"}:
        raise argparse.ArgumentTypeError(
            f"Unsupported step kind '{kind}'. Use expect, send, sendline, or sleep."
        )

    return LegacyStep(kind=kind, value=raw_value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UART expect/agent helper for bring-up automation.",
        epilog=(
            "예시:\n"
            "  ./tools/uart/uart_expect.py --port /dev/ttyUSB1 "
            "--step 'expect:=> ' --step 'sendline:version' --step 'expect:U-Boot'\n"
            "  ./tools/uart/uart_expect.py --port /dev/ttyUSB1 --plan tools/uart/uart-agent-example.json"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--port", default="/dev/ttyUSB1", help="UART device path")
    parser.add_argument("--baud", type=int, default=115200, help="UART baudrate")
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding for send/expect operations",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=DEFAULT_READ_TIMEOUT,
        help="Per-read timeout in seconds",
    )
    parser.add_argument(
        "--expect-timeout",
        type=float,
        default=DEFAULT_EXPECT_TIMEOUT,
        help="Default timeout for each expect step in seconds",
    )
    parser.add_argument(
        "--write-timeout",
        type=float,
        default=DEFAULT_WRITE_TIMEOUT,
        help="Serial write timeout in seconds",
    )
    parser.add_argument(
        "--line-ending",
        default=DEFAULT_LINE_ENDING,
        help=r"Line ending for sendline/command steps. Default: \n",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=0.0,
        help="Sleep after opening the port before running steps",
    )
    parser.add_argument("--log", help="Optional raw session log path")
    parser.add_argument(
        "--append-log",
        action="store_true",
        help="Append to the log file instead of overwriting it",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not mirror UART output to stdout",
    )
    parser.add_argument(
        "--exclusive",
        action="store_true",
        help="Request exclusive port access on Linux",
    )
    parser.add_argument(
        "--drain-startup",
        action="store_true",
        help="Discard any buffered UART input immediately after opening",
    )
    parser.add_argument(
        "--plan",
        help="Path to a JSON step plan for agent-style automation",
    )
    parser.add_argument(
        "--step",
        dest="steps",
        action="append",
        type=parse_legacy_step,
        help=(
            "Legacy ordered step. Supported forms: expect:<text>, send:<text>, "
            "sendline:<text>, sleep:<seconds>. Escape sequences like \\n and \\r are supported."
        ),
    )
    return parser


def require_string(step: dict[str, Any], field: str) -> str:
    value = step.get(field)
    if not isinstance(value, str) or value == "":
        raise UartExpectError(f"Plan step requires non-empty string field '{field}'.")
    return decode_escapes(value)


def optional_string(step: dict[str, Any], field: str, default: str) -> str:
    value = step.get(field, default)
    if not isinstance(value, str):
        raise UartExpectError(f"Plan field '{field}' must be a string.")
    return decode_escapes(value)


def optional_float(step: dict[str, Any], field: str, default: float) -> float:
    value = step.get(field, default)
    if not isinstance(value, (int, float)):
        raise UartExpectError(f"Plan field '{field}' must be numeric.")

    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise UartExpectError(f"Plan field '{field}' must be a finite non-negative number.")
    return numeric


def load_plan(plan_path: str) -> list[dict[str, Any]]:
    path = Path(plan_path)
    if not path.is_file():
        raise UartExpectError(f"Plan file not found: {plan_path}")

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UartExpectError(f"Invalid JSON plan file {plan_path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise UartExpectError("Plan file root must be a JSON object.")

    steps = loaded.get("steps")
    if not isinstance(steps, list) or not steps:
        raise UartExpectError("Plan file must contain a non-empty 'steps' array.")

    normalized: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise UartExpectError(f"Plan step #{index} must be a JSON object.")

        action = step.get("action")
        if not isinstance(action, str) or action == "":
            raise UartExpectError(f"Plan step #{index} must define a non-empty 'action'.")

        normalized_step = dict(step)
        normalized_step["action"] = action.strip().lower()
        normalized.append(normalized_step)

    return normalized


def normalize_patterns(raw_patterns: Any) -> list[MatchPattern]:
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise UartExpectError("Plan step 'patterns' must be a non-empty array.")

    patterns: list[MatchPattern] = []
    for index, item in enumerate(raw_patterns, start=1):
        if isinstance(item, str):
            text = decode_escapes(item)
            patterns.append(MatchPattern(name=f"match_{index}", text=text))
            continue

        if isinstance(item, dict):
            name = item.get("name")
            text = item.get("text")
            if not isinstance(name, str) or name == "":
                raise UartExpectError("Each pattern object needs a non-empty 'name'.")
            if not isinstance(text, str) or text == "":
                raise UartExpectError("Each pattern object needs a non-empty 'text'.")
            patterns.append(MatchPattern(name=name, text=decode_escapes(text)))
            continue

        raise UartExpectError("Plan patterns must be strings or {name, text} objects.")

    return patterns


def decode_line_ending(value: str) -> str:
    return decode_escapes(value)


class UartExpectSession:
    def __init__(self, args: argparse.Namespace) -> None:
        if serial is None:
            raise UartExpectError(
                "pyserial is not installed. Install it with 'python3 -m pip install pyserial'."
            )

        serial_kwargs: dict[str, Any] = {
            "port": args.port,
            "baudrate": args.baud,
            "timeout": args.read_timeout,
            "write_timeout": args.write_timeout,
        }
        if args.exclusive:
            serial_kwargs["exclusive"] = True

        try:
            self.serial_port = serial.Serial(**serial_kwargs)
        except Exception as exc:
            raise UartExpectError(f"Failed to open serial port {args.port}: {exc}") from exc

        self.args = args
        self.buffer = bytearray()
        self.cursor = 0
        self.last_match_name: str | None = None
        self.last_decision_name: str | None = None
        self.log_file = self._open_log_file(args.log, args.append_log)
        self.line_ending = decode_line_ending(args.line_ending)

    def _open_log_file(self, log_path: str | None, append: bool) -> TextIO | None:
        if not log_path:
            return None

        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        return path.open(mode, encoding="utf-8")

    def close(self) -> None:
        try:
            self.serial_port.close()
        finally:
            if self.log_file is not None:
                self.log_file.close()

    def run(self) -> None:
        if self.args.settle > 0:
            time.sleep(self.args.settle)

        if self.args.drain_startup:
            self.serial_port.reset_input_buffer()

        if self.args.plan:
            for step in load_plan(self.args.plan):
                self.run_plan_step(step)
            return

        if not self.args.steps:
            raise UartExpectError("Provide either --plan or at least one --step.")

        for step in self.args.steps:
            self.run_legacy_step(step)

    def run_legacy_step(self, step: LegacyStep) -> None:
        if step.kind == "sleep":
            self._sleep_step(step.value)
            return

        if step.kind == "expect":
            self.expect_text(decode_escapes(step.value), self.args.expect_timeout)
            return

        if step.kind == "send":
            self.send_text(decode_escapes(step.value), append_newline=False)
            return

        if step.kind == "sendline":
            self.send_text(decode_escapes(step.value), append_newline=True)
            return

        raise UartExpectError(f"Unhandled legacy step kind: {step.kind}")

    def run_plan_step(self, step: dict[str, Any]) -> None:
        action = step["action"]
        if not self.should_run_step(step):
            print(f"[INFO] Skipped step action={action!r} due to match condition", file=sys.stderr)
            return

        if action == "sleep":
            self._sleep_step(str(step.get("seconds", step.get("value", "0"))))
            return

        if action == "send":
            self.send_text(require_string(step, "text"), append_newline=False)
            return

        if action == "sendline":
            self.send_text(require_string(step, "text"), append_newline=True)
            return

        if action == "expect":
            timeout = optional_float(step, "timeout", self.args.expect_timeout)
            self.expect_text(require_string(step, "text"), timeout)
            return

        if action == "expect_any":
            timeout = optional_float(step, "timeout", self.args.expect_timeout)
            patterns = normalize_patterns(step.get("patterns"))
            self.expect_any(patterns, timeout)
            return

        if action == "command":
            timeout = optional_float(step, "timeout", self.args.expect_timeout)
            text = require_string(step, "text")
            self.send_text(text, append_newline=True)

            if "expect" in step:
                self.expect_text(require_string(step, "expect"), timeout)
                return

            if "patterns" in step:
                patterns = normalize_patterns(step.get("patterns"))
                self.expect_any(patterns, timeout)
                return

            return

        if action == "uboot_break":
            self.break_into_uboot(step)
            return

        raise UartExpectError(f"Unsupported plan action: {action}")

    def should_run_step(self, step: dict[str, Any]) -> bool:
        when_match = step.get("when_match")
        unless_match = step.get("unless_match")

        if when_match is not None:
            allowed = when_match if isinstance(when_match, list) else [when_match]
            if self.last_decision_name not in allowed:
                return False

        if unless_match is not None:
            blocked = unless_match if isinstance(unless_match, list) else [unless_match]
            if self.last_decision_name in blocked:
                return False

        return True

    def _sleep_step(self, seconds_text: str) -> None:
        try:
            seconds = float(seconds_text)
        except ValueError as exc:
            raise UartExpectError(f"Invalid sleep step value: {seconds_text}") from exc

        if not math.isfinite(seconds) or seconds < 0:
            raise UartExpectError(f"Sleep step must be a finite non-negative number: {seconds_text}")

        time.sleep(seconds)

    def send_text(self, text: str, append_newline: bool) -> None:
        payload = text + (self.line_ending if append_newline else "")
        data = payload.encode(self.args.encoding)
        try:
            self.serial_port.write(data)
            self.serial_port.flush()
        except Exception as exc:
            raise UartExpectError(f"Failed to write to serial port: {exc}") from exc

        printable = payload.replace("\r", "\\r").replace("\n", "\\n")
        print(f"[INFO] Sent: {printable}", file=sys.stderr)

    def expect_text(self, text: str, timeout: float) -> MatchResult:
        result = self._wait_for_patterns([MatchPattern(name="expect", text=text)], timeout)
        self.last_match_name = result.name
        print(f"[INFO] Matched expect text: {text!r}", file=sys.stderr)
        return result

    def expect_any(self, patterns: list[MatchPattern], timeout: float) -> MatchResult:
        result = self._wait_for_patterns(patterns, timeout)
        self.last_match_name = result.name
        self.last_decision_name = result.name
        print(
            f"[INFO] Matched pattern: name={result.name!r} text={result.text!r}",
            file=sys.stderr,
        )
        return result

    def break_into_uboot(self, step: dict[str, Any]) -> None:
        timeout = optional_float(step, "timeout", self.args.expect_timeout)
        trigger = optional_string(step, "trigger", DEFAULT_UBOOT_BREAK_TEXT)
        prompt = optional_string(step, "prompt", DEFAULT_UBOOT_PROMPT)
        send_text = optional_string(step, "send", self.line_ending)

        result = self.expect_any(
            [
                MatchPattern(name="autoboot_prompt", text=trigger),
                MatchPattern(name="uboot_prompt", text=prompt),
            ],
            timeout,
        )

        if result.name == "autoboot_prompt":
            self.send_text(send_text, append_newline=False)
            self.expect_text(prompt, timeout)
            self.last_match_name = "uboot_prompt"
            self.last_decision_name = "uboot_prompt"

    def _wait_for_patterns(self, patterns: list[MatchPattern], timeout: float) -> MatchResult:
        deadline = time.monotonic() + timeout
        existing = self._search_patterns(patterns)
        if existing is not None:
            self.cursor = existing.end_offset
            self._compact_buffer()
            return existing

        while time.monotonic() < deadline:
            chunk = self.serial_port.read(4096)
            if not chunk:
                continue

            self.buffer.extend(chunk)
            self._emit_output(chunk)

            result = self._search_patterns(patterns)
            if result is not None:
                self.cursor = result.end_offset
                self._compact_buffer()
                return result

        excerpt = self.buffer[max(0, len(self.buffer) - 200) :].decode(
            self.args.encoding,
            errors="replace",
        )
        expected = ", ".join(pattern.text for pattern in patterns)
        raise UartExpectError(
            f"Timed out waiting for one of [{expected}]. Last UART text tail:\n{excerpt}"
        )

    def _search_patterns(self, patterns: list[MatchPattern]) -> MatchResult | None:
        search_space = bytes(self.buffer[self.cursor :])
        first_match: MatchResult | None = None

        for pattern in patterns:
            needle = pattern.text.encode(self.args.encoding)
            index = search_space.find(needle)
            if index < 0:
                continue

            end_offset = self.cursor + index + len(needle)
            candidate = MatchResult(
                name=pattern.name,
                text=pattern.text,
                end_offset=end_offset,
            )
            if first_match is None or candidate.end_offset < first_match.end_offset:
                first_match = candidate

        return first_match

    def _emit_output(self, chunk: bytes) -> None:
        decoded = chunk.decode(self.args.encoding, errors="replace")
        if self.log_file is not None:
            self.log_file.write(decoded)
            self.log_file.flush()

        if not self.args.quiet:
            sys.stdout.write(decoded)
            sys.stdout.flush()

    def _compact_buffer(self) -> None:
        if len(self.buffer) <= BUFFER_TRIM_THRESHOLD or self.cursor <= BUFFER_TRIM_KEEP_TAIL:
            return

        trim_upto = self.cursor - BUFFER_TRIM_KEEP_TAIL
        del self.buffer[:trim_upto]
        self.cursor -= trim_upto


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    session: UartExpectSession | None = None

    try:
        if args.plan and args.steps:
            raise UartExpectError("Use either --plan or --step, not both.")

        session = UartExpectSession(args)
        session.run()
        return 0
    except UartExpectError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    sys.exit(main())
