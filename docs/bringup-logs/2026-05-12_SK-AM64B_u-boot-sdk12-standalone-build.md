---
title: SK-AM64B U-Boot SDK12 Standalone Build Log
path: docs/bringup-logs/2026-05-12_SK-AM64B_u-boot-sdk12-standalone-build.md
board: SK-AM64B
sdk_version: 12.00.00.07.04
u_boot_version: ti-u-boot-2026.01+git
status: R5/A53 build completed, boot verification pending
---

# 2026-05-12 SK-AM64B U-Boot SDK12 Standalone Build Log

## 작업 목적

SK-AM64B 기준으로 TI Processor SDK Linux AM64x `12.00.00.07.04`의 기본 U-Boot 소스를 직접 빌드하여, TI prebuilt bootloader 대신 자체 빌드 산출물로 부팅 검증하기 위한 준비 작업을 수행했다.

이번 작업은 커스텀 보드 제작 전, 레퍼런스 보드에서 다음 능력을 확보하기 위한 사전 리허설이다.

```text
- U-Boot source tree 확인
- R5/A53 defconfig 구분
- tiboot3.bin / tispl.bin / u-boot.img 직접 빌드
- SDK standalone build 환경 문제 해결
- prebuilt artifact와 자체 build artifact 비교
```

## 작업 위치

```text
SDK root:
~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04

U-Boot source:
~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/board-support/ti-u-boot-2026.01+git

Build output:
~/ti/am64x/build/u-boot-sdk12

Final artifacts:
~/ti/am64x/build/u-boot-sdk12/artifacts
```

## 확인된 환경

```text
Host arch:
x86_64

Host OS:
Ubuntu 22.04.5 LTS

Python:
3.10.12

Git:
2.34.1

Processor SDK:
12.00.00.07.04

U-Boot:
ti-u-boot-2026.01+git

U-Boot branch:
ti-u-boot-2026.01

U-Boot commit:
2549829c
```

## 확인된 SDK 구성

```text
board-support/
├── extra-drivers/
├── k3-respart-tool/
├── optee-os-4.9.0+git/
├── prebuilt-images/
├── ti-linux-kernel-6.18.13+git-ti/
├── ti-u-boot-2026.01+git/
└── trusted-firmware-a-2.14+git/
```

확인된 U-Boot defconfig:

```text
configs/am64x_evm_a53_defconfig
configs/am64x_evm_r5_defconfig
```

확인된 AM64x 관련 U-Boot 파일:

```text
arch/arm/dts/k3-am642-r5-sk.dts
arch/arm/dts/k3-am642-sk-u-boot.dtsi
arch/arm/dts/k3-am64-sk-lp4-1600MTs.dtsi
arch/arm/dts/k3-am64x-binman.dtsi
board/ti/am64x/
board/ti/am64x/am64x.env
configs/am64x_evm_a53_defconfig
configs/am64x_evm_r5_defconfig
```

## 확인된 prebuilt image

```text
prebuilt-images/am64xx-evm/bl31.bin
prebuilt-images/am64xx-evm/bl32.bin
prebuilt-images/am64xx-evm/ti-sysfw
prebuilt-images/am64xx-evm/tiboot3.bin
prebuilt-images/am64xx-evm/tispl.bin
prebuilt-images/am64xx-evm/u-boot.img
```

`tiboot3` 계열 prebuilt 파일:

```text
tiboot3-am64x-gp-evm.bin
tiboot3-am64x_sr2-hs-evm.bin
tiboot3-am64x_sr2-hs-fs-evm.bin
tiboot3-am64xx-evm-k3r5.bin
tiboot3.bin
```

SK-AM64B는 HS-FS silicon 기반 보드이므로 자체 artifact 수집 시 다음 파일을 사용했다.

```text
tiboot3-am64x_sr2-hs-fs-evm.bin -> tiboot3.bin
```

## 빌드 중 발생한 문제와 해결

### 1. A53 build 중 `-lgcc` link 실패

증상:

```text
aarch64-oe-linux-ld: cannot find -lgcc: No such file or directory
```

발생 위치:

```text
lib/efi_loader/helloworld_efi.so
lib/efi_loader/smbiosdump_efi.so
lib/efi_loader/dtbdump_efi.so
```

원인:

```text
U-Boot EFI app link 단계에서 PLATFORM_LIBGCC가 -lgcc 형태로 처리되었으나,
Yocto SDK standalone 환경에서 aarch64 linker가 libgcc.a 검색 경로를 알지 못함.
```

해결:

```bash
export LIBGCC_FILE=$(find $SDK/linux-devkit -name "libgcc.a" | grep -E "aarch64|aarch64-oe-linux" | head -1)
```

A53 build 시:

```bash
PLATFORM_LIBGCC="$LIBGCC_FILE"
```

확인된 libgcc:

```text
$SDK/linux-devkit/sysroots/aarch64-oe-linux/usr/lib/aarch64-oe-linux/15.2.0/libgcc.a
```

### 2. SDK environment source 후 Python setuptools 문제

증상:

```text
ModuleNotFoundError: No module named 'setuptools'
```

원인:

```text
linux-devkit/environment-setup-aarch64-oe-linux를 source하면
python3가 SDK sysroot 내부 Python으로 잡힘.
해당 Python 환경에는 setuptools가 없었음.
```

확인된 SDK Python:

```text
linux-devkit/sysroots/x86_64-arago-linux/usr/bin/python3
```

해결:

```text
SDK environment-setup을 source하지 않음.
PYTHON=/usr/bin/python3 를 build command에 명시.
```

### 3. SDK environment source 후 host build가 target sysroot header 참조

증상:

```text
fatal error: bits/timesize-32.h: No such file or directory
```

발생 위치:

```text
HOSTCC tools/image-host.o
```

원인:

```text
host tool build가 target sysroot include path를 참조함.
U-Boot build는 host tool과 target binary를 함께 빌드하므로
Yocto SDK environment를 통째로 source하면 환경이 오염될 수 있음.
```

해결:

```text
clean shell에서 SDK environment-setup 없이 toolchain prefix만 수동 지정.
```

### 4. `efi_initrd_register` undefined reference

증상:

```text
undefined reference to `efi_initrd_register'
```

원인:

```text
EFI_LOAD_FILE2_INITRD를 비활성화하면 efi_load_initrd 관련 object가 빠지지만,
efi_helper.c에서 efi_initrd_register를 계속 참조하여 최종 link 실패.
```

해결:

```bash
$UBOOT_DIR/scripts/config --file $A53_OUT/.config \
  -e EFI_LOAD_FILE2_INITRD
```

## 최종 build config 조정

A53 build에서 사용한 config 조정:

```bash
$UBOOT_DIR/scripts/config --file $A53_OUT/.config \
  -d BOOTEFI_HELLO_COMPILE \
  -d CMD_BOOTEFI_SELFTEST \
  -d EFI_SELFTEST \
  -e EFI_LOAD_FILE2_INITRD
```

기대 상태:

```text
# CONFIG_BOOTEFI_HELLO_COMPILE is not set
# CONFIG_CMD_BOOTEFI_SELFTEST is not set
CONFIG_EFI_LOAD_FILE2_INITRD=y
```

## 최종 Artifact

경로:

```text
~/ti/am64x/build/u-boot-sdk12/artifacts
```

파일:

```text
tiboot3.bin
tispl.bin
u-boot.img
```

크기:

```text
tiboot3.bin  531K
tispl.bin    1.1M
u-boot.img   1.3M
```

## TI prebuilt와 크기 비교

```text
prebuilt tiboot3.bin  506K
prebuilt tispl.bin    1.1M
prebuilt u-boot.img   1.6M

built    tiboot3.bin  531K
built    tispl.bin    1.1M
built    u-boot.img   1.3M
```

`u-boot.img` 크기 차이는 EFI hello/selftest 관련 옵션 비활성화 영향으로 판단한다.

## 현재 상태

```text
R5 build:
  완료

A53 build:
  완료

Artifact 수집:
  완료

SD 카드 boot partition 교체:
  미완료

SK-AM64B 실제 부팅 검증:
  미완료
```

## 다음 Action Item

```text
1. 생성된 tiboot3.bin / tispl.bin / u-boot.img를 SD boot partition에 배치
2. SK-AM64B를 SD boot mode로 부팅
3. UART boot log 저장
4. TI prebuilt boot log와 비교
5. U-Boot prompt 진입 여부 확인
6. Linux kernel boot 여부 확인
```

## 부팅 검증 시 확인할 로그 포인트

```text
- U-Boot SPL version/date
- SoC: AM64X SR2.0 HS-FS
- Board: AM64B-SKEVM rev A
- DRAM: 2 GiB
- Trying to boot from MMC2
- Authentication passed
- tispl.bin load 성공 여부
- u-boot.img load 성공 여부
- U-Boot prompt 진입 여부
- kernel Image / DTB load 여부
- Starting kernel ...
```

## 실패 시 의심 지점

### 아무 로그도 없음

```text
- tiboot3.bin silicon/security type 불일치
- SD boot partition 파일명/배치 문제
- boot mode 설정 문제
- SD card read 문제
```

### SPL 로그 후 tispl.bin 실패

```text
- SD/MMC 접근 문제
- tispl.bin 파일명 문제
- boot partition FAT 문제
```

### U-Boot proper 진입 실패

```text
- u-boot.img 문제
- A53 build config 문제
- TF-A / OP-TEE packaging 문제
```

### U-Boot prompt 이후 kernel 실패

```text
- uEnv.txt 문제
- bootcmd/env 차이
- kernel Image 경로 문제
- DTB 경로 문제
- rootfs partition 문제
```

## Knowledge

- AM64x U-Boot standalone build에서는 R5 build와 A53 build를 분리해서 봐야 한다.
- R5 build는 `tiboot3.bin` 계열을 만든다.
- A53 build는 `tispl.bin`, `u-boot.img`를 만든다.
- SDK environment-setup은 U-Boot standalone build에서 host tool build를 오염시킬 수 있다.
- `PLATFORM_LIBGCC`에 `libgcc.a` 절대경로를 명시하면 EFI app link 단계의 `-lgcc` 문제를 우회할 수 있다.

## Decision

- SDK environment-setup은 사용하지 않고 clean shell에서 빌드한다.
- A53 build에서 `PYTHON=/usr/bin/python3`를 명시한다.
- A53 build에서 `PLATFORM_LIBGCC`를 명시한다.
- EFI hello/selftest는 비활성화한다.
- `EFI_LOAD_FILE2_INITRD`는 유지한다.

## Open Question

- 생성한 bootloader 3종이 SK-AM64B에서 실제로 정상 부팅되는지 아직 미검증.
- Windows 환경에서 SD boot partition에 직접 파일 write가 거부되는 문제가 있었으며, 우회 방법은 별도 검토 중.
