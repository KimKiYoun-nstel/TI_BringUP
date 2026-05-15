# SK-AM64B Kernel/DTB Recovery 설계안

## 목적

이 문서는 현재 `TI_BringUP` repo의 실제 boot flow와 deploy 구조를 기준으로, Kernel/DTB recovery를 어떤 형태로 붙이는 것이 가장 자연스러운지 정리한 설계안이다.

이 문서는 구현 스크립트가 아니라 **적용 설계 기준**을 정의한다.

## 현재 기준

현재 baseline boot flow:

```text
U-Boot env 기반 direct boot
kernel  -> /boot/Image
dtb     -> /boot/dtb/ti/k3-am642-sk.dtb
rootfs  -> /dev/mmcblk1p2 (PARTUUID=076c4a2a-02)
```

즉 recovery 설계는 extlinux나 EFI menu가 아니라, **현재 U-Boot env + `/boot` 경로** 기준으로 맞춰야 한다.

## 복구 계층

Kernel/DTB recovery는 다음 두 단계로 나눈다.

### 1차 복구: SD 내부 정상 Kernel/DTB 세트 사용

목표:

```text
새 실험 Kernel/DTB가 실패해도,
SD 내부에 남겨둔 정상 세트를 이용해 다시 Linux에 진입한다.
```

### 2차 복구: U-Boot TFTP 부팅

목표:

```text
SD 내부의 Kernel/DTB 배치가 꼬였거나,
정상 세트 선택이 어려운 경우,
Host PC의 TFTP server에서 Kernel/DTB를 RAM으로 로드하여 부팅한다.
```

## 권장 파일 배치

현재 repo 기준으로 가장 자연스러운 1차 배치는 다음과 같다.

```text
/boot/Image                  현재 active kernel
/boot/Image.golden           마지막 부팅 성공이 확인된 kernel

/boot/dtb/ti/k3-am642-sk.dtb         현재 active dtb
/boot/dtb/ti/k3-am642-sk.dtb.golden  마지막 부팅 성공이 확인된 dtb
```

선택 이유:

- 현재 U-Boot env가 `/boot/Image`, `/boot/dtb/ti/k3-am642-sk.dtb`를 읽는다.
- extlinux 구조를 새로 만들 필요가 없다.
- deploy script가 golden 승격/active 교체를 명시적으로 다루기 쉽다.

## 권장 운용 규칙

### golden 승격 규칙

다음 조건을 만족한 경우에만 golden으로 승격한다.

```text
1. U-Boot까지 정상 진입
2. Linux kernel 부팅 성공
3. rootfs mount 성공
4. SSH 또는 UART 기준 기본 운영 확인
```

즉 **단순 deploy 성공**이 아니라 **실제 부팅 성공 확인 후** golden 승격이다.

### 실험 image 반영 규칙

기본 loop:

```text
1. 새 kernel 또는 dtb build
2. active 경로에 반영
3. reboot 검증
4. 성공 시 golden 갱신 여부 판단
5. 실패 시 golden 기준으로 복구
```

### DTB-only 규칙

DTB-only 실험은 다음 구조가 자연스럽다.

```text
active kernel 유지
active dtb만 교체
실패 시 golden dtb로 복구
```

이 루프는 가장 자주 반복될 가능성이 높다.

## U-Boot 수동 복구 개념

extlinux를 도입하지 않는 현재 구조에서는, 복구 경로로 다음 두 가지를 가진다.

### 방식 1: Linux 진입 후 파일 복구

조건:

- bootloader는 정상
- U-Boot 또는 Linux 진입 경로가 남아 있음

복구:

- SSH로 접속
- golden 파일을 active 파일로 복구

### 방식 2: U-Boot prompt에서 수동 load

조건:

- Linux 진입 실패
- U-Boot prompt까지는 진입 가능

복구 개념:

```text
U-Boot prompt에서
golden kernel/DTB 또는 TFTP로 받은 kernel/DTB를
직접 load 후 booti
```

## TFTP 복구 설계

현재 repo에서 TFTP recovery는 “가능성 높음” 상태이며, 다음 순서로 붙이는 것이 맞다.

### 1단계

문서에 수동 command template 추가

필요 항목:

- `serverip`
- `ipaddr`
- kernel load address
- dtb load address
- `booti` 인자
- rootfs bootargs 재사용 방식

### 2단계

실제 U-Boot TFTP recovery 성공 로그 확보

### 3단계

필요 시 helper script 또는 command generator 추가

즉 현재는 **command template 우선**, 자동화는 후순위다.

## build / deploy / recovery 역할 분리

이 repo에서 각 역할은 계속 분리 유지해야 한다.

```text
build:
  Host PC에서 artifact 생성

deploy:
  동작 중인 Linux에 SSH/SCP로 반영

recovery:
  Linux가 올라오지 않을 때 U-Boot 또는 OSPI 경로로 복구
```

이 셋을 섞으면 절차가 복잡해지고, 실패 원인도 추적하기 어려워진다.

## 현재 repo에 바로 추가 가능한 것

1. kernel/dtb golden 파일명 규칙 문서화
2. DTB-only 복구 규칙 문서화
3. TFTP recovery command template 문서화
4. golden 승격 기준 문서화
5. deploy script에 active/golden 조작 mode 추가
6. U-Boot 수동 복구 command template 문서화

## 아직 구현 전인 것

1. TFTP recovery 실증 로그 확보

## 현재 반영된 deploy mode

현재 kernel deploy script에는 다음 mode를 둘 수 있다.

```text
all                   active kernel + active dtb deploy
image-only            active kernel만 deploy
dtb-only              active dtb만 deploy
promote-golden        현재 active kernel/dtb를 golden으로 승격
restore-golden        golden kernel/dtb를 active로 복구
restore-golden-image  golden kernel만 active로 복구
restore-golden-dtb    golden dtb만 active로 복구
```

이 mode들은 다음 원칙을 따른다.

```text
- deploy와 recovery를 같은 스크립트 안에서 다루되,
  mode를 분리해서 역할을 명확히 유지한다.
- golden 승격은 실제 부팅 성공 확인 후 수동으로 수행한다.
- 복구는 active overwrite 전에 backup을 남긴다.
```

## 한 줄 요약

현재 repo 기준 Kernel/DTB recovery는 다음 순서로 가는 것이 가장 자연스럽다.

```text
OSPI는 bootloader recovery anchor로 유지하고,
Kernel/DTB는 SD 내부 golden 세트 + U-Boot TFTP 복구를 단계적으로 추가한다.
```

## 관련 문서

- [U-Boot kernel/dtb recovery command template](file:///home/nstel/ti/TI_Bringup/docs/setup/sk-am64b-u-boot-kernel-dtb-recovery-commands.md)
