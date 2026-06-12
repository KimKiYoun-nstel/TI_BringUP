# SBL OSPI Linux Workspace Base Note

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` early-boot 작업을
현재 시점에서 어떤 workspace 상태를 base로 볼지 정리한다.

## 현재 base 분류

### 1. 본질 수정

- LPDDR4 reginit 적용 workspace file
- 경로: `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h`
- sha256: `791481fcab5c1761df4eca015b908dc09d378a7347b368cf9eaebcddaf74c9e5`

의미:

- SK-AM64B 실보드 LPDDR4와 일치하는 DDR register init 자산
- `BL31/BL32/BL33 destination populate` 성공의 직접 기반

### 2. 현재 검증된 SBL workspace delta

- `sbl_ospi_linux` `example.syscfg`
  - 경로: `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/example.syscfg`
  - sha256: `fe45dede9b1fa05bca17538cdeab2fd5b528a05363e2183837eb52b5694f1812`

핵심 의미:

- `main.c`와 DDR/bootloader 공통부에 들어갔던 일시적 marker/diag는 정리했다.
- `example.syscfg`는 `APPIMAGE` DDR window를 `NonCached + no-exec`로 둔다.
- 즉 현재 clean workspace base의 source delta는 이 `.syscfg`와 LPDDR4 reginit asset 두 축이다.

### 3. repo-managed patch 상태

- patch: `bsp/mcu-plus/patches/0002-am64x-sbl-ospi-linux-keep-lp4-dual-boot-workspace-base.patch`

역할:

- 현재 clean `example.syscfg` delta를 main repo visibility 아래 둔다.
- LPDDR4 reginit table 자체는 standalone asset로 별도 관리한다.

## 현재 판단

확정:

- early-boot closure 범위는 `dual-boot까지` 이다.
- R5F firmware SHM/RPMsg 동작과 Linux userspace app 정합성은 다음 범위다.

주의:

- 이번 정리에서 early-boot debug marker/diag는 workspace source에서 제거했다.
- 즉 현재 repo 기준 active base는 **LPDDR4 asset + clean syscfg delta** 로 본다.
