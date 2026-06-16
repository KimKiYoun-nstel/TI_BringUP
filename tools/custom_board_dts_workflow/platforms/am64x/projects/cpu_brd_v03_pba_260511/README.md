# CPU_BRD_V03_PBA_260511 Project

이 디렉터리는 현재 AM64x custom board DTS 워크플로우의 실사용 board project다.

핵심 입력:

- netlist: `inputs/netlist/CPU_BRD_V03_PBA_260511.NET`
- schematic PDF: `inputs/schematic/CPU_Brd_V03_PBA_260511.pdf`
- board decision: `docs/board_dts_decisions.yaml`

핵심 문서:

- `docs/board_dts_decisions.yaml`
- `docs/sk_am64b_reference_delta_table.md`

실행 후 주요 산출물:

- `generated/linux/base/k3-am6412-custom-base.dts`
- `generated/linux/final/k3-am6412-custom-final.dts`
- `generated/uboot_spl/base/k3-am6412-custom-u-boot-spl.dtsi`
- `generated/uboot_spl/final/k3-am6412-custom-u-boot-final.dtsi`
- `delivery/linux/`
- `delivery/uboot_spl/`
- `reports/todo/manual_review_report.md`
