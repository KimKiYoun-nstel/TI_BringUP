# pyright: reportMissingImports=false
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dts_workflow.board_decisions import load_board_decisions
from dts_workflow.config import load_config
from dts_workflow.netlist_parser import parse_protel_netlist
from dts_workflow.pinmux_db import load_pinmux_db
from dts_workflow.pinmux_lookup import run_pinmux_lookup


class Stage1SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(PROJECT_ROOT / "config" / "paths.local.yaml")

    def test_required_signal_lookup(self) -> None:
        netlist_data = parse_protel_netlist(
            self.config.netlist_path,
            self.config.soc_refdes,
            self.config.soc_name,
        )
        pinmux_db = load_pinmux_db(self.config.pinmux_db_csv)
        board_decisions = load_board_decisions(self.config.board_decisions_path)
        results = run_pinmux_lookup(netlist_data.soc_pins, pinmux_db, board_decisions)

        expected = {
            ("D15", "UART0_RXD"): "0x0230",
            ("C16", "UART0_TXD"): "0x0234",
            ("A18", "I2C0_SCL"): "0x0260",
            ("B18", "I2C0_SDA"): "0x0264",
            ("A9", "MCU_UART0_RXD"): "0x0028",
            ("A8", "MCU_UART0_TXD"): "0x002c",
        }

        lookup = {}
        for result in results:
            if not result.db_row:
                continue
            lookup[(result.soc_pin.ball, result.db_row["signal_name"])] = result.db_row["dts_offset"]

        for key, expected_offset in expected.items():
            self.assertEqual(lookup.get(key), expected_offset, key)

    def test_stage1_generates_soc_based_maximal_dts(self) -> None:
        subprocess.run(
            ["python3", str(PROJECT_ROOT / "scripts" / "run_stage1.py")],
            check=True,
            cwd=PROJECT_ROOT.parents[2],
        )

        maximal_dts = (
            self.config.board_project_dir / "generated" / "linux" / "base" / "k3-am6412-custom-base.dts"
        ).read_text()
        controller_dtsi = (
            self.config.board_project_dir / "generated" / "linux" / "candidates" / "k3-am6412-custom-controllers.candidates.dtsi"
        ).read_text()
        interface_facts = (
            self.config.board_project_dir / "reports" / "facts" / "interface_facts.csv"
        ).read_text()
        manual_review = (
            self.config.board_project_dir / "reports" / "todo" / "manual_review_report.md"
        ).read_text()
        uboot_base = (
            self.config.board_project_dir / "generated" / "uboot_spl" / "base" / "k3-am6412-custom-u-boot-spl.dtsi"
        ).read_text()
        uboot_summary = (
            self.config.board_project_dir / "generated" / "uboot_spl" / "base" / "k3-am6412-custom-u-boot-spl.md"
        ).read_text()
        self.assertIn('#include "k3-am642.dtsi"', maximal_dts)
        self.assertNotIn('k3-am642-sk.dts', maximal_dts)
        self.assertIn('../facts/k3-am6412-custom-pinmux.facts.dtsi', maximal_dts)
        self.assertIn('../candidates/k3-am6412-custom-controllers.candidates.dtsi', maximal_dts)
        self.assertIn('&sdhci0 {', controller_dtsi)
        sdhci0_block = controller_dtsi.split('&sdhci0 {', 1)[1].split('};', 1)[0]
        self.assertNotIn('\tpinctrl-0 = <', sdhci0_block)
        self.assertIn('interface_key,category,node_name', interface_facts)
        self.assertIn('### Controller-Only Linux DTS', manual_review)
        self.assertIn('MMC0_CMD', manual_review)
        self.assertIn('test-led2', devices_dtsi := (self.config.board_project_dir / "generated" / "linux" / "candidates" / "k3-am6412-custom-devices.candidates.stub.dtsi").read_text())
        self.assertIn('GPIO0_13', (self.config.board_project_dir / "reports" / "facts" / "pinmux_lookup_report.csv").read_text())
        self.assertIn('../facts/k3-am6412-custom-early-pinmux.facts.dtsi', uboot_base)
        self.assertIn('&main_uart0 {', uboot_base)
        self.assertIn('default console candidate: `UART0`', uboot_summary)


if __name__ == "__main__":
    unittest.main()
