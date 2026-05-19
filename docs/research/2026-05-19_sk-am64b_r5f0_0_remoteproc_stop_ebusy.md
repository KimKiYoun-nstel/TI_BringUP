# 2026-05-19 SK-AM64B 78000000.r5f remoteproc stop EBUSY 분석

## 목적

SK-AM64B에서 `78000000.r5f` R5F core의 firmware를 runtime에 교체하기 위해 remoteproc stop/start를 시도했으나, `echo stop > state` 단계에서 `Device or resource busy`가 발생했다.

이 문서는 해당 현상의 재현 조건, 확인된 사실, 배제된 가설, 남은 가능성, 향후 검증 항목을 정리한다.

## 환경

| 항목 | 값 |
|---|---|
| Board | SK-AM64B |
| SoC | TI AM64x |
| Linux | 6.18.13-gc21449208550 |
| SDK | TI Processor SDK Linux AM64x 12.00.00.07.04 기반 |
| Target remote core | `78000000.r5f` |
| Target firmware-name | `am64-main-r5f0_0-fw` |
| 개발 목적 | A53 app + R5F RPMsg echo firmware runtime 반영 |

## 확인된 remoteproc 상태

`78000000.r5f`는 runtime에서 다음과 같이 확인되었다.

```text
/sys/class/remoteproc/remoteproc0/name     = 78000000.r5f
/sys/class/remoteproc/remoteproc0/firmware = am64-main-r5f0_0-fw
/sys/class/remoteproc/remoteproc0/state    = running
```

주의: `remoteproc0` 번호는 probe 순서에 따라 달라질 수 있으므로, 향후 스크립트에서는 반드시 `name` 기준으로 target을 찾는다.

## 확정된 실험 결과

baseline 상태에서 다음을 수행했다.

1. `benchmark_server.service` 중지
2. `rpmsg_json.service` 중지
3. 관련 userspace 프로세스 없음 확인
4. `fuser /dev/rpmsg* /dev/rpmsg_ctrl*` 기준 눈에 띄는 userspace holder 없음 확인
5. 아래 명령 수행

```sh
echo stop > /sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc0/state
```

결과:

```text
Device or resource busy
```

## 추가 확인 사항

현재 `/sys/bus/rpmsg/devices`를 확인하면 `78000000.r5f`에 대응하는 `virtio0.*` RPMsg bus entry가 보이지 않았다.

보이는 RPMsg bus entry는 다음 remote core 쪽이었다.

```text
M4F
78200000.r5f
78400000.r5f
78600000.r5f
```

문제의 `78000000.r5f` 쪽은 `state=running`임에도 눈에 띄는 RPMsg bus entry가 없었다.

## 의미

초기 가설은 다음과 같았다.

```text
A53 userspace app 또는 TI demo service가 /dev/rpmsg* endpoint를 잡고 있어서 remoteproc stop이 EBUSY가 된다.
```

그러나 이번 실험으로 다음이 확인되었다.

```text
userspace service 중지됨
관련 프로세스 없음
/dev/rpmsg* holder 없음
문제 core의 rpmsg bus entry도 보이지 않음
그럼에도 remoteproc stop은 EBUSY
```

따라서 현재 `78000000.r5f`의 runtime stop 실패는 단순 userspace RPMsg endpoint 점유 때문만은 아니라고 판단한다.

## 현재 결론

현재 증거상 `78000000.r5f`의 `EBUSY`는 userspace fd holder 문제가 아니라, 다음 계층의 문제일 가능성이 높다.

```text
remoteproc driver 내부 상태
rproc-virtio subdevice 상태
TI K3 R5F remoteproc driver stop path
RPMsg/virtio teardown sequence
R5F firmware graceful shutdown 미지원
AM64x current SDK의 graceful shutdown 제약
```

특히 `state=running`이지만 해당 core의 RPMsg bus entry가 보이지 않는 상태라면, Linux와 R5F 사이의 shutdown handshake 경로가 불완전할 가능성이 있다.

## 보드 브링업 관점 해석

이 문제는 Boot ROM/SPL/U-Boot 단계 문제가 아니다.

위치는 Linux boot 이후 remote processor lifecycle 관리 단계이다.

```text
Boot ROM
  -> SPL/U-Boot
  -> Linux Kernel boot
  -> ti_k3_r5_remoteproc module load/probe
  -> R5F firmware auto boot
  -> RPMsg/virtio channel 생성
  -> runtime stop 시도
  -> EBUSY
```

따라서 분석 대상은 다음이다.

```text
Linux kernel remoteproc core
ti_k3_r5_remoteproc driver
RPMsg/virtio subdevice
R5F firmware shutdown callback/resource table
```

## 현재 개발 루프 판단

현재 상태에서는 runtime firmware reload를 기본 개발 루프로 전제하지 않는다.

안정적인 baseline은 다음과 같이 둔다.

```text
R5F firmware 빌드
/usr/lib/firmware에 복사
필요 시 symlink 변경
sync
reboot
부팅 후 A53 app으로 RPMsg echo test
```

runtime stop/start는 별도 연구 과제로 분리한다.

## 추가 검증 항목

### 1. stop 실패 시 dmesg 확보

```sh
dmesg -w
# 다른 터미널에서 stop 시도
echo stop > /sys/class/remoteproc/remoteprocX/state
```

필터:

```sh
dmesg | grep -i -E "remoteproc|rproc|rpmsg|virtio|shutdown|busy|78000000|r5f" | tail -n 200
```

### 2. core별 stop 가능 여부 비교

다음 remote core에 대해 동일 조건에서 stop 결과를 비교한다.

```text
78000000.r5f
78200000.r5f
78400000.r5f
78600000.r5f
5000000.m4fss
```

### 3. rproc-virtio subdevice 상태 확인

```sh
ls -al /sys/class/remoteproc/remoteprocX/
ls -al /sys/class/remoteproc/remoteprocX/rproc-virtio* 2>/dev/null
find /sys/class/remoteproc/remoteprocX -maxdepth 3 -print
```

### 4. R5F firmware graceful shutdown 구현 여부 확인

MCU+ SDK project source에서 다음을 확인한다.

```text
Linux shutdown IPC message 처리 callback 존재 여부
RPMsg endpoint cleanup 여부
main loop 탈출 조건 존재 여부
resource table 포함 여부
RPMessage_deinit 또는 관련 IPC cleanup 여부
```

## 임시 운영 방침

- R5F firmware 변경 반영은 reboot 기반으로 진행한다.
- runtime reload는 가능하다고 가정하지 않는다.
- `remoteprocX` 번호는 고정하지 않는다.
- stop/start 스크립트는 `name` 기준으로 작성한다.
- `78000000.r5f` stop EBUSY는 board-specific issue로 추적한다.

## 관련 문서

- `docs/common/am64x-remoteproc-firmware-name-flow.md`
- `docs/bringup-logs/2026-05-19_sk-am64b_r5f_remoteproc_runtime_reload.md`
- `docs/boards/SK-AM64B/issues/2026-05-15_r5f-remoteproc-module-sync-and-rpmsg-race.md`
