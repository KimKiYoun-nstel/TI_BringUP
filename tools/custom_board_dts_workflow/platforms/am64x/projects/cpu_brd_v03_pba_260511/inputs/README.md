# Inputs

Expected input layout:

```text
platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/netlist/
  CPU_BRD_V03_PBA_260511.NET

platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/schematic/
  CPU_Brd_V03_PBA_260511.pdf

platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/reference_dts/linux/
  k3-am642-sk.dts
  k3-am642.dtsi
  k3-am64*.dtsi

platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/reference_dts/uboot/
  k3-am642-r5-sk.dts
  k3-am642-sk-u-boot.dtsi
  k3-am64-ddr.dtsi
  ...

platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/reference_headers/
  k3-pinctrl.h
  k3-serdes.h
  k3-timesync-router.h

platforms/am64x/db/
  am64x_sysconfig_pinmux_db.csv
  am64x_sysconfig_pinmux_db.json
```

`.NET` 파일은 board-specific electrical connectivity의 1차 사실 입력이다.

`schematic/` 아래 PDF는 `.NET`만으로 확정되지 않는 board intent를 확인하는 입력이다.
현재 helper가 직접 읽지는 않지만, `board_dts_decisions.yaml`을 작성할 때의 기준 근거다.

`reference_dts`와 `reference_headers` 복사본은 이 board project의 비교용 입력이다.
workspace Linux/U-Boot DTS source는 여전히 primary upstream reference다.
