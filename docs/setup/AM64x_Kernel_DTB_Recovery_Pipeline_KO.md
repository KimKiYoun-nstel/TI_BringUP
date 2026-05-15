# AM64x Kernel/DTB 복구 파이프라인 제안

## 1. 목적

이 문서는 현재 `TI_BringUP` 로컬 repo에 구축 중인 빌드/배포 파이프라인에 **Kernel + DTB 복구 흐름**을 추가하기 위한 가이드이다.

현재 파이프라인의 기본 방향은 다음과 같다.

```text
Host PC local repo
  → Bootloader / Kernel / DTB 빌드
  → Ethernet/SSH를 이용해 보드에 배포
  → SD card 기반 부팅으로 검증
```

이 방식은 빠르고 편하지만, 새로 배포한 Kernel 또는 DTB에 문제가 있으면 Linux까지 진입하지 못할 수 있다. 그러면 SSH/SCP 기반 복구가 불가능해진다.

따라서 파이프라인은 단순히 “빌드 후 배포”가 아니라, **실패해도 보드를 다시 살릴 수 있는 구조**를 포함해야 한다.

---

## 2. 현재 확인된 기준

현재 확인된 부팅 기준은 다음과 같다.

```text
U-Boot에서 SD card 장치:
  mmc 1

Linux rootfs:
  /dev/mmcblk1p2

현재 bootargs:
  console=ttyS2,115200n8
  root=PARTUUID=076c4a2a-02

현재 부팅 방식:
  extlinux.conf 기반이 아니라 TI SDK U-Boot env / bootcmd / uEnv.txt 기반 흐름으로 판단
```

부팅 흐름은 큰 관점에서 다음과 같이 본다.

```text
Boot ROM
  → tiboot3.bin
  → tispl.bin
  → u-boot.img
  → U-Boot env / bootcmd
  → Kernel Image
  → DTB
  → SD rootfs
```

---

## 3. 복구 파이프라인이 필요한 이유

현재 SD card 기반 실험 플로우에서는 다음 문제가 발생할 수 있다.

```text
정상 상태:
  SD bootloader 정상
  SD Kernel/DTB 정상
  SD rootfs 정상
  → Linux 부팅 성공
  → SSH/SCP로 다음 이미지 배포 가능

문제 상태:
  SD bootloader 정상
  SD Kernel 또는 DTB 비정상
  → U-Boot까지는 진입
  → Kernel boot 실패
  → Linux 진입 실패
  → SSH/SCP 복구 불가
```

즉, Kernel/DTB 실험을 반복하려면 **Linux 진입 이전 단계인 U-Boot에서 복구할 수 있는 경로**가 필요하다.

---

## 4. 복구 전략 개요

Kernel/DTB 복구는 두 단계로 구성한다.

```text
1차 복구:
  SD boot partition 안에 보관된 정상 Kernel/DTB 세트를 이용해 부팅

2차 복구:
  U-Boot 단계에서 TFTP로 Host PC의 정상 Kernel/DTB를 RAM에 로드하여 부팅
```

현재 repo의 실제 스크립트, 파일명, 배포 경로는 로컬 구현을 따른다. 이 문서는 특정 스크립트 이름을 강제하지 않고, 파이프라인이 가져야 할 역할과 흐름만 정의한다.

---

## 5. Bootloader 복구 흐름

Bootloader 복구는 기존에 확인한 OSPI flash 기반 복구 전략을 유지한다.

```text
SD bootloader 문제가 발생한 경우
  → boot mode switch를 OSPI boot로 변경
  → OSPI flash에 저장된 정상 bootloader로 부팅
  → U-Boot가 SD card의 Kernel/DTB/rootfs를 사용해 Linux 진입
  → Linux 진입 후 SD boot partition의 bootloader 이미지 복구
```

이 흐름의 목적은 다음과 같다.

```text
SD card의 tiboot3.bin / tispl.bin / u-boot.img가 깨져도
OSPI flash의 정상 bootloader를 통해 보드를 다시 살린다.
```

따라서 OSPI flash의 bootloader는 실험 대상이 아니라 **golden recovery bootloader**로 취급한다.

---

## 6. Kernel/DTB 1차 복구 흐름: SD 내부 정상 이미지 사용

Kernel/DTB 실험을 위해 SD boot partition에는 최소한 다음 두 종류의 이미지 세트를 둘 수 있다.

```text
정상 이미지 세트:
  이미 부팅 성공이 확인된 Kernel + DTB

실험 이미지 세트:
  새로 빌드해서 검증할 Kernel + DTB
```

현재 보드는 extlinux.conf 기반이 아니라 TI SDK의 U-Boot env/bootcmd 기반으로 보이므로, 실제 구현은 다음 중 repo에 맞는 방식을 선택한다.

현재 repo의 실제 baseline 경로는 다음과 같다.

```text
bootloader:
  /run/media/boot-mmcblk1p1/tiboot3.bin
  /run/media/boot-mmcblk1p1/tispl.bin
  /run/media/boot-mmcblk1p1/u-boot.img

kernel:
  /boot/Image

dtb:
  /boot/dtb/ti/k3-am642-sk.dtb
```

즉, 이 문서에서 말하는 “Kernel/DTB 정상 세트”는 현재 repo 기준으로는 **SD boot partition(FAT)** 이 아니라 **rootfs 쪽 `/boot`, `/boot/dtb/ti/` 경로**에 두는 것이 맞다.

```text
방식 A:
  uEnv.txt 또는 U-Boot env에서 로드할 Kernel/DTB 파일명을 전환

방식 B:
  deploy script가 현재 부팅 대상 파일을 test 이미지로 교체하되,
  정상 이미지를 별도 위치에 항상 보관

방식 C:
  U-Boot prompt에서 수동으로 정상 Kernel/DTB 파일을 load하여 부팅
```

현재 repo 기준으로는 **방식 B + 방식 C** 조합이 가장 자연스럽다.

이유:

```text
- 현재 deploy script는 active 파일 overwrite 방식이다.
- current boot flow는 extlinux가 아니라 U-Boot env 기반이다.
- 따라서 우선은 active + golden 파일 체계 또는 active + backup 체계를 두고,
  필요 시 U-Boot prompt에서 수동 load 하는 복구 절차가 잘 맞는다.
```

핵심은 파일 배치 방식이 아니라 다음 조건을 만족하는 것이다.

```text
- 정상 Kernel/DTB 세트가 SD 내부에 항상 존재해야 한다.
- 실험 Kernel/DTB가 실패해도 정상 세트를 선택할 수 있어야 한다.
- 정상 세트는 “마지막으로 부팅 성공이 확인된 이미지”만 승격해야 한다.
```

---

## 7. Kernel/DTB 2차 복구 흐름: U-Boot TFTP 사용

SD 내부의 정상 이미지 선택이 어렵거나, `/boot`와 `/boot/dtb/ti/` 아래의 Kernel/DTB 파일 구성이 꼬인 경우를 대비해 TFTP 복구 흐름을 둔다.

큰 흐름은 다음과 같다.

```text
1. 보드를 U-Boot prompt에서 정지
2. U-Boot Ethernet 사용 가능 여부 확인
3. Host PC의 TFTP server를 통해 정상 Kernel/DTB를 다운로드
4. 다운로드한 Kernel/DTB를 RAM에서 직접 부팅
5. rootfs는 기존 SD card의 rootfs partition 사용
6. Linux 진입 후 SD 내부의 `/boot`와 `/boot/dtb/ti/`를 복구
```

이 방식의 의미는 다음과 같다.

```text
Bootloader:
  SD 또는 OSPI의 정상 U-Boot 사용

Kernel:
  Host PC의 TFTP 서버에서 RAM으로 로드

DTB:
  Host PC의 TFTP 서버에서 RAM으로 로드

RootFS:
  기존 SD card의 /dev/mmcblk1p2 또는 PARTUUID 기반 rootfs 사용
```

현재 `U-Boot Ethernet/TFTP`는 가능성이 높다고 판단하고, 파이프라인에는 복구 옵션으로 포함한다. 단, 현재 repo에는 아직 **실제 TFTP recovery 성공 로그가 없으므로**, 1차 목표는 자동화가 아니라 **수동 U-Boot command template 문서화**가 맞다.

---

## 8. 파이프라인에 포함할 역할

로컬 repo의 스크립트 이름은 현재 구조에 맞추되, 역할은 다음 단위로 나누는 것이 좋다.

```text
Build 계층
  - bootloader build
  - kernel + dtb build
  - dtb-only build

Deploy 계층
  - bootloader deploy to SD
  - kernel + dtb deploy to SD
  - dtb-only deploy to SD

Recovery 계층
  - OSPI bootloader recovery 절차 문서화
  - SD 내부 정상 Kernel/DTB 복구 절차 문서화
  - TFTP Kernel/DTB recovery command template 생성 또는 문서화
```

중요한 점은 `build`, `deploy`, `recovery`를 섞지 않는 것이다.

```text
build:
  Host PC에서 산출물을 만든다.

deploy:
  정상 동작 중인 Linux에 SSH/SCP로 산출물을 배포한다.

recovery:
  Linux가 올라오지 않는 상황에서 U-Boot 또는 OSPI boot path를 이용해 보드를 살린다.
```

---

## 9. 추천 운영 흐름

### 9.1 Bootloader 실험

```text
1. bootloader 빌드
2. SD boot partition에 실험 bootloader 배포
3. SD boot mode로 부팅 검증
4. 실패 시 OSPI boot mode로 전환
5. OSPI bootloader로 Linux 진입
6. SD bootloader를 정상 이미지로 복구
```

### 9.2 Kernel + DTB 실험

```text
1. Kernel + DTB 빌드
2. 현재 repo 기준 `/boot/Image`, `/boot/dtb/ti/k3-am642-sk.dtb` 경로에 실험 Kernel/DTB 배포
3. SD boot로 부팅 검증
4. 실패 시 U-Boot 단계에서 정상 Kernel/DTB 선택
5. 필요 시 TFTP로 정상 Kernel/DTB를 RAM에 로드하여 부팅
6. Linux 진입 후 `/boot`와 `/boot/dtb/ti/`의 Kernel/DTB를 복구
```

### 9.3 DTB-only 실험

```text
1. DTB만 수정
2. DTB-only 빌드
3. SD boot partition에 실험 DTB만 배포
4. 기존 정상 Kernel + 실험 DTB 조합으로 부팅
5. 실패 시 정상 DTB로 복구
```

DTB-only 실험은 보드 브링업에서 가장 자주 반복될 가능성이 높다. 따라서 Kernel 전체 빌드와 분리된 빠른 빌드/배포 루프로 유지하는 것이 좋다.

---

## 10. RootFS에 대한 현재 범위

RootFS 복구 파이프라인은 현재 범위에서 제외한다.

현재 단계에서는 rootfs를 “안정 기준”으로 유지한다.

```text
현재 범위:
  bootloader
  kernel
  DTB

추후 범위:
  rootfs overlay
  package 추가
  service 설정
  A/B rootfs
  NFS rootfs
```

RootFS를 수정하기 시작하면 별도의 복구 전략이 필요하다.

```text
- rootfs backup
- rootfs overlay rollback
- init=/bin/sh emergency boot
- NFS rootfs
- A/B rootfs partition
```

하지만 현재 파이프라인의 1차 목표는 **부트로더와 Kernel/DTB 실험 루프를 안전하게 만드는 것**이다.

---

## 11. 로컬 AI Agent 작업 지시 요약

로컬 AI Agent에게는 다음 의도로 작업을 지시한다.

```text
현재 repo에 구축된 bootloader, kernel+dtb, dtb-only build/deploy 스크립트를 유지하면서,
Kernel/DTB 실패 시 복구 가능한 recovery pipeline을 추가한다.

복구 pipeline은 특정 구현을 과도하게 고정하지 말고,
현재 repo의 구조와 기존 스크립트 명명 규칙에 맞춰 자연스럽게 통합한다.
```

작업 범위는 다음으로 제한한다.

```text
- 부트로더 복구는 OSPI golden bootloader 전략으로 문서화
- Kernel/DTB 복구는 SD 내부 정상 이미지와 TFTP 복구 전략으로 문서화
- 필요한 경우 recovery helper script 또는 command template 추가
- rootfs 복구는 이번 범위에서 제외
```

Agent가 확인해야 할 항목은 다음이다.

```text
- 현재 deploy script가 어느 파일을 FAT boot partition에 쓰는지, 어느 파일을 rootfs `/boot`에 쓰는지
- 현재 uEnv.txt 또는 U-Boot env 기반 boot flow에서 Kernel/DTB 파일명을 어떻게 바꾸는지
- 정상 Kernel/DTB를 어디에 보관하는 것이 repo 구조에 가장 자연스러운지
- TFTP 복구 command를 문서로 둘지, helper script로 생성할지
- 복구 절차 문서를 docs 또는 board-specific note 중 어디에 둘지

현재 repo에 맞는 1차 권장 사항은 다음과 같이 정리한다.

```text
1. extlinux 도입 없이 현재 U-Boot env 기반 흐름을 유지한다.
2. kernel/DTB recovery는 rootfs `/boot` 기준으로 설계한다.
3. SD 내부 정상 세트는 active/test 개념보다 golden/test 파일명 체계를 우선 검토한다.
4. TFTP recovery는 helper script보다 수동 command template부터 확정한다.
```
```

---

## 12. 완료 기준

이 복구 파이프라인이 완료되었다고 판단하는 기준은 다음과 같다.

```text
1. Bootloader 실패 시 OSPI bootloader로 복구하는 절차가 문서화되어 있다.
2. Kernel/DTB 실패 시 SD 내부 정상 이미지로 복구하는 흐름이 정의되어 있다.
3. Kernel/DTB 실패 시 TFTP로 정상 이미지를 로드하는 흐름이 정의되어 있다.
4. rootfs는 현재 안정 기준으로 유지하며, 이번 범위에서 제외되어 있다.
5. build/deploy/recovery 역할이 문서상 분리되어 있다.
6. local repo의 기존 구조와 스크립트 이름을 해치지 않고 통합 가능하다.
```

---

## 13. 한 줄 요약

현재 파이프라인은 단순히 이미지를 빌드하고 SD card에 배포하는 수준에서 끝나면 안 된다.

```text
Bootloader는 OSPI golden bootloader로 복구하고,
Kernel/DTB는 SD 내부 정상 이미지 또는 U-Boot TFTP 부팅으로 복구한다.
RootFS는 현재 안정 기준으로 유지하고 추후 별도 복구 전략을 추가한다.
```

이 구조가 갖춰지면 SK-AM64B에서 SD card를 반복 탈착하지 않고도 bootloader, kernel, DTB bring-up 실험을 안정적으로 반복할 수 있다.
