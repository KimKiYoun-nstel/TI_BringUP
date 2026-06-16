from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_DB_COLUMNS = [
    "soc",
    "package",
    "ball",
    "device_pin_id",
    "device_pin_name",
    "control_register_offset",
    "interface_name",
    "signal_name",
    "peripheral_pin_id",
    "peripheral_pin_name",
    "mux_mode",
    "io_dir",
    "power_domain_id",
    "domain",
    "linux_macro",
    "dts_offset",
    "source",
]


@dataclass
class WorkflowConfig:
    project_root: Path
    platform_dir: Path
    board_project_dir: Path
    netlist_path: Path
    soc_refdes: str
    soc_name: str
    soc_family: str
    package: str
    pinmux_db_csv: Path
    pinmux_db_json: Path
    linux_dts_dir: Path
    linux_include_dir: Path
    soc_dtsi: list[str]
    reference_board_dts: list[str]
    pinctrl_header: str
    board_dts_prefix: str
    vendor_compatible: str
    model: str
    defaults: dict[str, Any]
    workflow_defaults: dict[str, Any]
    override_workflow_path: Path
    board_decisions_path: Path

    @property
    def config_dir(self) -> Path:
        return self.project_root / "config"

    @property
    def platform_config_dir(self) -> Path:
        return self.platform_dir / "config"

    @property
    def platform_db_dir(self) -> Path:
        return self.platform_dir / "db"

    @property
    def platform_docs_dir(self) -> Path:
        return self.platform_dir / "docs"

    @property
    def board_inputs_dir(self) -> Path:
        return self.board_project_dir / "inputs"

    @property
    def generated_linux_dir(self) -> Path:
        return self.board_project_dir / "generated" / "linux"

    @property
    def facts_linux_dir(self) -> Path:
        return self.generated_linux_dir / str(self.workflow_defaults.get("outputs", {}).get("facts_dir", "facts"))

    @property
    def candidates_linux_dir(self) -> Path:
        return self.generated_linux_dir / str(self.workflow_defaults.get("outputs", {}).get("candidates_dir", "candidates"))

    @property
    def base_linux_dir(self) -> Path:
        return self.generated_linux_dir / str(self.workflow_defaults.get("outputs", {}).get("base_dir", "base"))

    @property
    def generated_uboot_dir(self) -> Path:
        return self.board_project_dir / "generated" / "uboot_spl"

    @property
    def facts_uboot_dir(self) -> Path:
        return self.generated_uboot_dir / str(self.workflow_defaults.get("outputs", {}).get("uboot_facts_dir", "facts"))

    @property
    def candidates_uboot_dir(self) -> Path:
        return self.generated_uboot_dir / str(self.workflow_defaults.get("outputs", {}).get("uboot_candidates_dir", "candidates"))

    @property
    def base_uboot_dir(self) -> Path:
        return self.generated_uboot_dir / str(self.workflow_defaults.get("outputs", {}).get("uboot_base_dir", "base"))

    @property
    def reports_dir(self) -> Path:
        return self.board_project_dir / "reports"

    @property
    def report_facts_dir(self) -> Path:
        return self.reports_dir / str(self.workflow_defaults.get("outputs", {}).get("reports_facts_dir", "facts"))

    @property
    def report_todo_dir(self) -> Path:
        return self.reports_dir / str(self.workflow_defaults.get("outputs", {}).get("reports_todo_dir", "todo"))

    @property
    def pinmux_facts_path(self) -> Path:
        return self.facts_linux_dir / f"{self.board_dts_prefix}-pinmux.facts.dtsi"

    @property
    def controller_candidates_path(self) -> Path:
        return self.candidates_linux_dir / f"{self.board_dts_prefix}-controllers.candidates.dtsi"

    @property
    def device_candidates_path(self) -> Path:
        return self.candidates_linux_dir / f"{self.board_dts_prefix}-devices.candidates.stub.dtsi"

    @property
    def base_linux_dts_path(self) -> Path:
        suffix = str(self.workflow_defaults.get("linux_base", {}).get("base_dts_name", "base"))
        return self.base_linux_dir / f"{self.board_dts_prefix}-{suffix}.dts"

    @property
    def uboot_early_facts_path(self) -> Path:
        return self.facts_uboot_dir / f"{self.board_dts_prefix}-early-pinmux.facts.dtsi"

    @property
    def uboot_boot_media_candidates_path(self) -> Path:
        return self.candidates_uboot_dir / f"{self.board_dts_prefix}-boot-media.candidates.md"

    @property
    def uboot_ddr_candidates_path(self) -> Path:
        return self.candidates_uboot_dir / f"{self.board_dts_prefix}-ddr.candidates.md"

    @property
    def uboot_spl_base_path(self) -> Path:
        return self.base_uboot_dir / f"{self.board_dts_prefix}-u-boot-spl.dtsi"

    @property
    def uboot_spl_summary_path(self) -> Path:
        return self.base_uboot_dir / f"{self.board_dts_prefix}-u-boot-spl.md"

    @property
    def facts_soc_pin_net_table_path(self) -> Path:
        return self.report_facts_dir / "soc_pin_net_table.csv"

    @property
    def facts_lookup_report_path(self) -> Path:
        return self.report_facts_dir / "pinmux_lookup_report.csv"

    @property
    def facts_inventory_path(self) -> Path:
        return self.report_facts_dir / "peripheral_inventory.csv"

    @property
    def facts_interface_summary_path(self) -> Path:
        return self.report_facts_dir / "interface_facts.csv"

    @property
    def todo_report_path(self) -> Path:
        return self.report_todo_dir / "manual_review_report.md"


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> WorkflowConfig:
    data = load_yaml(path)
    project_root = Path(data["project_root"]).resolve()
    board_project_dir = _resolve_path(project_root, data["board_project_dir"])
    workflow_defaults = load_yaml(project_root / "config" / "workflow_defaults.yaml")
    override_workflow_path = _resolve_path(
        project_root,
        str(data.get("override_workflow_yaml", "config/override.local.yaml")),
    )
    board_decisions_path = _resolve_path(
        board_project_dir,
        str(data.get("board_decisions_yaml", "docs/board_dts_decisions.yaml")),
    )
    if override_workflow_path.exists():
        workflow_defaults = merge_dicts(workflow_defaults, load_yaml(override_workflow_path))

    return WorkflowConfig(
        project_root=project_root,
        platform_dir=_resolve_path(project_root, data["platform_dir"]),
        board_project_dir=board_project_dir,
        netlist_path=_resolve_path(board_project_dir, data["netlist_path"]),
        soc_refdes=str(data["soc_refdes"]),
        soc_name=str(data["soc_name"]),
        soc_family=str(data["soc_family"]),
        package=str(data["package"]),
        pinmux_db_csv=_resolve_path(project_root, data["pinmux_db_csv"]),
        pinmux_db_json=_resolve_path(project_root, data["pinmux_db_json"]),
        linux_dts_dir=Path(data["linux_dts_dir"]).resolve(),
        linux_include_dir=Path(data["linux_include_dir"]).resolve(),
        soc_dtsi=list(data.get("soc_dtsi", [])),
        reference_board_dts=list(data.get("reference_board_dts", [])),
        pinctrl_header=str(data["pinctrl_header"]),
        board_dts_prefix=str(data["board_dts_prefix"]),
        vendor_compatible=str(data["vendor_compatible"]),
        model=str(data["model"]),
        defaults=dict(data.get("defaults", {})),
        workflow_defaults=workflow_defaults,
        override_workflow_path=override_workflow_path,
        board_decisions_path=board_decisions_path,
    )


def validate_config(config: WorkflowConfig) -> None:
    required_paths = {
        "project_root": config.project_root,
        "netlist_path": config.netlist_path,
        "platform_dir": config.platform_dir,
        "board_project_dir": config.board_project_dir,
        "pinmux_db_csv": config.pinmux_db_csv,
        "pinmux_db_json": config.pinmux_db_json,
        "linux_dts_dir": config.linux_dts_dir,
        "linux_include_dir": config.linux_include_dir,
    }

    for name, path in required_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing required path for {name}: {path}")

    missing_dtsi = [name for name in config.soc_dtsi if not (config.linux_dts_dir / name).exists()]
    if missing_dtsi:
        raise FileNotFoundError(
            "Missing SoC DTSI files in workspace Linux DTS tree: " + ", ".join(missing_dtsi)
        )

    missing_reference = [
        name for name in config.reference_board_dts if not (config.linux_dts_dir / name).exists()
    ]
    if missing_reference:
        raise FileNotFoundError(
            "Missing reference board DTS files in workspace Linux DTS tree: "
            + ", ".join(missing_reference)
        )

    validate_pinmux_db(config.pinmux_db_csv)


def validate_pinmux_db(path: Path) -> None:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_DB_COLUMNS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Pinmux DB is missing required columns: {', '.join(missing)}")


def ensure_output_dirs(config: WorkflowConfig) -> None:
    config.generated_linux_dir.mkdir(parents=True, exist_ok=True)
    config.facts_linux_dir.mkdir(parents=True, exist_ok=True)
    config.candidates_linux_dir.mkdir(parents=True, exist_ok=True)
    config.base_linux_dir.mkdir(parents=True, exist_ok=True)
    config.generated_uboot_dir.mkdir(parents=True, exist_ok=True)
    config.facts_uboot_dir.mkdir(parents=True, exist_ok=True)
    config.candidates_uboot_dir.mkdir(parents=True, exist_ok=True)
    config.base_uboot_dir.mkdir(parents=True, exist_ok=True)
    config.reports_dir.mkdir(parents=True, exist_ok=True)
    config.report_facts_dir.mkdir(parents=True, exist_ok=True)
    config.report_todo_dir.mkdir(parents=True, exist_ok=True)
