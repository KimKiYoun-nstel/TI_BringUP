# 2026-06-25 Workspace Cleanup

## 목적

`cpu_brd_v03_pba_260511` custom board bring-up 과정에서 `workspace/` 소스 트리에 남아 있던 local DTS projection과 build integration hook을 정리하고, 장기 보관 가치가 있는 내용만 이 프로젝트와 `bsp/.../sets/bringup-default/` 자산으로 남긴다.

이번 정리의 목표는 다음과 같다.

- workspace dirty 상태를 다음 실험의 baseline으로 삼지 않기
- custom board 관련 source of truth를 root-managed DTS set와 프로젝트 문서로 일원화하기
- 추후 재투영이 필요할 때 어떤 파일이 왜 필요했는지 다시 찾을 수 있게 하기

## 정리 시점 사실

- U-Boot workspace: `workspace/ti-u-boot-sdk12`
- U-Boot branch: `base-sd-watchdog`
- U-Boot baseline tag: `ti-sdk-12.00.00.07.04-baseline`
- Linux workspace: `workspace/ti-linux-kernel-sdk12`
- Linux branch: `base-clean`
- Linux baseline tag: `ti-sdk-12.00.00.07.04-baseline`

## 이미 보존된 DTS payload

다음 파일들은 workspace untracked copy와 동일하거나, bringup-default 기준의 최신 authoritative copy로 이미 main repo에 승격되어 있다.

### Linux authoritative set

- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-final.dts`
- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-final-overrides.dtsi`
- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-pinmux.facts.dtsi`

### U-Boot authoritative set

- `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-u-boot-final.dtsi`
- `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-u-boot-spl.dtsi`
- `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-early-pinmux.facts.dtsi`

확인 결과, 다음 workspace 파일은 위 authoritative set와 동일했다.

- Linux `arch/arm64/boot/dts/ti/k3-am6412-custom-final-overrides.dtsi`
- Linux `arch/arm64/boot/dts/ti/k3-am6412-custom-pinmux.facts.dtsi`
- Linux `arch/arm64/boot/dts/ti/k3-am6412-cpu-brd-v03-pba.dts`
- U-Boot `arch/arm/dts/k3-am6412-custom-u-boot-spl.dtsi`
- U-Boot `arch/arm/dts/k3-am6412-custom-early-pinmux.facts.dtsi`
- U-Boot `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-u-boot.dtsi`

## workspace 전용 integration hook

다음 변경은 DTS payload 자체라기보다 build projection을 위해 workspace 안에만 임시로 넣어두었던 통합용 변경이다.

### Linux

- `arch/arm64/boot/dts/ti/Makefile`
  - `dtb-$(CONFIG_ARCH_K3) += k3-am6412-cpu-brd-v03-pba.dtb`
  - 의미: 커스텀 top-level DTS를 kernel DTB build 대상에 등록

### U-Boot

- `arch/arm/dts/k3-am64x-binman.dtsi`
  - `SPL_AM642_EVM_DTB`, `SPL_AM642_SK_DTB`를 `../r5/spl/dts/k3-am6412-cpu-brd-v03-pba-r5.dtb`로 재지정
  - `AM642_SK_DTB`를 `u-boot.dtb`로 재지정
  - 의미: 기존 AM642 target build 경로를 이용해 custom SPL/A53 DTB packaging을 우회 연결

이 hook들은 current bringup에서 유용했지만, 아직 upstream-friendly patch나 최종 build policy로 정리된 상태는 아니다. 따라서 이번에는 patch로 채택하지 않고 프로젝트 기록으로만 남긴다.

## workspace wrapper / projection 파일

다음 파일은 build tree projection을 위해서만 필요했던 wrapper 또는 copied top-level 파일이다.

### Linux

- `arch/arm64/boot/dts/ti/k3-am6412-cpu-brd-v03-pba.dts`

### U-Boot

- `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-r5.dts`
- `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-u-boot.dtsi`
- `dts/upstream/src/arm64/ti/k3-am6412-cpu-brd-v03-pba.dts`

특히 `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-r5.dts`는 다음 include chain을 사용했다.

- board top-level DTS: `k3-am6412-cpu-brd-v03-pba.dts`
- DDR baseline: `k3-am64-sk-lp4-1600MTs.dtsi`
- DDR common: `k3-am64-ddr.dtsi`
- U-Boot final quirks: `k3-am6412-cpu-brd-v03-pba-u-boot.dtsi`
- R5 common: `k3-am642-r5.dtsi`

## 주의사항

- U-Boot workspace의 `dts/upstream/src/arm64/ti/k3-am6412-cpu-brd-v03-pba.dts`는 정리 시점 기준으로 Linux authoritative final DTS보다 한 단계 뒤처져 있었다.
- 차이는 `#include "k3-am64-ti-ipc-firmware.dtsi"` 뒤의 `remoteproc` / `mcu_m4fss` 재-disable override가 빠져 있다는 점이다.
- 따라서 추후 재투영 시 Linux source of truth는 항상 `bsp/linux/.../k3-am6412-custom-final.dts`를 기준으로 삼아야 한다.

## 정리 방침

- authoritative DTS payload는 `bsp/.../sets/bringup-default/`를 기준으로 유지한다.
- eMMC boot 관찰, 원인 분리, 원복 판단은 이 프로젝트 문서를 기준으로 유지한다.
- workspace에는 custom board local projection을 남겨두지 않고 baseline clean 상태로 되돌린다.
- 다시 projection이 필요하면 이 문서의 integration hook와 wrapper 구성을 참고해 최소 파일만 재생성한다.
