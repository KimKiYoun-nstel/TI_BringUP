# Linux DTS Set: bringup-default

이 set는 `cpu_brd_v03_pba_260511` 보드의 Linux bring-up 기본 build 입력이다.

source workflow final:

- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/linux/final/k3-am6412-custom-final.dts`
- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/linux/final/k3-am6412-custom-final-overrides.dtsi`
- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/linux/facts/k3-am6412-custom-pinmux.facts.dtsi`

반영 정책:

- LPDDR4 2GB memory node
- reserved-memory baseline candidate 유지
- `main_uart0` Linux console
- `main_uart2`는 `K19 TX + W6 RX` 교차검증 결과 반영
- `sdhci0` eMMC 8-bit 사용, `sdhci1` disable
- Linux boot source 기본 정책은 eMMC-first
- OSPI는 single-SPI safe fallback profile 유지
- USB0는 `USB2-only + OTG` 초기 bring-up 정책
- dual CPSW RGMII PHY 기본 연결

남은 TODO:

- PMIC/regulator binding
- reserved-memory 최종 layout
- CPSW reset/interrupt provider
- SERDES0 최종 routing policy
- TPM `U15`와 `U21` 정책

workspace projection:

- Linux source tree top-level DTS filename: `k3-am6412-cpu-brd-v03-pba.dts`
- companion DTSI는 현재 set 파일명을 유지한다.
