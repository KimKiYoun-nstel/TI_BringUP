# AM64x U-Boot Standalone Build Procedure - Processor SDK 12

## 목적

TI Processor SDK Linux AM64x `12.00.00.07.04`에 포함된 U-Boot 소스를 사용해 AM64x 계열 부트로더 산출물을 standalone 방식으로 빌드하는 절차를 정리한다.

이 절차의 목표 산출물은 다음 3개이다.

```text
tiboot3.bin
tispl.bin
u-boot.img
```

AM64x 부팅 흐름에서 각 파일의 위치는 다음과 같다.

```text
Boot ROM
  -> tiboot3.bin
  -> tispl.bin
  -> u-boot.img
  -> Linux Kernel / DTB / RootFS
```

## 기준 SDK

```text
Processor SDK Linux:
  ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04

U-Boot source:
  board-support/ti-u-boot-2026.01+git

U-Boot branch:
  ti-u-boot-2026.01

U-Boot commit:
  2549829c
```

## 사용 defconfig

```text
configs/am64x_evm_r5_defconfig
configs/am64x_evm_a53_defconfig
```

## 공통 경로 설정

```bash
export SDK=~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04
export UBOOT_DIR=$SDK/board-support/ti-u-boot-2026.01+git
export PREBUILT=$SDK/board-support/prebuilt-images/am64xx-evm

export CROSS_COMPILE_32=$SDK/k3r5-devkit/sysroots/x86_64-arago-linux/usr/bin/arm-oe-eabi/arm-oe-eabi-
export CROSS_COMPILE_64=$SDK/linux-devkit/sysroots/x86_64-arago-linux/usr/bin/aarch64-oe-linux/aarch64-oe-linux-

export BUILD_BASE=~/ti/am64x/build/u-boot-sdk12
export R5_OUT=$BUILD_BASE/r5
export A53_OUT=$BUILD_BASE/a53
export ARTIFACTS=$BUILD_BASE/artifacts

mkdir -p $R5_OUT $A53_OUT $ARTIFACTS
```

Host Python은 Ubuntu system Python을 명시한다.

```bash
/usr/bin/python3 -c "import setuptools; print(setuptools.__version__)"
```

## 주의: SDK environment-setup 사용 금지

이번 standalone U-Boot 빌드에서는 아래 스크립트를 source하지 않는다.

```bash
source linux-devkit/environment-setup-aarch64-oe-linux
```

해당 environment setup을 source하면 SDK 내부 Python 또는 target sysroot 설정이 host tool build에 섞여 다음 문제가 발생할 수 있다.

```text
ModuleNotFoundError: No module named 'setuptools'
fatal error: bits/timesize-32.h: No such file or directory
```

따라서 clean shell에서 toolchain prefix만 직접 지정한다.

## R5 빌드

R5 빌드는 Boot ROM이 처음 로드하는 `tiboot3.bin` 계열 산출물을 만든다.

```bash
cd $UBOOT_DIR

make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_32" \
  am64x_evm_r5_defconfig \
  O=$R5_OUT

make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_32" \
  O=$R5_OUT \
  BINMAN_INDIRS=$PREBUILT \
  -j$(nproc)
```

산출물 확인:

```bash
find $R5_OUT -maxdepth 4 \
  \( -name "tiboot3*.bin" -o -name "u-boot-spl.bin" \) \
  -print | sort
```

SK-AM64B는 HS-FS silicon 기반 보드이므로 우선 다음 파일을 사용한다.

```text
tiboot3-am64x_sr2-hs-fs-evm.bin
```

## A53 빌드

A53 빌드는 `tispl.bin`과 `u-boot.img`를 만든다.

### A53 defconfig

```bash
rm -rf $A53_OUT
mkdir -p $A53_OUT

cd $UBOOT_DIR

make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_64" \
  am64x_evm_a53_defconfig \
  O=$A53_OUT \
  BINMAN_INDIRS=$PREBUILT
```

### EFI 관련 config 조정

이번 SDK 환경에서는 EFI hello/selftest 계열이 standalone build 중 `libgcc` link 문제를 일으켰다.

bring-up 목적에서는 EFI hello/selftest는 필수 경로가 아니므로 비활성화한다.

단, `EFI_LOAD_FILE2_INITRD`는 유지해야 한다. 이 옵션이 꺼지면 최종 U-Boot link 단계에서 다음 문제가 발생할 수 있다.

```text
undefined reference to `efi_initrd_register'
```

설정:

```bash
$UBOOT_DIR/scripts/config --file $A53_OUT/.config \
  -d BOOTEFI_HELLO_COMPILE \
  -d CMD_BOOTEFI_SELFTEST \
  -d EFI_SELFTEST \
  -e EFI_LOAD_FILE2_INITRD

make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_64" \
  O=$A53_OUT \
  olddefconfig
```

확인:

```bash
grep EFI $A53_OUT/.config | grep -E "HELLO|SELFTEST|LOAD_FILE2_INITRD" || true
```

기대 상태:

```text
# CONFIG_BOOTEFI_HELLO_COMPILE is not set
# CONFIG_CMD_BOOTEFI_SELFTEST is not set
CONFIG_EFI_LOAD_FILE2_INITRD=y
```

### libgcc 경로 지정

이번 SDK에서는 다음 명령이 libgcc 절대경로가 아니라 파일명만 반환했다.

```bash
${CROSS_COMPILE_64}gcc -print-libgcc-file-name
```

따라서 실제 `libgcc.a`를 찾아 `PLATFORM_LIBGCC`로 직접 전달한다.

```bash
export LIBGCC_FILE=$(find $SDK/linux-devkit -name "libgcc.a" | grep -E "aarch64|aarch64-oe-linux" | head -1)
ls -l "$LIBGCC_FILE"
```

확인된 예:

```text
$SDK/linux-devkit/sysroots/aarch64-oe-linux/usr/lib/aarch64-oe-linux/15.2.0/libgcc.a
```

### A53 build

```bash
cd $UBOOT_DIR

make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_64" \
  PYTHON=/usr/bin/python3 \
  BL31=$PREBUILT/bl31.bin \
  TEE=$PREBUILT/bl32.bin \
  O=$A53_OUT \
  BINMAN_INDIRS=$PREBUILT \
  PLATFORM_LIBGCC="$LIBGCC_FILE" \
  -j$(nproc)
```

산출물 확인:

```bash
find $A53_OUT -maxdepth 3 \
  \( -name "tispl*.bin" -o -name "u-boot*.img" -o -name "u-boot*.dtb" \) \
  -print | sort
```

기대 산출물:

```text
$A53_OUT/tispl.bin
$A53_OUT/u-boot.img
$A53_OUT/u-boot.dtb
```

## Artifact 수집

```bash
mkdir -p $ARTIFACTS

cp $R5_OUT/tiboot3-am64x_sr2-hs-fs-evm.bin $ARTIFACTS/tiboot3.bin
cp $A53_OUT/tispl.bin $ARTIFACTS/tispl.bin
cp $A53_OUT/u-boot.img $ARTIFACTS/u-boot.img

ls -lh $ARTIFACTS
```

최종 확인:

```text
tiboot3.bin
tispl.bin
u-boot.img
```

## 이후 검증

생성한 3개 파일을 SD 카드 boot partition 또는 수정된 `.wic` image의 boot partition에 배치한 뒤 SK-AM64B에서 부팅을 검증한다.

검증 로그에서 볼 포인트:

```text
- U-Boot SPL version/date
- SoC: AM64X SR2.0 HS-FS
- Board: AM64B-SKEVM rev A
- DRAM: 2 GiB
- Trying to boot from MMC2
- Authentication passed
- U-Boot prompt 진입 여부
- kernel Image / DTB load 여부
- Starting kernel ...
```
