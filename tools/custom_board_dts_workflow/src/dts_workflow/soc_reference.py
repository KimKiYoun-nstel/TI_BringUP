from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"')
LABEL_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^;{]+\{')
NO_PADCONFIG_RE = re.compile(r'MMC0_[A-Z0-9_]+: no padconfig')


@dataclass
class SocReference:
    root_files: list[Path]
    parsed_files: list[Path]
    labels: set[str]
    no_padconfig_signals: set[str]

    def has_label(self, label: str) -> bool:
        return label in self.labels


def load_soc_reference(dts_dir: Path, soc_dtsi: list[str]) -> SocReference:
    roots = [(dts_dir / name).resolve() for name in soc_dtsi]
    labels: set[str] = set()
    no_padconfig_signals: set[str] = set()
    parsed_files: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        if path in seen or not path.exists():
            return
        seen.add(path)
        parsed_files.append(path)

        for line in path.read_text(errors="replace").splitlines():
            include_match = INCLUDE_RE.match(line)
            if include_match:
                include_name = include_match.group(1)
                include_path = (path.parent / include_name).resolve()
                if include_path.parent == dts_dir.resolve():
                    visit(include_path)

            label_match = LABEL_RE.match(line)
            if label_match:
                labels.add(label_match.group(1))

            no_padconfig_match = NO_PADCONFIG_RE.search(line)
            if no_padconfig_match:
                signal = no_padconfig_match.group(0).split(":", 1)[0].strip()
                no_padconfig_signals.add(signal)

    for root in roots:
        visit(root)

    return SocReference(
        root_files=roots,
        parsed_files=parsed_files,
        labels=labels,
        no_padconfig_signals=no_padconfig_signals,
    )
