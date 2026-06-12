# 2026-06-11 SK-AM64B SBL OSPI Linux LPDDR4 First Boot Success

## 목적

이 문서는 SK-AM64B에서 `MCU+ SDK sbl_ospi_linux` 계열 실험 중,
`LPDDR4 DDR reginit` 반영 후 처음으로 OSPI 기준 Linux 부팅에 성공한 로그와 판단을 정리한다.

## 성공 조건

```text
SBL: local sbl_ospi_linux_a53only
DDR reginit: U-Boot SK LPDDR4 dtsi 기반으로 교체한 MCU+ board_ddrReginit.h
BL31/BL32/BL33 destination: DDR 적재 성공
BL32: init_ti_sci keep, secure_boot_information/HUK only bypass
결과: U-Boot SPL -> U-Boot -> Linux boot -> login prompt 도달
```

## 핵심 판단

### 원인

기존 MCU+ SDK 공용 DDR 자산은 아래처럼 `DDR4`로 생성되어 있었다.

파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h`

기존 header:

```c
#define DDR_TYPE DDR4
```

반면 SK-AM64B의 공식 U-Boot R5 자산은 아래 LPDDR4 dtsi를 사용한다.

파일:

- `workspace/ti-u-boot-sdk12/arch/arm/dts/k3-am642-r5-sk.dts`
- `workspace/ti-u-boot-sdk12/arch/arm/dts/k3-am64-sk-lp4-1600MTs.dtsi`

즉 SBL 경로가 SK-AM64B 실물 메모리와 맞지 않는 DDR4 reginit를 사용하고 있었던 것이 핵심 문제였다.

### 적용

U-Boot SK LPDDR4 dtsi의 `DDRSS_CTL_*`, `DDRSS_PI_*`, `DDRSS_PHY_*` 값을
MCU+ SDK `board_ddrReginit.h` 형식으로 변환해 적용했다.

### 결과

```text
0x80080000 plain write 성공
0x9e800000 plain write 성공
BL33/BL32 destination populate 성공
BL32 init 이후 U-Boot SPL 진입 성공
Linux boot 및 login prompt 성공
```

## 다음 목표

1. `sbl_ospi_linux_a53only` 제거
2. 원본 `sbl_ospi_linux`에서 R5F/A53 동시 부팅 복구
3. Linux attach / RPMsg 검증
