# U-Boot DTS Set: bringup-default

이 set는 `cpu_brd_v03_pba_260511` 보드의 U-Boot/SPL bring-up 기본 build 입력이다.

source workflow final:

- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/uboot_spl/final/k3-am6412-custom-u-boot-final.dtsi`
- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/uboot_spl/base/k3-am6412-custom-u-boot-spl.dtsi`
- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/generated/uboot_spl/facts/k3-am6412-custom-early-pinmux.facts.dtsi`

반영 정책:

- `main_uart0` early console
- `sdhci0` eMMC first boot candidate
- `ospi0` single-SPI safe fallback profile
- `usb0` peripheral candidate
- `k3-am64x-binman.dtsi` include 유지
- Linux handoff 기본 정책은 eMMC-first로 본다.
- 4MiB eMMC boot partition 기준 small raw layout candidate를 사용한다.
- SPL wrapper가 재사용하는 top-level memory node에 `bootph-pre-ram`을 U-Boot DTS 쪽에서 다시 부여한다.

남은 TODO:

- LPDDR4 timing/training include chain
- octal/DQS profile 재전환 시점
- SERDES0 / USB3 / PCIe 정책
- eMMC boot 재시도 시 `dram_init_banksize()` 경고와 MMC init 연동 여부 재확인

workspace projection:

- A53 top-level DTS filename: `dts/upstream/src/arm64/ti/k3-am6412-cpu-brd-v03-pba.dts`
- A53 U-Boot quirks DTSI filename: `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-u-boot.dtsi`
- R5 SPL top-level DTS filename: `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-r5.dts`
- R5는 현재 임시로 `k3-am64-sk-lp4-1600MTs.dtsi` DDR baseline을 쓰는 wrapper가 필요하다.

boot source policy:

- 현재 build helper 기준 U-Boot boot command baseline은 `CONFIG_BOOTCOMMAND="run envboot; run bootcmd_ti_mmc; bootflow scan -lb"`다.
- TI 공통 MMC env의 `mmcdev=0`를 따르므로, 현재 custom board bringup-default는 `mmc0 -> sdhci0 -> eMMC`를 Linux boot 1순위로 본다.
- `ospi0`는 boot media hardware candidate이지만, 현재 rootfs / kernel handoff 기본 정책은 아니다.
- 현재 eMMC boot partition size runtime fact는 `boot0 = 4MiB`, `boot1 = 4MiB`다.
- 현재 small raw layout candidate는 `tiboot3 @ 0x0`, `tispl @ 0x400`, `u-boot.img @ 0x1400`이다.
