# Tools 사용 가이드

## 목적

`tools/` 디렉터리는 TI_BringUP 저장소에서 반복적으로 사용하는 준비, 빌드, 배포 스크립트를 모아 둔 운영 디렉터리이다.

이 문서는 실제 작업자가 어떤 순서로 어떤 스크립트를 사용해야 하는지, 그리고 Option A 기준에서 어떤 복구 경로를 염두에 둬야 하는지를 정리한다.

## 디렉터리 구성

```text
tools/
  env/      환경 변수 파일
  prepare/  workspace 준비 및 patch 적용
  build/    artifact build 스크립트
  install/  보드 반영(deploy/install) 스크립트
  uart/
    uartctl.py             daemon client CLI
    uartd.py               persistent UART daemon
```

## 기본 사용 순서

### 1. 환경 준비

```bash
source tools/env/sdk-12.00.00.07.04.env
./tools/build/check-env.sh
```

### 2. bootloader build

```bash
./tools/build/build-u-boot.sh all
```

산출물:

```text
out/u-boot/artifacts/tiboot3.bin
out/u-boot/artifacts/tispl.bin
out/u-boot/artifacts/u-boot.img
```

### 3. kernel build

```bash
./tools/build/build-kernel.sh all
```

산출물:

```text
out/kernel/artifacts/Image
out/kernel/artifacts/k3-am642-sk.dtb
out/kernel/modules/
```

### 4. deploy 전 검토

실제 write 전에 항상 다음을 먼저 본다.

- boot 대상 보드 IP
- 현재 boot mode switch 상태
- OSPI known-good bootloader 존재 여부
- UART 사용 가능 여부
- 실제 overwrite 대상 경로

### 5. dry-run 우선 실행

bootloader:

```bash
./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --dry-run
```

kernel/DTB:

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 all --dry-run
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --dry-run
```

kernel modules:

```bash
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy --dry-run
```

### 6. 실제 deploy

bootloader:

```bash
./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --reboot
```

kernel/DTB:

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 all --reboot
./tools/install/install-kernel-to-sd.sh 192.168.0.110 image-only --reboot
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
./tools/install/install-kernel-to-sd.sh 192.168.0.110 promote-golden
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden-dtb --reboot
```

kernel modules:

```bash
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy --verify-post-deploy
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 promote-golden
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 restore-golden
```

## UART daemon helper

UART 로그 감시, reboot 이후 boot 출력 추적, U-Boot 진입, 명령 전송, Linux shell prompt 확인 같은 반복 작업에는 daemon 모델을 기본으로 사용한다.

- `tools/uart/uartd.py`: UART 포트를 계속 점유하는 daemon
- `tools/uart/uartctl.py`: daemon에 접속해 `status`, `send`, `expect`, `tail`, `stop`를 수행하는 client CLI

사전 준비:

```bash
python3 -m pip install pyserial
```

daemon 방식 기본 예시:

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
./tools/uart/uartctl.py status
./tools/uart/uartctl.py tail
./tools/uart/uartctl.py expect 'Hit any key to stop autoboot' --timeout 5
./tools/uart/uartctl.py send '' --newline
./tools/uart/uartctl.py stop
```

이 모델에서는 `uartd.py`가 UART를 단독으로 열고, 모든 UART 출력은 기본적으로 `logs/runtime_log`에 append된다. 사용자나 상위 Agent는 직접 serial port를 다시 열지 않고 `uartctl.py`로 daemon에 붙어서 제어한다.

`uartd.py`/`uartctl.py`는 **persistent session** 용도다. 사람이 `tail`로 계속 UART를 보고 있고, 다른 Agent가 동시에 `expect` 또는 `send`를 수행해야 하는 경우를 기본 시나리오로 본다.

기본적으로 `uartd.py`가 `logs/runtime_log`에 append하므로, 작업 중 다른 terminal에서 다음처럼 바로 확인할 수 있다.

```bash
tail -f logs/runtime_log
```

daemon 모델에서 `uartd.py`는 기본적으로 `logs/runtime_log`를 사용한다. socket, pid, runtime log 경로를 바꾸려면 `--socket`, `--pid-file`, `--runtime-log` 옵션을 사용한다.

구조 설명, 역할 분리, terminal A/B 사용 예시는 `docs/common/UART_DAEMON_AGENT_WORKFLOW.md`를 참고한다.

## Option A 기준 동작 원칙

현재 파이프라인은 Option A를 따른다.

의미:

```text
현재 검증된 U-Boot environment 기반 SD boot flow를 유지한다.
부트 정책 자체를 먼저 바꾸지 않는다.
```

현재 deploy 대상:

- bootloader: `/run/media/boot-mmcblk1p1`
- kernel: `/boot/Image`
- DTB: `/boot/dtb/ti/k3-am642-sk.dtb`

## staging 과 backup 의 차이

두 용어는 목적이 다르다.

### staging

staging은 새 artifact를 active 경로에 반영하기 전에 잠시 올려두는 **임시 작업 영역**이다.

예:

```text
/tmp/ti-bringup-uboot-<timestamp>
/tmp/ti-bringup-kernel-<timestamp>
```

용도:

- 로컬 artifact를 보드로 먼저 복사
- checksum 비교
- active 파일 교체 전 중간 검증

원칙:

- bootloader / kernel / DTB 수준의 현재 artifact 크기에서는 `/tmp` tmpfs 용량으로 충분히 감당 가능하다.
- 성공한 deploy의 staging은 자동 정리된다.
- 실패한 deploy는 reboot 전까지 `/tmp`에 staging이 남아 있어 중간 상태를 확인할 수 있다.
- reboot 이후에는 `/tmp`가 사라지므로, overwrite 후 부팅 실패 분석의 주 수단은 UART 로그와 OSPI recovery 경로이다.

### backup

backup은 현재 active 상태를 되돌리기 위한 **복구용 사본**이다.

예:

```text
/run/media/boot-mmcblk1p1/backup/bootloader/<timestamp>
/boot/backup/kernel/<timestamp>
```

용도:

- overwrite 직전 상태 보관
- deploy 직후 문제 발생 시 같은 SD 기준 경로에서 빠르게 rollback

주의:

- bootloader backup은 SD boot partition 내부에 존재하므로 SD 자체 손상까지 막지는 못함
- SD 전체가 망가지는 상황의 recovery anchor는 OSPI known-good bootloader임
- full rootfs image, 대형 tarball, `.wic` 같은 큰 파일은 `/tmp` staging 대상이 아니라 별도 정책으로 다뤄야 한다.

## 정리 정책

현재 deploy script의 정리 정책은 다음과 같다.

- backup은 최근 3개만 유지
- 성공한 deploy의 staging은 자동 삭제
- 실패한 deploy의 staging은 분석을 위해 남을 수 있음

## OSPI의 역할

Option A에서 OSPI는 단순 부가 저장장치가 아니라 recovery anchor이다.

핵심 원칙:

```text
OSPI에는 known-good bootloader를 유지하고,
SD는 반복 실험 대상 영역으로 사용한다.
```

## 언제 OSPI를 활용하는가

### OSPI에 write 해두는 경우

- SD bootloader를 반복적으로 교체할 예정일 때
- deploy 자동화를 시작하기 전에 안전한 복구 경로를 확보해야 할 때
- 현재 보드가 SD bootloader 손상 시 자체 복구가 어렵다고 판단될 때

### boot mode switch를 OSPI로 바꾸는 경우

- SD에서 SPL/U-Boot 진입이 안 될 때
- `tiboot3.bin`, `tispl.bin`, `u-boot.img` overwrite 이후 UART 부트 로그가 비정상일 때
- SD bootloader 문제로 SSH 진입 경로가 끊겼을 때

### OSPI가 꼭 필요하지 않은 경우

- Linux까지는 정상 부팅되고, kernel/DTB/rootfs만 문제인 경우
- DTB-only 검증 실패를 다시 SD 경로에서 되돌릴 수 있는 경우

## Recovery 흐름

```text
1. SD bootloader 문제 발생
2. 보드 전원 차단
3. boot mode switch를 OSPI 쪽으로 변경
4. OSPI known-good bootloader로 부팅
5. SD kernel/rootfs를 통해 Linux 진입
6. SSH/UART로 SD bootloader 또는 kernel/DTB 복구
7. 보드 전원 차단
8. boot mode switch를 다시 SD 기준 상태로 복귀
9. SD 부팅 재검증
```

## Kernel/DTB golden 운용

현재 repo는 다음 파일 체계를 기준으로 recovery를 확장한다.

```text
/boot/Image
/boot/Image.golden
/boot/dtb/ti/k3-am642-sk.dtb
/boot/dtb/ti/k3-am642-sk.dtb.golden
```

원칙:

- active 파일은 현재 부팅 대상
- golden 파일은 마지막 부팅 성공이 확인된 정상 세트
- deploy 직후 자동 golden 승격은 하지 않음
- 실제 부팅 성공 확인 후 `promote-golden`으로 승격
- 실패 시 `restore-golden*` mode로 active를 되돌림

## 스크립트 사용 시 주의사항

- 실제 write 전에는 dry-run을 먼저 실행한다.
- backup 생성 여부를 확인하고 나서 overwrite 한다.
- bootloader 문제와 kernel/DTB 문제를 구분해서 대응한다.
- `/tmp` 같은 휘발성 영역은 장기 증적 보관용으로 믿지 않는다.
- UART 로그를 남겨야 bootloader 문제를 정확히 분류할 수 있다.

## 문서 연계

- boot-flow BASE: [../docs/common/am64x-boot-flow-baseline.md](file:///home/nstel/ti/TI_Bringup/docs/common/am64x-boot-flow-baseline.md)
- SK-AM64B BASE: [../docs/boards/SK-AM64B/boot-flow-baseline.md](file:///home/nstel/ti/TI_Bringup/docs/boards/SK-AM64B/boot-flow-baseline.md)
- Option A deploy 전략: [../docs/setup/sk-am64b-option-a-deploy-strategy.md](file:///home/nstel/ti/TI_Bringup/docs/setup/sk-am64b-option-a-deploy-strategy.md)
- OSPI boot 참고: [../docs/boards/SK-AM64B/2026-05-11_ospi-flash-bootloader-boot-review.md](file:///home/nstel/ti/TI_Bringup/docs/boards/SK-AM64B/2026-05-11_ospi-flash-bootloader-boot-review.md)
- U-Boot/TFTP kernel recovery: [../docs/setup/sk-am64b-u-boot-kernel-dtb-recovery-commands.md](file:///home/nstel/ti/TI_Bringup/docs/setup/sk-am64b-u-boot-kernel-dtb-recovery-commands.md)
