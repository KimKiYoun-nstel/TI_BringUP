# SBL OSPI Linux LPDDR4 Alignment Note

## 목적

이 문서는 SK-AM64B에서 `MCU+ SDK sbl_ospi_linux` 실험 시,
왜 기본 `board_ddrReginit.h` 대신 SK용 LPDDR4 자산을 반영해야 했는지 정리한다.

## 공식 자산 근거

### U-Boot SK R5 경로

파일:

- `workspace/ti-u-boot-sdk12/arch/arm/dts/k3-am642-r5-sk.dts`

핵심 include:

```dts
#include "k3-am64-sk-lp4-1600MTs.dtsi"
```

### LPDDR4 dtsi

파일:

- `workspace/ti-u-boot-sdk12/arch/arm/dts/k3-am64-sk-lp4-1600MTs.dtsi`

명시값:

```text
DDR Type: LPDDR4
F0 = 50MHz    F1 = 800MHz    F2 = 800MHz
Density (per channel): 16Gb
Number of Ranks: 1
```

### MCU+ SDK 공용 reginit

파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h`

기존값:

```c
#define DDR_TYPE DDR4
```

## 실제 영향

DDR4 reginit 사용 시:

```text
DDR_init/firwall/bridge/authUpdate는 성공처럼 보임
하지만 R5F plain DDR write/memcpy는 실패
BL33/BL32 destination이 populate되지 않음
```

LPDDR4 reginit 교체 후:

```text
0x80080000 write 성공
0x9e800000 write 성공
BL33/BL32 populate 성공
U-Boot SPL -> U-Boot -> Linux boot 성공
```

## 현재 관리 원칙

1. SK-AM64B SBL OSPI Linux 실험에서는 LPDDR4 reginit를 source of truth로 본다.
2. MCU+ SDK 기본 공용 DDR4 reginit를 active 기준으로 간주하지 않는다.
3. 현재 standalone asset pin은 `bsp/mcu-plus/syscfg/board_ddrReginit_sk_am64b_lpddr4.h`를 따른다.
4. 현재 workspace/base pin 문서는 `bsp/mcu-plus/syscfg/sk-am64b-lpddr4-reginit-workspace-base.md`를 따른다.
5. 현재 실보드에서 검증된 clean `sbl_ospi_linux` base는 `bsp/mcu-plus/notes/sbl_ospi_linux_workspace_base.md`를 따른다.
6. 즉 early-boot closure의 본질 수정은 LPDDR4 reginit이고,
   임시 debug marker/diag는 정리한 뒤 clean base만 남긴다.
