---
title: Processor SDK Linux AM64x 초기 설치 및 부트 준비 기록
path: docs/setup/processor-sdk-linux-am64x-initial-setup.md
boards:
  - TMDS64EVM
  - SK-AM64B
sdk_version: 12.00.00.07.04
status: 사전 빌드 SD 카드 이미지 다운로드 완료, 보드 부팅 전
---

# Processor SDK Linux AM64x 초기 설치 및 부트 준비 기록

## 목적

이 문서는 TMDS64EVM과 SK-AM64B 보드에서 TI AM64x 계열 Embedded Linux BSP bring-up을 진행하기 위한 초기 개발 환경과 Processor SDK Linux 설치 상태를 기록합니다.

현재 단계의 목표는 U-Boot, Linux Kernel, Device Tree, RootFS를 직접 수정하기 전에 TI 공식 Processor SDK Linux의 prebuilt SD 카드 이미지를 사용해 레퍼런스 보드의 기본 Linux 부팅 기준선을 확보하는 것입니다.

## 대상 보드

- TMDS64EVM
- SK-AM64B

## Host 개발 환경

Windows PC에서 WSL2 기반 Ubuntu 22.04를 TI AM64x BSP 작업용 기본 개발 환경으로 사용합니다.

```text
Host OS:
  Windows

Linux Build Environment:
  WSL2 Ubuntu 22.04

작업 경로:
  ~/ti/am64x
```

WSL2 Ubuntu 24.04도 사용할 수 있지만, TI Processor SDK Linux와의 호환성을 고려해 Ubuntu 22.04 WSL2를 별도로 준비하여 기본 작업 환경으로 사용합니다.

## 공식 TI 링크

Processor SDK Linux AM64x 제품 페이지:

```text
https://www.ti.com/tool/PROCESSOR-SDK-AM64X
```

Processor SDK Linux AM64x 12.00.00.07.04 다운로드 페이지:

```text
https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-AM64X/12.00.00.07.04
```

Processor SDK Linux AM64x 문서:

```text
https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/latest/exports/docs/
```

SD 카드 이미지 생성 및 플래싱 관련 문서:

```text
https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/latest/exports/docs/linux/Overview/Processor_SDK_Linux_create_SD_card.html
```

## 작업 디렉터리 생성

WSL2 Ubuntu 22.04에서 TI AM64x 작업 디렉터리를 생성합니다.

```bash
mkdir -p ~/ti/am64x
cd ~/ti/am64x
```

## Processor SDK Linux AM64x 설치

다운로드한 Processor SDK Linux installer를 WSL2 Ubuntu 22.04 환경에서 실행합니다.

설치 대상 SDK 버전:

```text
ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04
```

installer 파일명:

```text
ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin
```

실행 명령:

```bash
cd ~/ti/am64x
chmod +x ./ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin
./ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin
```

설치 경로:

```text
~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04
```

설치가 끝나면 SDK 디렉터리로 이동합니다.

```bash
cd ~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04
```

## SDK 내부 이미지 확인

SDK 내부에서 SD 카드 이미지, rootfs, prebuilt 이미지 관련 파일을 확인하기 위해 아래 명령을 실행합니다.

```bash
find . -iname "*.wic*" -o -iname "*.img*" -o -iname "*tisdk*image*"
```

확인된 주요 파일:

```text
./filesystem/am64xx-evm/tisdk-default-image-am64xx-evm.rootfs.tar.xz
./filesystem/am64xx-evm/tisdk-thinlinux-image-am64xx-evm.rootfs.tar.xz
./filesystem/am64xx-evm/tisdk-default-image-am64xx-evm.rootfs.vex.json
./filesystem/am64xx-evm/tisdk-thinlinux-image-am64xx-evm.rootfs.vex.json
./filesystem/am64xx-evm/tisdk-base-image-am64xx-evm.rootfs.spdx.json
./filesystem/am64xx-evm/tisdk-thinlinux-image-am64xx-evm.rootfs.spdx.json
./filesystem/am64xx-evm/tisdk-default-image-am64xx-evm.rootfs.spdx.json
./filesystem/am64xx-evm/tisdk-base-image-am64xx-evm.rootfs.tar.xz
./filesystem/am64xx-evm/tisdk-base-image-am64xx-evm.rootfs.vex.json
./board-support/prebuilt-images/am64xx-evm/u-boot.img
```

해석:

- SDK 설치 디렉터리 안에는 rootfs tarball과 prebuilt boot component가 포함되어 있습니다.
- SDK 설치 디렉터리 내부에서는 완성된 `.wic.xz` SD 카드 이미지가 바로 보이지 않았습니다.
- 완성된 SD 카드 이미지는 TI 다운로드 페이지에서 별도 항목으로 제공됩니다.

## Prebuilt SD 카드 이미지

TI 다운로드 페이지에서 AM64x EVM용 prebuilt SD 카드 이미지를 확인하고 다운로드합니다.

사용한 이미지 파일:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

이 파일은 microSD 카드에 직접 기록하여 TMDS64EVM과 SK-AM64B의 기본 Linux 부팅 여부를 확인하는 기준선 이미지입니다.

## 현재 상태

완료한 작업:

```text
- WSL2 Ubuntu 22.04 준비
- TI AM64x BSP 작업 디렉터리 생성
- Processor SDK Linux AM64x 12.00.00.07.04 다운로드
- Processor SDK Linux installer 실행
- SDK 설치 완료
- SDK 내부 rootfs tarball 확인
- SDK 내부 prebuilt u-boot.img 확인
- TI 다운로드 페이지에서 prebuilt SD 카드 이미지 확인
- prebuilt SD 카드 이미지 다운로드 완료
```

아직 수행하지 않은 작업:

```text
- prebuilt SD 카드 이미지를 microSD 카드에 기록
- TMDS64EVM microSD boot mode 설정
- SK-AM64B microSD boot mode 설정
- UART 콘솔 연결
- TMDS64EVM 부팅 확인
- SK-AM64B 부팅 확인
- boot log 저장
- Linux login prompt 확인
```

## 다음 단계

다음 단계는 다운로드한 prebuilt SD 카드 이미지를 microSD 카드에 기록한 뒤 각 보드에서 microSD 부팅을 수행해 baseline boot log를 확보하는 것입니다.

사용할 이미지:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

부팅 확인 순서:

```text
1. prebuilt SD 카드 이미지를 microSD 카드에 기록
2. 보드별 microSD boot mode 설정
3. UART 콘솔 연결
4. 전원 인가
5. boot log 저장
6. Linux login prompt 확인
7. 부팅 후 device tree model 확인
```

부팅 성공 후 보드에서 확인할 명령:

```bash
uname -a
cat /proc/device-tree/model
cat /proc/cmdline
dmesg | head -n 80
lsblk
ip addr
mount
```

## Bring-up 기준

이번 단계는 커널 수정이나 Device Tree 수정 이전의 기준 상태를 확보하기 위한 baseline bring-up 단계입니다.

향후 U-Boot, Linux Kernel, Device Tree, RootFS를 수정한 뒤 문제가 발생하면, 이번 prebuilt 이미지 부팅 결과와 비교해 문제 위치를 구분합니다.

구분 기준:

```text
- 보드 전원 / boot mode / SD 카드 / UART 문제
- bootloader 단계 문제
- kernel loading 문제
- Device Tree 문제
- rootfs mount 문제
- 사용자 수정 BSP 변경 사항에 의한 문제
```
