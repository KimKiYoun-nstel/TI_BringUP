# 2026-06-09 SK-AM64B R5F Early Boot OP-TEE Visibility Build

## 목적

이 문서는 SK-AM64B SBL early boot local fullchain에서
`BL31` 이후 UART 가시성을 높이기 위해 **verbose OP-TEE variant** 를 생성한 절차와 산출물을 기록한다.

## 배경

이전 local fullchain boot에서는 다음이 확인되었다.

- local-built `BL31` 이 실제로 반영됨
- boot는 `BL31` banner까지 도달함
- 이후 `U-Boot SPL` / `login:` 이 보이지 않음

추가 확인 결과 OP-TEE K3 platform 기본 설정은 다음과 같았다.

- `CFG_CONSOLE_UART ?= 0`
- `CFG_CONSOLE_RUNTIME_SET ?= y`
- `CFG_CONSOLE_RUNTIME_LOG_LEVEL ?= 0`

즉 기본 build는 런타임 시점에 UART console visibility를 낮출 가능성이 있다.

## 이번 세션에서 적용한 접근

소스 수정 대신 build override 방식으로
**별도 verbose OP-TEE output tree** 를 생성했다.

핵심 override:

```text
CFG_BUILD_IN_TREE_TA=n
CFG_CONSOLE_RUNTIME_SET=n
CFG_CONSOLE_RUNTIME_LOG_LEVEL=4
CFG_TEE_CORE_LOG_LEVEL=4
CFG_TEE_CORE_DEBUG=y
CFG_TEE_TA_LOG_LEVEL=4
CFG_DEBUG_INFO=y
CFG_CC_OPT_LEVEL=0
```

추가로 OP-TEE build 전에는 env의 `ARCH=arm64`를 제거하기 위해
`unset ARCH`를 유지했다.

## verbose OP-TEE 빌드

실행 개념:

```bash
source tools/env/sdk-12.00.00.07.04.env
unset ARCH
make \
  O=/home/nstel/ti/TI_Bringup/out/optee-verbose \
  CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
  CROSS_COMPILE32="$CROSS_COMPILE_ARMV7R" \
  CROSS_COMPILE64="$CROSS_COMPILE_AARCH64" \
  PLATFORM=k3-am64x \
  CFG_ARM64_core=y \
  CFG_BUILD_IN_TREE_TA=n \
  CFG_CONSOLE_RUNTIME_SET=n \
  CFG_CONSOLE_RUNTIME_LOG_LEVEL=4 \
  CFG_TEE_CORE_LOG_LEVEL=4 \
  CFG_TEE_CORE_DEBUG=y \
  CFG_TEE_TA_LOG_LEVEL=4 \
  CFG_DEBUG_INFO=y \
  CFG_CC_OPT_LEVEL=0
```

산출물:

- `out/optee-verbose/core/tee-pager_v2.bin`

확인값:

- size: `758528`
- sha256: `094b1ec998adc2851b5a0e663e8fe92dfa7c0ac25d2204c3a56bed4e105ec362`

문자열 확인:

- `OP-TEE`
- `WARNING: This OP-TEE configuration might be insecure!`
- `4.9.0-49-gf2a7ad063 ... Tue Jun 9 03:01:25 UTC 2026`

## verbose OP-TEE 기반 A53 chain 재빌드

verbose OP-TEE binary를 `TEE=` 입력으로 연결해 U-Boot A53를 다시 빌드했다.

산출물:

- `out/u-boot-local-a53chain-optee-verbose/a53/u-boot.img`
- `out/u-boot-local-a53chain-optee-verbose/a53/spl/u-boot-spl.bin`

확인값:

- `u-boot.img`
  - size: `1578531`
  - sha256: `7d66b5d228ef52474f1ec035d7181fc8e2d80d9d658b635204e1eedf5d055b0f`
- `spl/u-boot-spl.bin`
  - size: `363148`
  - sha256: `9626b746f2e4445e4d1b9f5ef2a794a50e4764ea1baada8e103ff8bea80714f5`

## verbose OP-TEE 기반 linux appimage 재생성

staging 구성:

- `bl31.bin` -> local TF-A output
- `bl32.bin` -> `out/optee-verbose/core/tee-pager_v2.bin` alias
- `u-boot-spl.bin-am64xx-evm` -> verbose A53 chain SPL alias
- `u-boot.img` -> verbose A53 chain `u-boot.img`

산출물:

- `out/r5f-early-boot/linux-appimage-build-optee-verbose/linux.mcelf.hs_fs`
- `out/r5f-early-boot/linux-appimage-build-optee-verbose/u-boot.img`

확인값:

- `linux.mcelf.hs_fs`
  - size: `1167506`
  - sha256: `66c6bd745504128f6ae701db1ae42ce3a6dbce328b544a4a36bf8ca372120e0d`
- copied `u-boot.img`
  - size: `1578531`
  - sha256: `7d66b5d228ef52474f1ec035d7181fc8e2d80d9d658b635204e1eedf5d055b0f`

## 다음 flash용 cfg

다음 retry에서는 아래 cfg를 사용한다.

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_optee-verbose.cfg`

## 현재 판단

이 variant의 목적은 boot success를 직접 보장하는 것이 아니라,
`BL31` 이후 secure-world / OP-TEE / handoff 구간에서
**UART에 더 많은 증적을 노출**시키는 것이다.

즉 다음 부팅 판정 포인트는 다음과 같다.

```text
BL31 이후 OP-TEE 로그가 추가로 보이는가?
U-Boot SPL banner가 보이는가?
여전히 무출력/정지인가?
```
