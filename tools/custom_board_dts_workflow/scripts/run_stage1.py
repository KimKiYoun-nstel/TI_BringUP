#!/usr/bin/env python3
# pyright: reportMissingImports=false
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dts_workflow.config import ensure_output_dirs, load_config, validate_config
from dts_workflow.board_decisions import load_board_decisions
from dts_workflow.board_reference import load_board_reference
from dts_workflow.dts_writer import write_outputs
from dts_workflow.netlist_parser import parse_protel_netlist
from dts_workflow.pinmux_db import load_pinmux_db
from dts_workflow.pinmux_lookup import run_pinmux_lookup
from dts_workflow.soc_reference import load_soc_reference


def main() -> int:
    config = load_config(ROOT / "config" / "paths.local.yaml")
    validate_config(config)
    ensure_output_dirs(config)

    netlist_data = parse_protel_netlist(config.netlist_path, config.soc_refdes, config.soc_name)
    pinmux_db = load_pinmux_db(config.pinmux_db_csv)
    board_decisions = load_board_decisions(config.board_decisions_path)
    soc_reference = load_soc_reference(config.linux_dts_dir, config.soc_dtsi)
    board_reference = load_board_reference(config.linux_dts_dir, config.reference_board_dts)
    lookup_results = run_pinmux_lookup(netlist_data.soc_pins, pinmux_db, board_decisions)
    write_outputs(config, netlist_data, lookup_results, soc_reference, board_reference, board_decisions)

    matched = sum(result.status == "MATCHED" for result in lookup_results)
    missing_offset = sum(result.status == "MATCHED_NO_OFFSET" for result in lookup_results)
    unmatched = sum(result.status == "UNMATCHED" for result in lookup_results)
    out_of_scope = sum(result.status == "OUT_OF_SCOPE" for result in lookup_results)
    conflicts = sum(result.status == "CONFLICT" for result in lookup_results)

    print("Custom Board DTS Workflow Stage-1 completed")
    print(f"project_root={config.project_root}")
    print(f"platform_dir={config.platform_dir}")
    print(f"board_project_dir={config.board_project_dir}")
    print(f"soc_pin_facts={len(netlist_data.soc_pins)}")
    print(f"matched={matched}")
    print(f"matched_no_offset={missing_offset}")
    print(f"unmatched={unmatched}")
    print(f"out_of_scope={out_of_scope}")
    print(f"conflicts={conflicts}")
    print(f"reports_dir={config.reports_dir}")
    print(f"generated_linux_dir={config.generated_linux_dir}")
    print(f"generated_uboot_dir={config.generated_uboot_dir}")
    print(f"soc_reference_labels={len(soc_reference.labels)}")
    print(f"board_reference_nodes={len(board_reference.node_pinctrl_usage)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
