# 2026-06-18 CPU_BRD_V03_PBA_260511 Deploy Handoff

## 목적

이 문서는 현재 세션에서 완료한 커스텀 보드용 bootloader / kernel build 결과를 정리하고, 다음 세션에서 실제 deploy 및 eMMC boot 검증을 이어가기 위한 handoff 메모다.

## 이번 세션에서 완료한 항목

1. `tools/custom_board_dts_workflow`의 `final` 산출물을 기준으로 root repo 관리 DTS set를 정리했다.
2. Linux build 입력 DTS set를 `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/` 아래에 추가했다.
3. U-Boot/SPL build 입력 DTS set를 `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/` 아래에 추가했다.
4. root-managed DTS set를 workspace source tree에 투영하는 helper를 추가했다.
5. 커스텀 보드 전용 Linux/U-Boot build helper를 추가했다.
6. 실제 custom board bootloader trio와 kernel/DTB 빌드를 성공시켰다.
7. eMMC boot partition 크기가 `boot0=4MiB`, `boot1=4MiB` 임을 runtime 정보로 확인하고, 현재 U-Boot raw layout candidate를 small-layout 기준으로 조정했다.

## 현재 기준 자산 경로

### DTS / config 기준 경로

- Linux DTS set: `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/`
- U-Boot DTS set: `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/`
- U-Boot config override: `bsp/u-boot/configs/custom-board/cpu_brd_v03_pba_260511/`
- workflow guide: `docs/common/CUSTOM_BOARD_DTS_WORKFLOW.md`

### helper 경로

- DTS sync helper: `tools/prepare/sync-custom-board-dts-set-to-workspace.sh`
- Linux build helper: `tools/build/build-custom-board-linux.sh`
- U-Boot build helper: `tools/build/build-custom-board-u-boot.sh`

### build 산출물 경로

- Linux artifacts: `out/kernel-custom-board/cpu_brd_v03_pba_260511/bringup-default/artifacts/`
- U-Boot artifacts: `out/u-boot-custom-board/cpu_brd_v03_pba_260511/bringup-default/artifacts/`

현재 확인된 핵심 산출물:

- `Image`
- `k3-am6412-cpu-brd-v03-pba.dtb`
- `tiboot3.bin`
- `tispl.bin`
- `u-boot.img`
- `modules/`

## 이번 세션 기준 확정 사실

1. Linux boot 정책은 현재 `eMMC-first`다.
2. 현재 보드의 eMMC는 runtime 기준 `mmcblk0` 약 3.64 GiB user area를 가진다.
3. eMMC boot partition은 `mmcblk0boot0=4MiB`, `mmcblk0boot1=4MiB`다.
4. U-Boot raw bootloader layout candidate는 현재 다음 값으로 맞춰져 있다.

```text
tiboot3.bin @ 0x0
tispl.bin   @ 0x400
u-boot.img  @ 0x1400
```

5. 이 offset은 deploy 편의용 값이 아니라, 현재 build override와 일치해야 하는 boot chain 위치 정보다.
6. rootfs는 기존 보드의 `mmcblk0p2`를 재사용하는 방향으로 본다. 단 다음 세션에서 새 kernel과 modules 반영 여부를 같이 확인해야 한다.
7. 보드는 Ethernet으로 접근 가능했고, 확인 시점 기준 SSH 접속 정보는 다음과 같았다.

```text
IP: 192.168.0.154
login: root
password: 없음
```

## 아직 남아 있는 deploy 작업

1. active eMMC boot partition이 `boot0`인지 `boot1`인지 확인 필요
2. `tiboot3.bin`, `tispl.bin`, `u-boot.img` 실제 write 절차 정리 필요
3. `Image`, `DTB`, `modules`를 기존 eMMC layout에 어떻게 반영할지 결정 필요
4. bootloader write 후 boot mode를 eMMC로 바꿔 cold boot 검증 필요
5. UART 기준 boot evidence 수집 필요

## 다음 세션 권장 순서

1. UART와 SSH 둘 다 확보한다.
2. 현재 Linux에서 eMMC 상태를 다시 확인한다.
3. `mmc partconf` 또는 동등 정보로 active boot partition을 확인한다.
4. 기존 eMMC user area의 boot asset 위치와 rootfs mount 상태를 확인한다.
5. bootloader trio를 선택한 boot partition에 raw write 한다.
6. `Image`, `DTB`, `modules`를 기존 rootfs/boot layout에 맞게 반영한다.
7. boot mode switch를 eMMC로 변경한다.
8. 전원 재인가 후 UART에서 다음을 확인한다.

```text
Boot ROM -> tiboot3.bin -> tispl.bin -> u-boot.img -> Linux kernel -> rootfs mount
```

9. Linux prompt 도달 후 `uname -a`, `/proc/cmdline`, `mount`, `lsblk`, `dmesg` 핵심 증거를 수집한다.

## 다음 세션에서 먼저 볼 파일

- `docs/common/CUSTOM_BOARD_DTS_WORKFLOW.md`
- `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/README.md`
- `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default/README.md`
- `bsp/u-boot/configs/custom-board/cpu_brd_v03_pba_260511/README.md`
- `tools/build/build-custom-board-linux.sh`
- `tools/build/build-custom-board-u-boot.sh`

## 메모

- 현재 세션 범위는 build 완료까지다. 실제 deploy/write 및 boot success 검증은 아직 하지 않았다.
- rootfs는 새로 재생성하지 않는 전제로 진행한다.
- deploy 단계에서는 build 설정의 raw offset과 실제 eMMC write offset이 반드시 일치해야 한다.
