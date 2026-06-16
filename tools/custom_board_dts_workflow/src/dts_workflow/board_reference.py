from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"')
NODE_REF_RE = re.compile(r'^\s*&([A-Za-z_][A-Za-z0-9_]*)\s*\{')
NO_PADCONFIG_RE = re.compile(r'([A-Z0-9_]+): no padconfig')
TOKEN_RE = re.compile(r'[A-Z][A-Z0-9_]+')


@dataclass
class BoardReference:
    root_files: list[Path]
    parsed_files: list[Path]
    node_pinctrl_usage: dict[str, bool]
    pinctrl_signals: set[str]
    no_padconfig_signals: set[str]

    def node_has_pinctrl(self, label: str) -> bool | None:
        return self.node_pinctrl_usage.get(label)

    def signal_has_pinctrl_precedent(self, signal_name: str) -> bool:
        return signal_name.upper() in self.pinctrl_signals


def load_board_reference(dts_dir: Path, reference_board_dts: list[str]) -> BoardReference:
    roots = [(dts_dir / name).resolve() for name in reference_board_dts]
    parsed_files: list[Path] = []
    node_pinctrl_usage: dict[str, bool] = {}
    pinctrl_signals: set[str] = set()
    no_padconfig_signals: set[str] = set()
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        if path in seen or not path.exists():
            return
        seen.add(path)
        parsed_files.append(path)

        lines = path.read_text(errors="replace").splitlines()
        current_node: str | None = None
        brace_depth = 0

        for line in lines:
            include_match = INCLUDE_RE.match(line)
            if include_match:
                include_name = include_match.group(1)
                include_path = (path.parent / include_name).resolve()
                if include_path.parent == dts_dir.resolve():
                    visit(include_path)

            for match in NO_PADCONFIG_RE.finditer(line):
                no_padconfig_signals.add(match.group(1))

            node_match = NODE_REF_RE.match(line)
            if node_match:
                current_node = node_match.group(1)
                brace_depth = line.count("{") - line.count("}")
                node_pinctrl_usage.setdefault(node_match.group(1), False)
                continue

            if current_node is not None:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 1 and "pinctrl-0" in line:
                    node_pinctrl_usage[current_node] = True

                if "AM64X_IOPAD(" in line or "AM64X_MCU_IOPAD(" in line:
                    comment = line.split("/*", 1)[1] if "/*" in line else line
                    for token in TOKEN_RE.findall(comment):
                        pinctrl_signals.add(token)

                if brace_depth <= 0:
                    current_node = None

    for root in roots:
        visit(root)

    return BoardReference(
        root_files=roots,
        parsed_files=parsed_files,
        node_pinctrl_usage=node_pinctrl_usage,
        pinctrl_signals=pinctrl_signals,
        no_padconfig_signals=no_padconfig_signals,
    )
