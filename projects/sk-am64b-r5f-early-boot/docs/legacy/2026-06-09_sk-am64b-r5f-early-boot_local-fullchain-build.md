# 2026-06-09 SK-AM64B R5F Early Boot Local Fullchain Build

## 목적

이 문서는 SK-AM64B SBL early boot 검증을 위해
**A53-side source image를 local workspace source에서 직접 빌드한 절차와 산출물**을 기록한다.

핵심 목적은 다음과 같다.

- SDK prebuilt `board-support/prebuilt-images` 의존을 줄이고
- `BL31` 이후 정지 원인을 좁히기 위해
- TF-A / OP-TEE / U-Boot / linux appimage chain을 local build lineage로 재구성한다.

## 배경

이전까지는 다음과 같은 혼합 provenance가 사용되었다.

- `bl31.bin`: SDK prebuilt
- `bl32.bin`: SDK prebuilt
- SPL: local raw 또는 SDK prebuilt 혼용
- `u-boot.img`: local build

이 조합으로 만든 `linux.mcelf.hs_fs`는 OSPI boot에서
`BL31` banner 이후 정지했다.

## 이번 세션에서 실제로 한 일

### 1. local workspace clone 추가

외부 reference-only source를 workspace 아래로 복제했다.

- TF-A local workspace:
  - `workspace/trusted-firmware-a-2.14+git`
- OP-TEE local workspace:
  - `workspace/optee-os-4.9.0+git`

의미:

- 외부 SDK original을 건드리지 않고 local build 실험을 계속할 수 있다.

### 2. local TF-A 빌드

실행 개념:

```bash
source tools/env/sdk-12.00.00.07.04.env
make ARCH=aarch64 CROSS_COMPILE="$CROSS_COMPILE_AARCH64" PLAT=k3 TARGET_BOARD=lite SPD=opteed
```

산출물:

- `workspace/trusted-firmware-a-2.14+git/build/k3/lite/release/bl31.bin`

확인값:

- size: `43776`
- sha256: `851beca9c91bf9ed6ce0339aa5ed43389e4b860dd5e775de1f1634a4024b0550`

### 3. local OP-TEE 빌드

초기 시도에서는 env의 `ARCH=arm64` export 때문에
`lib/libutee/arch/arm64/sub.mk` 경로 오류가 발생했다.

교정:

- OP-TEE build 전 `unset ARCH`

추가 이슈:

- 기본 build는 in-tree TA link 단계에서 `libgcc.a` 부족으로 실패했다.

교정:

- core binary 확보 목적이므로 `CFG_BUILD_IN_TREE_TA=n` 으로 재시도

실행 개념:

```bash
source tools/env/sdk-12.00.00.07.04.env
unset ARCH
make \
  CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
  CROSS_COMPILE32="$CROSS_COMPILE_ARMV7R" \
  CROSS_COMPILE64="$CROSS_COMPILE_AARCH64" \
  PLATFORM=k3-am64x \
  CFG_ARM64_core=y \
  CFG_BUILD_IN_TREE_TA=n
```

산출물:

- `workspace/optee-os-4.9.0+git/out/arm-plat-k3/core/tee-pager_v2.bin`

확인값:

- size: `482664`
- sha256: `974f30d3160d103a7ed4352160a9f02641d126c6ce9ea4d2781111e060081680`

주의:

- linuxAppimageGen staging 시에는 tool 기대 이름 때문에
  `tee-pager_v2.bin`을 `bl32.bin` 이름으로 staging 했다.

### 4. local U-Boot A53 chain 빌드

기존 helper는 SDK prebuilt `BL31` / `TEE` 를 사용했으므로,
이번에는 local-built TF-A / OP-TEE 결과를 직접 연결해 A53를 다시 빌드했다.

핵심 연결:

- `BL31` -> local `bl31.bin`
- `TEE` -> local `tee-pager_v2.bin`

산출물 위치:

- `out/u-boot-local-a53chain/a53/u-boot.img`
- `out/u-boot-local-a53chain/a53/spl/u-boot-spl.bin`

확인값:

- `u-boot.img`
  - size: `1573372`
  - sha256: `2c7d79965c9dd1526cb602139ba79457fe32fd02b2bfbfb25053a701223b2bb7`
- `spl/u-boot-spl.bin`
  - size: `363148`
  - sha256: `09d7d40c964f469695705fa5fab3fab1dd6f98b3083536d1d179b5b7e1703513`

### 5. local MCU+ SBL artifact 확인

SBL은 workspace MCU+ SDK example tree의 local artifact를 기준으로 유지했다.

경로:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang/sbl_ospi_linux.release.hs_fs.tiimage`

확인값:

- size: `327013`

### 6. local-built fullchain linux appimage 생성

staging 구성:

- `bl31.bin` -> local TF-A output
- `bl32.bin` -> local OP-TEE `tee-pager_v2.bin` copied as alias
- `u-boot-spl.bin-am64xx-evm` -> local `spl/u-boot-spl.bin` copied as alias
- `u-boot.img` -> local U-Boot A53 output

산출물:

- `out/r5f-early-boot/linux-appimage-build-local-fullchain/linux.mcelf.hs_fs`
- `out/r5f-early-boot/linux-appimage-build-local-fullchain/u-boot.img`

확인값:

- `linux.mcelf.hs_fs`
  - size: `891642`
  - sha256: `33e7787a9ef7579c59fb4cb609009d0aa59d14bc5182d7b4eebcdf0336cf317a`
- copied `u-boot.img`
  - size: `1573372`
  - sha256: `2c7d79965c9dd1526cb602139ba79457fe32fd02b2bfbfb25053a701223b2bb7`

## 이번 세션 산출물 요약

| 역할 | 경로 |
|---|---|
| local TF-A BL31 | `workspace/trusted-firmware-a-2.14+git/build/k3/lite/release/bl31.bin` |
| local OP-TEE BL32 input | `workspace/optee-os-4.9.0+git/out/arm-plat-k3/core/tee-pager_v2.bin` |
| local U-Boot raw SPL | `out/u-boot-local-a53chain/a53/spl/u-boot-spl.bin` |
| local U-Boot proper | `out/u-boot-local-a53chain/a53/u-boot.img` |
| local SBL | `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/.../sbl_ospi_linux.release.hs_fs.tiimage` |
| local fullchain linux appimage | `out/r5f-early-boot/linux-appimage-build-local-fullchain/linux.mcelf.hs_fs` |

## 다음 flash용 cfg

다음 retry에서는 아래 cfg를 사용한다.

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_local-fullchain.cfg`

의미:

- offset `0x0`: local SBL artifact path
- offset `0x80000`: current custom R5F heartbeat image 유지
- offset `0x300000`: local-built `u-boot.img`
- offset `0x800000`: local-built fullchain `linux.mcelf.hs_fs`

## 현재 판단

이번 세션으로 다음은 충족했다.

```text
TF-A local build: yes
OP-TEE local build: yes (core binary 확보)
U-Boot A53 local build with local BL31/TEE: yes
linux appimage regeneration with local-built A53 inputs: yes
```

이제 다음 판정 포인트는 다음 하나다.

```text
local-built fullchain linux appimage로도 BL31 이후 정지하는가?
```
