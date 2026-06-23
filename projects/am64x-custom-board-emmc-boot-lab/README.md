# AM64x Custom Board eMMC Boot Lab

## 목적

이 프로젝트는 `cpu_brd_v03_pba_260511` 커스텀 보드의 eMMC boot bring-up 실험을 별도 관리하기 위한 작업 구역이다.

이 프로젝트는 DTS 생성 workflow 자체가 아니라, 그 workflow에서 나온 DTS set와 build 산출물을 이용해 실제 boot chain을 검증하고 원인을 분리하는 데 목적이 있다.

## 범위

- OSPI known-good bootloader + eMMC kernel/DTB/rootfs 조합 검증
- eMMC boot0 raw bootloader write 검증
- current custom kernel/DTB/modules 조합 문제 원인 분리
- UART 기반 reboot/boot evidence 수집
- 복구 경로와 원복 절차 기록

## canonical log 원칙

- 이 프로젝트의 custom board reboot/boot evidence는 `logs/runtime_log`를 canonical로 보지 않는다.
- custom board의 canonical raw log는 `projects/am64x-custom-board-emmc-boot-lab/logs/` 아래에 순수 UART 출력만 저장한다.

## 현재 남겨둔 자산

- raw UART reboot log:
  - `logs/2026-06-19_ospi-uboot_current-kernel-final-fixed-dtb_uart-reboot.log`
- 세션 요약:
  - `docs/2026-06-19_session-summary.md`
- build artifact hash 목록:
  - `artifacts/2026-06-19_build-artifacts.sha256`

## 현재 소스/문서 연관 경로

- Linux DTS set:
  - `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/`
- U-Boot DTS set:
  - `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/`
- build helper:
  - `tools/build/build-custom-board-linux.sh`
  - `tools/build/build-custom-board-u-boot.sh`
- eMMC deploy helper:
  - `tools/install/install-custom-board-emmc.sh`

## 현재 보드 최종 상태

- bootloader source: OSPI known-good
- active kernel/DTB/modules: deploy 이전 backup 상태로 원복 완료
- reboot 후 login/SSH 재확인 완료

## 다음 액션

1. restore 상태를 baseline으로 보고 eMMC bootloader 재검증 전략을 다시 세운다.
2. current custom kernel/DTB/modules를 다시 적용할 때는 이 프로젝트 문서 기준으로 단계별로 분리 검증한다.
3. `USB/SERDES`, `ICSSG/PRUSS`, `remoteproc`, `SA2UL` 재활성화는 별도 실험 단위로 다룬다.
