# SK-AM64B R5F remoteproc / RPMsg 이슈 해결 정리

- 날짜: 2026-05-15
- 대상 보드: SK-AM64B
- 상태: Resolved on live board
- 권장 저장 위치: `docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md`
- 관련 영역: Linux Kernel, Device Tree, remoteproc, RPMsg, rootfs systemd service, kernel modules deploy

## 요약

이번 이슈는 최종적으로 **R5F bring-up 실패**가 아니라 다음 두 문제가 겹친 것으로 정리한다.

1. 실행 중인 커널 release와 rootfs의 kernel module tree가 불일치했다.
2. `rpmsg_json.service`가 R5F remoteproc 및 RPMsg character device 준비보다 먼저 시작되는 startup race가 있었다.

현재 live board clean boot 기준으로 다음이 확인되었으므로 해결 완료로 판단한다.

- `/lib/modules/$(uname -r)` 존재
- `ti_k3_r5_remoteproc`, `ti_k3_m4_remoteproc`, `rpmsg_char`, `rpmsg_ctrl` 로드됨
- `/sys/class/remoteproc/remoteproc0..4` 생성
- M4F 및 R5F 4개 core가 모두 `running`
- `/dev/rpmsg0..4`, `/dev/rpmsg_ctrl0..4` 생성
- `rpmsg_json.service`가 `active (running)` 상태
- `override.conf` drop-in 적용 확인
- `ExecStartPre` 대기 조건 성공
- `Avg round trip time` 로그 및 `oob_update.json` write 확인

## 보드 브링업 흐름상 위치

이 이슈는 AM64x 부팅 흐름에서 다음 구간에 위치한다.

```text
Boot ROM
  -> tiboot3.bin
  -> tispl.bin
  -> u-boot.img
  -> Linux Image / DTB load
  -> Kernel boot
  -> rootfs mount
  -> kernel modules / remoteproc probe
  -> R5F/M4F firmware boot
  -> RPMsg device 생성
  -> systemd userspace service 실행
```

따라서 이 문제는 Boot ROM, SPL, U-Boot 단계의 문제가 아니라 **Linux kernel 이후 remoteproc/RPMsg/userspace service ordering 문제**다.

## 최초 증상

초기에는 A53 Linux에서 R5F 제어가 정상적으로 동작하지 않는 것처럼 보였다.

관측된 증상:

- `modprobe ti_k3_r5_remoteproc` 실패
- `uname -r`와 `/lib/modules/<release>` 불일치
- 특정 관측 시점에서 `/sys/class/remoteproc/`가 비어 있음
- `remoteproc ... releasing ...` 로그 관측
- `rpmsg_json.service` 실패
- `_rpmsg_char_find_rproc: 78000000.r5f device is mostly yet to be created!`
- `Can't create an endpoint device: Bad address`

초기에는 remoteproc registration 자체가 실패하는 것으로 해석될 수 있었지만, clean reboot 후 재검증 결과 remoteproc bring-up 자체는 정상임이 확인되었다.

## 1차 원인: kernel Image와 module tree 불일치

실행 중인 커널 release와 rootfs에 설치된 module directory가 달랐다.

```text
running kernel: 6.18.13-gc21449208550
rootfs modules: /lib/modules/6.18.13-ti-00778-gc21449208550-dirty/
```

이 상태에서는 현재 커널 release에 맞는 remoteproc 관련 모듈을 `modprobe`가 찾을 수 없다.

### 조치

현재 커널 release 기준으로 다음 모듈을 rootfs에 다시 배포했다.

- `ti_k3_r5_remoteproc.ko`
- `ti_k3_m4_remoteproc.ko`
- `rpmsg_char.ko`
- `rpmsg_ctrl.ko`

관련 deploy helper:

- `tools/install/install-kernel-modules-to-sd.sh`
- `tools/install/verify-kernel-modules-postdeploy.sh`

의미:

> A53 Linux가 현재 실행 중인 커널 release와 일치하는 R5F/M4F remoteproc 및 RPMsg 모듈을 로드할 수 있게 되었다.

## 2차 원인: rpmsg_json.service startup race

모듈 동기화 후 remoteproc/RPMsg 자체는 clean boot에서 정상으로 올라왔지만, `rpmsg_json.service`가 너무 이른 시점에 시작되면 RPMsg character device가 아직 준비되지 않아 실패할 수 있었다.

실패 시나리오:

```text
systemd가 rpmsg_json.service 시작
  -> remoteproc1 또는 /dev/rpmsg_ctrl1 아직 없음
  -> rpmsg endpoint 생성 실패
  -> Bad address
```

이 문제는 remoteproc driver 자체 실패가 아니라 **userspace service ordering 문제**다.

### 조치

rootfs overlay에 systemd override drop-in을 추가했다.

권장 저장 위치:

```text
rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf
```

핵심 동작:

- `remoteproc1/state`가 `running`이 될 때까지 대기
- `/dev/rpmsg_ctrl1` 생성까지 대기
- 조건 충족 후 `rpmsg_json` 실행
- 실패 시 재시작 가능하도록 구성

## 최종 검증 결과

### kernel/module sync

```text
uname -r: 6.18.13-gc21449208550
/lib/modules/6.18.13-gc21449208550 존재
```

로드된 핵심 모듈:

```text
rpmsg_ctrl
rpmsg_char
ti_k3_r5_remoteproc
ti_k3_m4_remoteproc
ti_k3_common
```

판정: 정상

### remoteproc sysfs

확인된 remoteproc entry:

```text
remoteproc0 -> 5000000.m4fss
remoteproc1 -> 78000000.r5f
remoteproc2 -> 78200000.r5f
remoteproc3 -> 78400000.r5f
remoteproc4 -> 78600000.r5f
```

추가로 PRU/RTU/TXPRU 계열 remoteproc도 `remoteproc5..16`으로 등록되었다.

판정: 정상

### M4F/R5F state

```text
5000000.m4fss      running    am64-mcu-m4f0_0-fw
78000000.r5f       running    am64-main-r5f0_0-fw
78200000.r5f       running    am64-main-r5f0_1-fw
78400000.r5f       running    am64-main-r5f1_0-fw
78600000.r5f       running    am64-main-r5f1_1-fw
```

판정: 정상

### RPMsg device node

```text
/dev/rpmsg0
/dev/rpmsg1
/dev/rpmsg2
/dev/rpmsg3
/dev/rpmsg4
/dev/rpmsg_ctrl0
/dev/rpmsg_ctrl1
/dev/rpmsg_ctrl2
/dev/rpmsg_ctrl3
/dev/rpmsg_ctrl4
```

판정: 정상

### rpmsg_json.service

```text
Active: active (running)
Drop-In: /etc/systemd/system/rpmsg_json.service.d/override.conf
ExecStartPre: status=0/SUCCESS
```

주요 로그:

```text
Read 2009 bytes from /usr/share/benchmark-server/app/oob_data.json
Avg round trip time: 1309 usecs
Avg round trip time: 540 usecs
Total 2009 bytes have output
Write 2009 bytes to oob_update.json
```

판정: 정상

## 정상 bring-up 시퀀스

이번 검증에서 확인된 정상 시퀀스는 다음과 같다.

```text
DT platform device 생성
  -> remoteproc driver bind
  -> reserved memory assign
  -> remoteprocX is available
  -> firmware boot
  -> virtio_rpmsg_bus online
  -> remote processor is now up
  -> /dev/rpmsg* 생성
  -> rpmsg_json.service 실행
  -> RPMsg round-trip 성공
```

## 이번 이슈에서 배운 점

## Knowledge

- `modprobe` 성공 여부와 R5F 동작 여부는 별개다.
- `/sys/class/remoteproc/remoteprocX` 존재 여부는 Linux remoteproc registration 성공 여부를 판단하는 핵심 기준이다.
- `state=running`은 해당 remote core firmware가 Linux remoteproc에 의해 boot되어 실행 중임을 의미한다.
- `/dev/rpmsg_ctrlX`는 userspace에서 RPMsg endpoint를 만들기 위한 control device다.
- RPMsg userspace service 실패는 remoteproc bring-up 실패와 분리해서 봐야 한다.
- AM64x에서는 A53 Linux와 M4F/R5F remoteproc/RPMsg flow가 정상적으로 공존할 수 있다.

## Decision

- 이 이슈는 `R5F bring-up 실패`가 아니라 `kernel/modules sync + rpmsg userspace startup ordering` 이슈로 분류한다.
- `rpmsg_json.service`는 remoteproc/RPMsg 준비를 기다린 뒤 시작하도록 systemd override를 적용한다.
- 향후 유사 이슈에서는 먼저 `uname -r`, `/lib/modules/$(uname -r)`, `/sys/class/remoteproc/*/state`, `/dev/rpmsg*` 순서로 확인한다.

## Assumption

- 현재 검증은 SK-AM64B live board 및 현재 rootfs/kernel 조합 기준이다.
- `remoteproc1 == 78000000.r5f`라는 번호 매핑은 현재 부팅 환경 기준이다. 다른 DTB/driver probe 순서에서는 remoteproc 번호가 달라질 수 있으므로 name도 함께 확인해야 한다.

## Open Question

- `rpmsg_json.service`가 특정 remoteproc 번호에 고정 의존하는 구조를 유지할지, name 기반으로 더 견고하게 바꿀지 검토 필요.
- PRU/RTU/TXPRU remoteproc은 현재 offline이지만 이번 이슈 범위에는 포함하지 않는다.
- LED deferred probe 및 Wi-Fi NVS firmware missing 로그는 별도 이슈로 관리할지 판단 필요.

## Action Item

- 이 문서를 `docs/bringup-logs/`에 저장한다.
- systemd override 설정은 `rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf`에 유지한다.
- 관련 결정사항은 `docs/decisions/` 또는 `docs/decisions/DECISION_LOG.md`에 반영한다.
- task 상태는 `docs/tasks/TASK_BOARD.md`에 `Resolved`로 반영한다.

## Board Note

- SK-AM64B에서 M4F 1개와 R5F 4개가 remoteproc으로 정상 등록 및 running 상태까지 검증되었다.
- `/dev/rpmsg0..4`, `/dev/rpmsg_ctrl0..4`가 생성되어 userspace RPMsg path가 정상 동작한다.
- `rpmsg_json` 기준 round-trip time은 수백 usec에서 일부 1~2 ms 수준까지 관측되었다.

## Artifact

- `rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf`
- `tools/install/install-kernel-modules-to-sd.sh`
- `tools/install/verify-kernel-modules-postdeploy.sh`
- `docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md`
- `logs/runtime/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_verification.md` 또는 동등한 runtime log

## 재발 시 빠른 판정 명령

```sh
uname -r
ls -ld /lib/modules/$(uname -r)
lsmod | grep -E "remoteproc|rpmsg|ti_k3"
ls -al /sys/class/remoteproc/
for r in /sys/class/remoteproc/remoteproc*; do
    [ -e "$r" ] || continue
    echo "== $r =="
    cat "$r/name"
    cat "$r/state"
    cat "$r/firmware" 2>/dev/null
done
ls -al /dev/rpmsg*
systemctl status rpmsg_json.service
journalctl -u rpmsg_json.service -b --no-pager | grep -iE "round|trip|result|success|failed|error|bad address|mostly yet"
```

## 최종 결론

현재 live board 기준으로 R5F/M4F remoteproc bring-up 및 RPMsg userspace 통신은 정상이다.

이번 이슈는 R5F 자체가 동작하지 않는 문제가 아니라, 커널 모듈 배포 불일치와 userspace service startup timing race가 겹쳐 R5F bring-up 실패처럼 보였던 문제로 마무리한다.
