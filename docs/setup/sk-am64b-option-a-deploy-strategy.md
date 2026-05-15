# SK-AM64B Option A Deploy 전략

## 목적

이 문서는 현재 SK-AM64B 브링업 파이프라인에서 사용할 배포 전략을 확정한다.

Option A의 의미는 다음과 같다.

```text
현재 검증된 U-Boot environment 기반 부팅 경로를 존중한다.
아직 extlinux/test-golden 부트 모델로 강제 전환하지 않는다.
```

## BASE 가정

현재 검증된 부팅 동작은 다음과 같다.

```text
U-Boot env가 /boot/Image 에서 kernel을 읽는다.
U-Boot env가 /boot/dtb/ti/k3-am642-sk.dtb 에서 DTB를 읽는다.
Linux는 root=PARTUUID=076c4a2a-02 로 부팅한다.
```

## 전략 개요

### Bootloader deploy 범위

대상:

```text
/run/media/boot-mmcblk1p1/tiboot3.bin
/run/media/boot-mmcblk1p1/tispl.bin
/run/media/boot-mmcblk1p1/u-boot.img
```

동작:

1. 로컬 artifact 존재 여부 확인
2. 보드의 `/tmp` staging 경로로 먼저 복사
3. 보드에서 timestamped backup 생성
4. FAT boot partition의 active 파일 교체
5. `sync`
6. 필요 시 reboot

추가 운영 원칙:

- bootloader / kernel / DTB artifact 크기 기준으로는 `/tmp` staging이 충분하다.
- staging은 임시 작업 영역이며 성공 시 정리한다.
- backup은 rollback 용도이며 최근 3개만 유지한다.

### Kernel deploy 범위

대상:

```text
/boot/Image
/boot/dtb/ti/k3-am642-sk.dtb
```

동작:

1. 로컬 `Image` 존재 여부 확인
2. 선택된 DTB 존재 여부 확인
3. 보드에서 현재 active 파일 백업
4. 새 kernel 및 DTB를 `/tmp` staging 이름으로 먼저 복사
5. 가능하면 atomic하게 active 파일 교체
6. `sync`
7. 필요 시 reboot

추가 운영 원칙:

- staging은 checksum 검증과 active 교체 전 임시 보관용이다.
- 현재 kernel + baseline DTB 크기(약 43MB)는 `/tmp` staging으로 충분히 감당 가능하다.
- backup은 현재 active 상태를 되돌리기 위한 rollback 용도다.
- kernel/DTB backup은 최근 3개만 유지한다.

### DTB-only deploy 범위

대상:

```text
/boot/dtb/ti/k3-am642-sk.dtb
```

동작:

1. `/boot/Image`는 덮어쓰지 않음
2. 현재 DTB 백업
3. active DTB만 교체
4. 검증을 위해 reboot

### RootFS-only deploy 범위

대상:

```text
/etc
/usr/local
/lib/firmware
기타 overlay 관리 파일
```

동작:

- bootloader build 없음
- kernel rebuild 없음
- 변경에 꼭 필요하지 않으면 DTB도 교체하지 않음

## OSPI의 역할

Option A에서 OSPI Flash는 단순 참고 저장장치가 아니라 **SD bring-up 반복작업을 위한 recovery anchor**로 사용한다.

의미:

```text
SD 쪽 bootloader를 반복적으로 바꾸다가 SD boot가 깨져도,
OSPI에 known-good bootloader가 남아 있으면 boot mode switch 변경으로
U-Boot까지 다시 살린 뒤 SD kernel/rootfs를 통해 Linux에 진입하여 복구할 수 있다.
```

즉 Option A는 다음 이중 구조를 전제로 한다.

```text
1차 실험 대상: SD bootloader / SD kernel / SD DTB / SD rootfs
복구 기준점:  OSPI의 known-good bootloader
```

## 언제 OSPI에 bootloader를 write 하는가

다음 경우에는 TI prebuilt 또는 이미 검증된 bootloader를 OSPI에 먼저 기록해 두는 것을 권장한다.

1. SD bootloader를 반복적으로 교체하며 bring-up을 진행할 때
2. `tiboot3.bin`, `tispl.bin`, `u-boot.img`를 직접 build/deploy 하면서 실패 가능성이 있을 때
3. UART만으로 복구하는 것보다 Linux/SSH 복구 경로를 빠르게 확보하고 싶을 때
4. SD boot partition overwrite 작업을 자동화하기 전에 known-good 부트 기준점을 확보해야 할 때

권장 운영 원칙:

```text
OSPI에는 known-good bootloader를 유지하고,
SD는 반복 실험 대상 영역으로 사용한다.
```

## OSPI에 무엇을 write 하는가

현재 기준으로 OSPI의 bootloader 관련 파티션은 다음을 의미한다.

```text
ospi.tiboot3
ospi.tispl
ospi.u-boot
```

현재 repo 기준 권장 first-write source는 다음과 같다.

```text
TI prebuilt bootloader 이미지
또는 이미 UART/실보드에서 검증된 known-good 조합
```

초기 안정화 단계에서는 **직접 실험 중인 self-built SD bootloader를 곧바로 OSPI golden으로 승격하지 않는다.**

## 언제 boot mode switch를 OSPI로 바꾸는가

다음 조건 중 하나라도 충족하면 OSPI boot로 전환하는 recovery 절차를 고려한다.

1. SD에서 SPL/U-Boot 진입 실패
2. SD bootloader overwrite 이후 UART 출력이 기대와 다름
3. `tiboot3.bin`, `tispl.bin`, `u-boot.img` 중 하나가 손상되었을 가능성이 있음
4. SD bootloader 쪽 문제로 SSH 재진입이 불가능함

반대로 다음 경우는 보통 OSPI 전환 없이도 처리 가능하다.

- kernel only 문제
- DTB only 문제
- rootfs only 문제
- Linux까지는 올라오지만 서비스/드라이버만 이상한 경우

## OSPI recovery 절차

현재 Option A 기준 recovery 절차는 다음과 같이 본다.

```text
1. SD bootloader 문제 의심
2. 보드 전원 차단
3. boot mode switch를 OSPI boot 쪽으로 변경
4. 보드 부팅
5. OSPI의 known-good bootloader로 U-Boot 진입
6. 이후 SD kernel/rootfs를 통해 Linux 진입 확인
7. SSH 또는 UART 기반으로 SD bootloader 복구
8. 필요 시 SD kernel/DTB도 함께 복구
9. 보드 전원 차단
10. boot mode switch를 다시 SD 기준 상태로 복귀
11. SD 부팅 재검증
```

## OSPI write와 반복 작업의 관계

반복 bring-up 관점에서는 OSPI write를 한 번 해두고 끝내는 것이 아니라, 다음 기준으로 관리한다.

### OSPI를 다시 write 해야 하는 경우

- 현재 OSPI golden이 너무 오래되어 SD와의 호환성이 떨어질 때
- 검증된 새 U-Boot 조합을 golden 기준으로 승격하기로 결정했을 때
- OSPI bootloader 자체가 손상되었거나 다른 실험으로 덮어써졌을 때

### OSPI를 함부로 다시 write 하지 않는 경우

- 아직 충분히 검증되지 않은 self-built bootloader만 있는 경우
- SD 쪽 실험 중인 artifact를 그대로 golden으로 쓰기 위험한 경우

## deploy 전략에 포함되는 Recovery Note

bootloader deploy는 항상 다음을 전제로 한다.

```text
배포 실패 시 SD에서 직접 복구가 안 될 수 있다.
그 경우 OSPI boot + boot mode switch 전환이 복구 경로가 된다.
```

따라서 deploy 전 체크리스트에는 다음이 들어가야 한다.

- OSPI golden bootloader 존재 여부
- 현재 boot mode switch 기준 상태 기록
- UART 사용 가능 여부
- SD와 OSPI 각각의 복구 경로 인지 여부

## 지금 Option A를 선택하는 이유

Option A가 현재 가장 안전한 이유는 다음과 같다.

1. 이미 검증된 U-Boot environment 동작을 유지한다.
2. 파이프라인 초기 단계에서 boot policy 자체를 다시 쓰지 않는다.
3. 현재 보드의 source of truth와 deploy 로직을 일치시킨다.
4. bootloader, kernel, DTB-only, rootfs loop를 독립적으로 운영할 수 있다.

## 아직 바꾸지 않을 항목

첫 deploy script 구현에서는 다음 값을 바꾸지 않는다.

- `bootcmd`
- `bootcmd_ti_mmc`
- `bootpart`
- `bootdir`
- `fdtfile`
- `get_fdt_mmc`
- `get_kern_mmc`
- `run_kern`

또한 아직 다음 구조를 주 경로로 도입하지 않는다.

- `extlinux.conf` 기반 test/golden switching
- FAT boot partition DTB 선택 구조
- alternate boot menu policy

## 향후 재검토 조건

다음 요구가 생기면 Option A를 넘어서는 구조를 검토한다.

- known-good / test kernel 간 자동 rollback 필요
- active 파일 overwrite 없이 A/B kernel 검증 필요
- 반복 bring-up에서 boot menu 선택이 필수화됨
- extlinux 또는 EFI menu를 표준 운용 경로로 강제해야 함

## 실제 deploy script 설계 방향

### Bootloader deploy script

실구현 대상:

```text
tools/install/install-bootloader-to-sd.sh
```

예상 인터페이스:

```bash
./tools/install/install-bootloader-to-sd.sh 192.168.0.110 [--reboot] [--dry-run]
```

추가 전제:

- active 파일 overwrite 전 backup 생성
- board-side staging은 휘발성 `/tmp`가 아니라 유지 가능한 경로 사용
- deploy 문서에서 OSPI recovery 절차를 함께 참조

### Kernel/DTB deploy script

실구현 대상:

```text
tools/install/install-kernel-to-sd.sh
```

예상 인터페이스:

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 all
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only
./tools/install/install-kernel-to-sd.sh 192.168.0.110 image-only
```

추가 전제:

- DTB-only deploy는 `/boot/dtb/ti/k3-am642-sk.dtb`만 교체
- kernel/DTB 문제는 보통 OSPI write 없이도 SD rootfs 경로에서 복구 가능
- bootloader 문제와 kernel/DTB 문제를 구분해서 대응

### RootFS overlay deploy script

향후 구현 대상:

```text
tools/install/deploy-rootfs-overlay-to-board.sh
```

## 검증 기준

각 deploy는 다음 증거로 검증해야 한다.

- bootloader 변경 -> UART SPL/U-Boot log
- kernel 변경 -> `uname -a`, boot log, driver/probe 동작
- DTB-only 변경 -> runtime device tree 또는 probe 변화
- rootfs-only 변경 -> 서비스 및 런타임 동작
