# 2026-06-12 SK-AM64B SBL OSPI Linux Dual-Boot OSPI Write

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` early-boot 작업에서
LPDDR4 기반 dual-boot image set을 `U-Boot tftp + sf write`로 기록하고
실제 Linux boot까지 확인한 provenance를 남긴다.

## 이번 세션 범위

포함:

- `sbl_ospi_linux` 기본 dual-boot 경로로 복귀
- LPDDR4 reginit workspace base 유지
- `0x0 / 0x80000 / 0x300000 / 0x800000` OSPI write
- Linux login prompt까지 boot 확인

제외:

- custom early-boot R5F firmware의 SHM heartbeat 기능 closure
- baseline Linux `rpmsg_json` app과의 왕복 통신 closure

## 기록한 image set

TFTP dir:

- `tftp/am64x-sbl-ospi-lp4-dualboot-20260612/`

### `0x000000` SBL

- file: `sbl_ospi_linux.release.hs_fs.tiimage`
- source: `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang/sbl_ospi_linux.release.hs_fs.tiimage`
- size: `341469`
- sha256: `97ab1c901d581dfbb6adcf7a18711f2e4c8b266211630b8db9782cb6b831fc6a`
- U-Boot CRC before/after: `a63fc4b9`

### `0x080000` R5F multicore appimage

- file: `r5f-early-heartbeat.mcelf.hs_fs`
- source: `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`
- size: `42082`
- sha256: `a521478f19664486a74ebd46dd7d61f0d00139dca9373d4006c93adc1fc4fcda`
- U-Boot CRC before/after: `59e9b325`

### `0x300000` U-Boot proper

- file: `u-boot.img`
- source lineage: current success-compatible A53 chain copy in `tftp/am64x-sbl-ospi-lp4-dualboot-20260612/u-boot.img`
- size: `1578531`
- sha256: `7d66b5d228ef52474f1ec035d7181fc8e2d80d9d658b635204e1eedf5d055b0f`
- U-Boot CRC before/after: `188e56f3`

### `0x800000` Linux appimage

- file: `linux.mcelf.hs_fs`
- source lineage: `out/r5f-early-boot/linux-appimage-build-bl31bl32diag-v2/linux.mcelf.hs_fs`
- size: `899866`
- sha256: `6e3fe3314f6e44eaa9783f745a8e6719b37e3d4ba66a5d82d0bd9735fa82e420`
- U-Boot CRC before/after: `138df1e2`

## boot 결과

확인된 것:

- `logs/runtime_log`에 `SBL_LP4_DUAL_BOOT_V1` marker 기록
- `App_loadLinuxImages status=0`
- `App_loadImages status=0`
- `Starting linux and RTOS/Baremetal applications [SBL_LP4_DUAL_BOOT_V1]`
- Linux login prompt 도달

remoteproc 관련 핵심 log:

- `remoteproc1: 78000000.r5f ... now attached`
- `remoteproc2: 78200000.r5f ... now attached`
- `remoteproc3: 78400000.r5f ... now up`
- `remoteproc4: 78600000.r5f ... now up`

## 후속 정리

이번 write provenance 이후 workspace에서는 다음을 추가 정리했다.

1. LPDDR4 `board_ddrReginit.h`를 repo-managed standalone asset로 반입
2. `sbl_ospi_linux` temporary debug marker/diag를 workspace source에서 제거
3. clean source delta는 `example.syscfg` noncached/no-exec policy만 남김

## 현재 경계 해석

이번 provenance가 닫는 범위:

```text
LPDDR4 기반 SBL OSPI Linux dual-boot image set 준비
  -> U-Boot tftp + sf write
  -> Linux boot 성공
```

이번 provenance가 닫지 않는 범위:

```text
custom early-boot R5F firmware의 intended SHM/RPMsg 기능 검증
baseline Linux RPMsg app과의 정상 round-trip 검증
```
