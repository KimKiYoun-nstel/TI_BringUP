# AM64x Boot Flow와 extlinux.conf 정리

## Knowledge

AM64x 계열 보드의 전원 인가 후 첫 실행 주체는 SoC 내부 Boot ROM이다. Boot ROM은 Linux나 U-Boot 환경변수를 알지 못하며, Boot Mode Pin, Fuse, Strap 또는 DIP Switch 설정에 따라 선택된 boot media에서 초기 부트 이미지를 찾는다.

기본 흐름은 다음과 같다.

```text
Power On
  -> SoC Boot ROM
  -> Boot Mode 확인
  -> SD / OSPI / UART / USB / Ethernet 등에서 초기 boot image 로드
  -> SPL / tiboot3.bin 실행
  -> DDR 및 필수 초기화
  -> TF-A / OP-TEE / U-Boot proper 로드
  -> U-Boot proper 실행
  -> kernel Image + DTB + optional initramfs 로드
  -> Linux Kernel 실행
  -> rootfs mount
```

여기서 중요한 구분은 Boot ROM 단계와 U-Boot 단계가 서로 다른 boot decision을 한다는 점이다.

```text
Boot ROM 단계:
  tiboot3.bin / SPL 같은 초기 부트 이미지를 어디서 가져올지 결정한다.

U-Boot 단계:
  Linux kernel Image, DTB, initramfs, rootfs 정보를 어디서 어떻게 가져올지 결정한다.
```

따라서 SD boot라고 말해도 정확히는 다음 중 어느 단계의 SD 접근인지 구분해야 한다.

```text
Boot ROM:
  SD에서 tiboot3.bin을 찾는다.

SPL:
  SD에서 다음 stage image를 찾는다.

U-Boot:
  SD의 filesystem에서 /boot/Image, /boot/dtb, extlinux.conf 등을 찾는다.

Linux:
  SD partition을 block device로 인식하고 rootfs를 mount한다.
```

## extlinux.conf의 위치와 의미

`extlinux.conf`는 Linux가 부팅된 뒤 사용하는 설정 파일이 아니라, U-Boot가 Linux kernel을 실행하기 전에 읽는 boot menu/config 파일이다.

즉 `extlinux.conf`는 다음 단계에 속한다.

```text
Boot ROM 단계 아님
SPL 단계 아님
U-Boot proper 단계에서 사용하는 Linux boot 설정
```

`extlinux.conf`도 파일이므로 U-Boot가 접근 가능한 저장장치의 filesystem 안에 실제로 존재해야 한다. 하지만 반드시 보드 내장 저장장치에 있어야 하는 것은 아니다.

가능한 위치 예시는 다음과 같다.

```text
SD card:
  /boot/extlinux/extlinux.conf

USB storage:
  /boot/extlinux/extlinux.conf

eMMC:
  /boot/extlinux/extlinux.conf

Network boot:
  PXE/extlinux 계열 설정 사용 가능
```

핵심은 다음이다.

```text
extlinux.conf는 보드 내부 저장장치 전용 개념이 아니다.
U-Boot가 읽을 수 있는 media에 있으면 된다.
```

## 완전 생보드에서 extlinux.conf 사용 가능 여부

완전 생보드, 즉 보드 내부 OSPI/eMMC가 비어 있는 상태에서도 `extlinux.conf`를 사용할 수 있다. 단, U-Boot가 실행된 이후 접근 가능한 외부 media에 `extlinux.conf`, kernel Image, DTB, rootfs가 준비되어 있어야 한다.

예시:

```text
보드 내부 저장장치:
  비어 있음

microSD card:
  tiboot3.bin
  tispl.bin
  u-boot.img
  /boot/extlinux/extlinux.conf
  /boot/Image
  /boot/dtb/ti/k3-am642-sk.dtb
  rootfs
```

이 경우 흐름은 다음과 같다.

```text
Boot ROM:
  SD에서 tiboot3.bin 로드

SPL:
  SD에서 U-Boot proper 로드

U-Boot:
  SD filesystem을 읽고 /boot/extlinux/extlinux.conf 확인
  extlinux.conf가 지정한 kernel Image와 DTB 로드

Linux:
  SD rootfs mount
```

즉 `extlinux.conf`는 “한 번 Linux로 부팅한 뒤 보드 내부 저장장치에 설치해야만 사용 가능한 옵션”이 아니다. U-Boot가 읽을 수 있는 media에 이미 존재하면 첫 부팅부터 사용할 수 있다.

## U-Boot env 방식과 extlinux.conf 방식의 차이

U-Boot가 Linux를 부팅하는 방식은 여러 가지가 있다.

```text
U-Boot env script 기반 직접 로딩
uEnv.txt 기반 환경변수 override
extlinux.conf 기반 boot menu
boot.scr script
EFI boot
PXE/DHCP/TFTP network boot
```

TI SDK 계열 U-Boot 환경에서는 `/boot/Image`, `/boot/dtb/...`를 U-Boot 환경변수로 직접 로드하는 방식이 먼저 실행될 수 있다.

예시 개념:

```text
bootcmd
  -> envboot
  -> bootcmd_ti_mmc
  -> bootflow scan
```

이 경우 `bootcmd_ti_mmc`가 성공하면 `extlinux.conf`를 사용하지 않고 바로 kernel을 실행할 수 있다. 반대로 `bootflow scan`에서 extlinux boot method가 활성화되어 있으면 `/boot/extlinux/extlinux.conf`를 탐색할 수 있다.

## Decision

현재 학습/bring-up 단계에서는 다음 순서로 이해하고 검증하는 것이 좋다.

```text
1. Boot ROM이 어떤 media에서 SPL/tiboot3.bin을 가져오는지 확인한다.
2. SPL/U-Boot가 어떤 media에서 다음 stage를 가져오는지 확인한다.
3. U-Boot의 bootcmd, boot_targets, bootmeths를 확인한다.
4. TI env 기반 /boot/Image 직접 로딩 경로를 먼저 이해한다.
5. 이후 extlinux.conf 기반 bootflow도 별도 실험한다.
```

## Assumption

현재 SK-AM64B 또는 TMDS64EVM의 SD card boot 환경은 다음 구조일 가능성이 높다.

```text
FAT boot partition:
  tiboot3.bin
  tispl.bin
  u-boot.img
  uEnv.txt optional

ext4 rootfs partition:
  /boot/Image
  /boot/dtb/ti/*.dtb
  /boot/extlinux/extlinux.conf optional
  rootfs 전체
```

## Open Question

각 보드에서 실제로 어떤 boot 경로가 우선 사용되는지는 U-Boot 환경변수와 SD 카드 파일 구조를 직접 확인해야 한다.

확인 항목:

```bash
printenv bootcmd
printenv boot_targets
printenv bootmeths
printenv bootpart
printenv bootdir
printenv fdtfile

ls mmc 1:1
ls mmc 1:2 /boot
ls mmc 1:2 /boot/extlinux
cat mmc 1:2 /boot/extlinux/extlinux.conf
```

## Action Item

1. U-Boot prompt에서 `bootflow scan -lb`를 실행하여 extlinux 후보가 탐색되는지 확인한다.
2. Linux 부팅 후 `/boot/extlinux/extlinux.conf` 존재 여부를 확인한다.
3. TI env 기반 `/boot/Image` 직접 로딩과 extlinux 기반 로딩을 각각 분리해서 테스트한다.
4. 커스텀 보드 BSP 정책으로 U-Boot env 기반, uEnv.txt 기반, extlinux.conf 기반 중 어떤 방식을 주 boot path로 사용할지 결정한다.

## Board Note

SK-AM64B와 TMDS64EVM은 같은 AM64x 계열 SoC를 사용할 수 있지만, board DTB, boot switch, storage 연결, power/reset 회로, enabled peripheral 구성이 다를 수 있다. 따라서 boot path 검증은 보드별로 따로 남겨야 한다.

## Artifact

권장 저장 위치:

```text
docs/bringup/am64x_boot_flow_extlinux_summary.md
```
