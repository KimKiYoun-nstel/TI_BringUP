# 2026-06-19 Session Summary

## 배경

커스텀 보드용 current custom bootloader/kernel/DTB/modules를 eMMC에 반영한 뒤 다음 두 문제가 확인되었다.

1. eMMC boot 모드에서는 custom SPL이 `spl: could not initialize mmc. error: -22`로 실패
2. OSPI known-good bootloader로 우회해도 eMMC의 current custom kernel/DTB/modules 조합에서 Linux가 정상 shell까지 가지 못함

## 이번 세션 핵심 판단

### 1. SPL 문제

- custom SPL은 `boot0`의 `tiboot3.bin`까지는 읽었지만, SPL 단계의 MMC init이 실패했다.
- U-Boot DTS 쪽에서 `memory@80000000`의 `bootph-pre-ram` 가시성 문제를 먼저 수정해 재빌드했다.

관련 수정:

- `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-u-boot-final.dtsi`

### 2. current custom Linux 조합 문제

- custom board current kernel/DTB 자체가 전혀 부팅 불가한 것은 아니었다.
- 문제는 current DTB가 unresolved subsystem을 너무 많이 enable한 상태에서 current modules가 autoload/probe되던 경로였다.
- crash/hang에 직접 걸린 축:
  - `remoteproc` / `M4`
  - `R5 remoteproc`
  - `SERDES / USB / wiz`
  - `PRUSS / ICSSG`
  - `SA2UL`

### 3. backup 상태의 의미

- `deploy 이전 backup`은 deploy 직전 target에 있던 `/boot`와 `/lib/modules/6.18.13-gc21449208550-dirty`의 스냅샷이다.
- 이 backup kernel은 release 문자열이 current custom kernel과 같지만, 이미지 내용은 다르다.
- 따라서 backup kernel에 current modules를 붙이면 mismatch가 날 수 있었다.

## current custom DT fix

bringup-default 단계에서 다음을 disable하도록 DTS를 수정했다.

- `usbss0`
- `usb0`
- `serdes_ln_ctrl`
- `serdes_wiz0`
- `serdes0`
- `icssg0`
- `icssg1`
- `crypto` (`sa2ul`)
- `main_r5fss0/1` 및 각 core
- `mcu_m4fss`

추가로 `k3-am64-ti-ipc-firmware.dtsi`가 include 마지막에 remoteproc/M4를 다시 `okay`로 되살리기 때문에, `k3-am6412-custom-final.dts`의 include 뒤에서 다시 disable override를 넣었다.

관련 수정:

- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-final-overrides.dtsi`
- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/k3-am6412-custom-final.dts`
- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/README.md`

## current custom 조합 검증 결과

- `current kernel + final fixed DTB + current modules` 조합으로
  - `login:` 도달 확인
  - UART root login 성공
  - SSH 성공

즉 current custom Linux 조합 문제는 DT bringup 범위 정리로 일단 해결됐다.

## raw UART reboot log 저장

이번 세션에서 정상 동작이 확인된 조합의 reboot 로그를 순수 UART 출력 기준으로 다음 파일에 저장했다.

- `projects/am64x-custom-board-emmc-boot-lab/logs/2026-06-19_ospi-uboot_current-kernel-final-fixed-dtb_uart-reboot.log`

이 파일은 custom board용 canonical raw log로 간주한다.

## 최종 원복 상태

사용자 요청에 따라 최종적으로 target는 deploy 이전 backup 상태로 원복했다.

- `/boot/Image` -> `/root/ti-bringup-backup/20260619_160803/boot/Image`
- `/boot/dtb/ti/k3-am642-sk.dtb` -> `/root/ti-bringup-backup/20260619_160803/boot/k3-am642-sk.dtb`
- `/lib/modules/6.18.13-gc21449208550-dirty` -> `/root/ti-bringup-backup/20260619_160803/modules/6.18.13-gc21449208550-dirty`

원복 후 확인 결과:

- kernel: `6.18.13-gc21449208550-dirty #1`
- boot ID: `be05b427-db7c-4924-8864-4fbd6d31fe0a`
- UART login 성공
- SSH 성공

## 메모

- current custom final-fix 상태는 target recovery 디렉터리에 임시 보존돼 있을 수 있으나, 현재 active 상태는 아니다.
- eMMC bootloader 검증은 restore 상태를 baseline으로 다시 시작하는 것이 안전하다.
