# TI AM64x SDK 구조 파악 및 TI_BringUP Repo 구성 세션 정리

## Knowledge

### TI Processor SDK의 성격

`ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04`는 AM64x 계열 EVM/SK 보드를 위한 TI 공식 Linux BSP 통합 SDK로 이해한다.

이 SDK는 단일 소스 프로젝트가 아니라 다음 요소를 포함하는 BSP 작업 공간이다.

```text
TI Processor SDK
├── board-support/
│   ├── ti-u-boot-2026.01+git/
│   ├── ti-linux-kernel-6.18.13+git-ti/
│   ├── trusted-firmware-a-2.14+git/
│   ├── optee-os-4.9.0+git/
│   ├── prebuilt-images/
│   ├── extra-drivers/
│   └── k3-respart-tool/
├── linux-devkit/
├── k3r5-devkit/
├── filesystem/
├── bin/
├── makerules/
├── manifest/
├── Makefile
├── Rules.make
└── setup.sh
```

BSP 관점에서 SDK는 다음 역할을 한다.

```text
Boot ROM 이후 부팅 소프트웨어:
  tiboot3.bin
  tispl.bin
  u-boot.img

Linux 실행 환경:
  Linux kernel source
  Device Tree source
  kernel modules
  rootfs
  firmware

빌드/개발 환경:
  cross toolchain
  sysroot
  prebuilt images
  scripts
  reference Makefile
```

AM64x 부팅 흐름에서 SDK 구성 요소의 위치는 다음과 같다.

```text
Boot ROM
  -> tiboot3.bin
  -> tispl.bin
  -> u-boot.img
  -> Linux Image + DTB
  -> RootFS
```

### board-support 하위 source tree의 의미

`board-support` 하위의 `ti-u-boot-*`, `ti-linux-kernel-*`, `trusted-firmware-a-*`, `optee-os-*`는 각각 독립적인 upstream/TI source tree 성격을 가진다.

다만 AM64x에서 실제 bootable image를 만들 때는 source tree 하나만으로 끝나지 않는다. U-Boot/SPL 빌드에는 R5/A53 빌드 흐름, TF-A, OP-TEE, TIFS/SYSFW/DM firmware, prebuilt binaries, signing/packaging flow가 함께 엮일 수 있다.

따라서 다음과 같이 이해한다.

```text
source tree 관점:
  U-Boot와 Linux kernel은 독립 프로젝트처럼 다룰 수 있다.

빌드 재현성 관점:
  TI SDK의 toolchain, sysroot, firmware, prebuilt image, scripts에 의존한다.
```

### 커스텀 보드 BSP 작업에서 실제로 많이 수정하는 영역

커스텀 보드 개발 시 Linux kernel core driver나 U-Boot core code를 직접 수정하는 경우는 상대적으로 적다. 일반적으로는 보드 설정과 hardware description 중심의 변경이 많다.

주요 수정 대상은 다음과 같다.

Linux 영역:

```text
arch/arm64/boot/dts/ti/*.dts
arch/arm64/boot/dts/ti/*.dtsi
kernel defconfig
kernel config fragment
driver enable/disable CONFIG 옵션
```

U-Boot 영역:

```text
arch/arm/dts/*.dts
arch/arm/dts/*-u-boot.dtsi
configs/*_defconfig
board-specific configuration
bootcmd / environment
DDR / boot media 관련 설정
```

RootFS 영역:

```text
rootfs overlay
/etc 설정
systemd service
network config
application install script
firmware install 위치
```

가능하면 TI EVM 원본 파일을 직접 수정하기보다, 내 보드용 파일을 추가하는 방식이 좋다.

예:

```text
TI 원본:
  k3-am642-sk.dts

내 보드:
  k3-am642-myboard.dts
```

즉, `modify`보다 `add` 중심의 구조가 장기 유지보수에 유리하다.

### patch/layer 기반 관리 개념

내 보드 변경사항은 TI BSP source tree 전체를 내 원격 repo에 동기화하는 대신, TI 원본 대비 변경분을 patch 형태로 관리한다.

```text
TI BSP source tree
  + 내 board-specific patches
  + 내 config fragments
  + 내 rootfs overlay
  = 내 보드용 BSP
```

patch는 다음 의미를 가진다.

```text
TI 원본 source tree 대비 내 변경사항의 재현 가능한 기록
```

작업 중에는 source tree에서 직접 수정해도 되지만, 장기 보관 대상은 patch로 export하여 `TI_BringUP` repo에 저장한다.

예:

```bash
git format-patch <baseline>..HEAD -o ~/ti/TI_Bringup/bsp/linux/patches/
```

Yocto 단계에서는 patch와 config를 `meta-myboard` 같은 custom layer에 편입하는 방식으로 확장할 수 있다.

## Decision

### Repo와 SDK의 역할 분리

현재 WSL2 작업 구조는 다음과 같다.

```text
~/ti/
├── TI_Bringup/
└── am64x/
    └── ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/
```

역할은 다음과 같이 분리한다.

```text
~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/
  - TI 원본 SDK
  - reference BSP
  - toolchain/sysroot/firmware/rootfs/prebuilt provider
  - 가능하면 직접 수정하지 않음

~/ti/TI_Bringup/
  - 문서 저장소
  - SDK manifest 저장소
  - build/prepare/install script 저장소
  - board-specific patch/config/dts/rootfs overlay 저장소
  - AI Agent 작업 지침 저장소
  - boot/kernel log 및 분석 결과 저장소
```

### source tree 관리 방식

BSP source tree 전체를 `TI_BringUP` 원격 repo에 동기화하지 않는다.

대신 로컬 repo 내부에 `workspace/`를 두고, 그 안에 SDK source tree를 copy 또는 checkout해서 코드 분석/수정/빌드에 사용한다.

```text
~/ti/TI_Bringup/
├── workspace/
│   ├── ti-u-boot-sdk12/
│   └── ti-linux-kernel-sdk12/
├── bsp/
│   ├── u-boot/
│   └── linux/
├── tools/
├── sdk-manifest/
├── board/
├── rootfs/
└── docs/
```

`workspace/`는 상위 `TI_BringUP` repo의 Git 관리 대상에서 제외한다.

```gitignore
/workspace/
```

하지만 `workspace/ti-u-boot-sdk12`와 `workspace/ti-linux-kernel-sdk12` 내부의 자체 `.git`은 유지할 수 있다. 이를 통해 source tree 내부에서 실험 branch와 local commit을 관리한다.

### 변경사항 장기 보관 방식

의미 있는 source tree 변경은 다음 흐름으로 관리한다.

```text
1. workspace source tree에서 직접 수정
2. 빌드/부팅 검증
3. workspace 내부 git commit 생성
4. git format-patch로 patch export
5. TI_BringUP/bsp/*/patches/에 저장
6. TI_BringUP 원격 repo에 commit/push
```

즉, 장기적으로 원격 repo에 남기는 것은 source tree 전체가 아니라 다음이다.

```text
docs
sdk-manifest
build scripts
prepare scripts
install scripts
patches
config fragments
board notes
rootfs overlay
logs
```

### 다른 머신에서의 재현 방식

다른 머신에서는 다음 조건이 있으면 동일 작업 환경을 복원할 수 있도록 한다.

```text
1. TI_BringUP repo clone
2. 동일 버전 TI Processor SDK 설치
3. SDK path 설정
4. workspace 생성 script 실행
5. patch 적용 script 실행
6. build script 실행
```

목표는 다음 상태이다.

```text
내 원격 repo + 동일 TI SDK
  -> workspace 재생성
  -> patch 재적용
  -> 동일 bootloader/kernel/dtb/rootfs customization 재현
```

## Assumption

현재 기준 SDK 경로는 다음으로 가정한다.

```bash
~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04
```

현재 기준 bring-up repo 경로는 다음으로 가정한다.

```bash
~/ti/TI_Bringup
```

현재 SDK의 주요 source tree 이름은 다음으로 확인되었다.

```text
ti-u-boot-2026.01+git
ti-linux-kernel-6.18.13+git-ti
trusted-firmware-a-2.14+git
optee-os-4.9.0+git
```

현재 단계에서는 여러 개발 머신 간 source tree 자체를 동기화하지 않는 것으로 가정한다. 여러 머신에서 이어서 작업해야 할 경우에도 source tree 전체가 아니라 `patch + scripts + manifest + 동일 SDK` 조합으로 재현한다.

## Open Question

1. 실제 대상 보드는 SK-AM64B 기준으로 계속 갈 것인지, TMDS64EVM도 병행 관리할 것인지 결정이 필요하다.

2. 자체 보드 이름과 device tree compatible string naming rule을 정해야 한다.

예:

```text
k3-am642-nstel-board.dts
compatible = "nstel,am642-xxx", "ti,am642";
```

3. U-Boot 쪽에서 내 보드용 defconfig를 새로 추가할지, 초기에는 TI EVM defconfig를 그대로 사용할지 결정이 필요하다.

4. Linux kernel build output 설치 위치와 SD card mount path naming rule을 정해야 한다.

예:

```text
/mnt/sd-boot
/mnt/sd-rootfs
```

5. patch 적용 방식은 `git am` 기반으로 할지, 단순 `patch -p1` 기반으로 할지 결정이 필요하다. Git commit metadata를 보존하려면 `git am`이 적합하다.

6. 향후 Yocto 단계에서 `meta-nstel` 또는 `meta-myboard` layer를 생성할지 결정이 필요하다.

## Action Item

### 1. Repo 기본 구조 유지/검증

`TI_BringUP` repo에 다음 구조가 존재하는지 확인한다.

```text
sdk-manifest/
bsp/
  u-boot/
    patches/
    configs/
    dts/
  linux/
    patches/
    configs/
    dts/
tools/
  env/
  prepare/
  build/
  install/
board/
  sk-am64b/
  myboard/
rootfs/
  overlay/
logs/
workspace/
```

`workspace/`는 `.gitignore`에 포함되어야 한다.

```gitignore
/workspace/
```

### 2. SDK 환경 파일 관리

`tools/env/sdk-12.00.00.07.04.env` 형태로 SDK path 설정 파일을 관리한다.

예상 내용:

```bash
#!/usr/bin/env bash

export TI_WORKSPACE="$HOME/ti"
export BRINGUP_ROOT="$TI_WORKSPACE/TI_Bringup"

export SDK_VERSION="12.00.00.07.04"
export SDK_ROOT="$TI_WORKSPACE/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04"

export BOARD_SUPPORT="$SDK_ROOT/board-support"
export LINUX_DEVKIT="$SDK_ROOT/linux-devkit"
export K3R5_DEVKIT="$SDK_ROOT/k3r5-devkit"
export PREBUILT_IMAGES="$SDK_ROOT/board-support/prebuilt-images"
export FILESYSTEM="$SDK_ROOT/filesystem"

export UBOOT_SRC="$BRINGUP_ROOT/workspace/ti-u-boot-sdk12"
export KERNEL_SRC="$BRINGUP_ROOT/workspace/ti-linux-kernel-sdk12"
```

### 3. workspace 생성 자동화

`tools/prepare/create-workspace.sh`는 다음 역할을 수행한다.

```text
1. SDK_ROOT 존재 여부 확인
2. BRINGUP_ROOT/workspace 생성
3. SDK board-support의 ti-u-boot-*를 workspace/ti-u-boot-sdk12로 복사
4. SDK board-support의 ti-linux-kernel-*를 workspace/ti-linux-kernel-sdk12로 복사
5. 각 source tree의 git commit 정보를 출력
```

### 4. manifest 생성

`sdk-manifest/`에는 다음 정보를 남긴다.

```text
SDK version
SDK install path example
board-support source tree list
U-Boot commit hash
Linux kernel commit hash
TF-A version
OP-TEE version
prebuilt image list
```

추천 파일:

```text
sdk-manifest/sdk-version.md
sdk-manifest/source-commits.md
sdk-manifest/board-support-tree.md
sdk-manifest/build-targets.md
```

### 5. patch 적용/추출 스크립트 관리

Linux:

```text
tools/prepare/apply-linux-patches.sh
tools/prepare/export-linux-patches.sh
```

U-Boot:

```text
tools/prepare/apply-u-boot-patches.sh
tools/prepare/export-u-boot-patches.sh
```

patch 저장 위치:

```text
bsp/linux/patches/
bsp/u-boot/patches/
```

### 6. build script skeleton 관리

Linux build:

```text
tools/build/build-kernel.sh
```

U-Boot build:

```text
tools/build/build-u-boot.sh
```

초기에는 기존에 수동으로 성공했던 build command를 그대로 script화하고, 이후 refactor한다.

### 7. 작업 규칙 문서화

Repo README 또는 Agent guide에 다음 규칙을 명시한다.

```text
- TI SDK 원본은 직접 수정하지 않는다.
- workspace/는 로컬 source analysis/build 공간이며 원격 repo에 push하지 않는다.
- 의미 있는 source 변경은 workspace 내부 git commit으로 먼저 정리한다.
- 장기 보관할 변경은 patch로 export해서 bsp/*/patches/에 저장한다.
- 원격 repo에는 patch, script, manifest, docs, board notes, rootfs overlay를 저장한다.
- 다른 머신에서는 TI SDK + TI_BringUP repo + prepare script로 workspace를 재현한다.
```

## Board Note

### SK-AM64B / AM64x EVM 공통 학습 기준

현재 학습과 bring-up 리허설은 TI AM64x 계열 EVM/SK SDK를 기준으로 진행한다.

현재 SDK의 `board-support`에는 다음 주요 source가 존재한다.

```text
extra-drivers/
k3-respart-tool/
optee-os-4.9.0+git/
prebuilt-images/
ti-linux-kernel-6.18.13+git-ti/
ti-u-boot-2026.01+git/
trusted-firmware-a-2.14+git/
```

이 중 초기 주요 분석 대상은 다음이다.

```text
Bootloader:
  ti-u-boot-2026.01+git
  trusted-firmware-a-2.14+git
  optee-os-4.9.0+git
  prebuilt-images

Linux:
  ti-linux-kernel-6.18.13+git-ti
```

커스텀 보드 전환 시 가장 먼저 비교해야 할 항목은 다음이다.

```text
DDR
PMIC / regulator
boot media: SD/eMMC/OSPI
UART console
Ethernet PHY
I2C device tree
GPIO expander
reset lines
clock source
pinmux
rootfs mount path
```

## Artifact

이번 세션에서 생성/반영된 산출물 후보는 다음이다.

```text
TI_Bringup_Repo_Setup_Agent_Guide.md
```

이 문서는 local AI Agent가 `TI_BringUP` repo 구조와 SDK 환경을 구성하는 기준 문서로 사용되었다.

향후 repo 내에서 관리할 권장 문서는 다음이다.

```text
AGENTS.md
PROJECT_BRIEF.md
README.md
docs/sdk/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04.md
docs/workflow/bsp-workspace-and-patch-flow.md
docs/workflow/build-and-install-flow.md
sdk-manifest/sdk-version.md
sdk-manifest/source-commits.md
```

## Final Summary

이번 세션의 핵심 결론은 다음과 같다.

```text
TI Processor SDK는 AM64x용 공식 BSP workspace로 사용한다.
TI SDK 원본은 reference/build dependency로 유지한다.
TI_BringUP repo는 source tree 전체가 아니라 내 보드 변경사항과 자동화/문서를 관리한다.
로컬 workspace 안에 U-Boot/kernel source tree를 두어 코드 분석과 빌드를 편하게 한다.
workspace는 원격 repo에 push하지 않는다.
의미 있는 변경은 patch로 export하여 TI_BringUP repo에 저장한다.
다른 머신에서는 TI_BringUP repo와 동일 TI SDK를 이용해 workspace를 재현한다.
```
