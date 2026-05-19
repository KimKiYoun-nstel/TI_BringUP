# 2026-05-19 SK-AM64B R5F remoteproc runtime reload 작업 로그

## 목적

SK-AM64B에서 A53 Linux app과 R5F RPMsg echo firmware를 local repo 기반으로 교체하면서, reboot 없이 runtime에서 `remoteproc` stop/start만으로 변경 사항을 반영할 수 있는지 확인했다.

## 배경

현재 개발 목표는 다음과 같다.

```text
Host local repo에서 A53 app 빌드
Host local repo에서 R5F firmware 빌드
Target rootfs의 /usr/lib/firmware에 firmware 반영
A53 Linux runtime에서 remoteproc stop/start
R5F firmware 변경 사항 확인
```

하지만 실제 실험에서 `78000000.r5f`에 대해 `echo stop > state`가 `Device or resource busy`로 실패했다.

## 확인한 구조

### firmware-name 원본

SDK source grep 결과, AM64x R5F/M4F firmware 이름은 Device Tree에 정의되어 있다.

```text
arch/arm64/boot/dts/ti/k3-am64-main.dtsi
arch/arm64/boot/dts/ti/k3-am64-mcu.dtsi
```

확인된 mapping:

```text
78000000.r5f  -> am64-main-r5f0_0-fw
78200000.r5f  -> am64-main-r5f0_1-fw
78400000.r5f  -> am64-main-r5f1_0-fw
78600000.r5f  -> am64-main-r5f1_1-fw
5000000.m4fss -> am64-mcu-m4f0_0-fw
```

### runtime DT 확인

`/sys/class/remoteproc/remoteprocX/device/of_node`를 따라가서 runtime DT에도 `firmware-name`이 존재함을 확인했다.

예:

```text
/sys/firmware/devicetree/base/bus@f4000/r5fss@78000000/r5f@78000000/firmware-name
am64-main-r5f0_0-fw
```

### kernel/module 구성

확인된 kernel config:

```text
CONFIG_REMOTEPROC=y
CONFIG_REMOTEPROC_CDEV=y
CONFIG_TI_K3_R5_REMOTEPROC=m
CONFIG_TI_K3_M4_REMOTEPROC=m
CONFIG_PRU_REMOTEPROC=m
CONFIG_RPMSG=y
CONFIG_RPMSG_CHAR=m
CONFIG_RPMSG_CTRL=m
CONFIG_RPMSG_NS=y
CONFIG_RPMSG_VIRTIO=y
```

해석:

```text
remoteproc core = built-in
TI K3 R5F/M4F/PRU remoteproc driver = module
rpmsg_char/rpmsg_ctrl = module
```

## 실험 내용

### userspace holder 가설 검증

초기 가설:

```text
A53 userspace app 또는 TI demo service가 /dev/rpmsg*를 잡고 있어서 remoteproc stop이 EBUSY가 된다.
```

baseline에서 다음을 수행했다.

1. `benchmark_server.service` 중지
2. `rpmsg_json.service` 중지
3. 관련 userspace 프로세스 없음 확인
4. `fuser /dev/rpmsg* /dev/rpmsg_ctrl*` 기준 holder 없음 확인
5. `78000000.r5f` stop 시도

명령:

```sh
echo stop > /sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc0/state
```

결과:

```text
Device or resource busy
```

### rpmsg bus entry 확인

추가로 `/sys/bus/rpmsg/devices`를 확인했다.

현재 보이는 RPMsg bus entry는 다음 remote core 쪽이었다.

```text
M4F
78200000.r5f
78400000.r5f
78600000.r5f
```

문제 target인 `78000000.r5f`에 대응하는 `virtio0.*` RPMsg bus entry는 눈에 띄지 않았다.

## 판단

이번 실험으로 다음 결론을 얻었다.

```text
78000000.r5f의 runtime stop 실패는 단순 userspace RPMsg endpoint 점유 때문만은 아니다.
```

근거:

```text
userspace service 중지됨
관련 프로세스 없음
/dev/rpmsg* holder 없음
문제 core의 rpmsg bus entry도 보이지 않음
그럼에도 remoteproc stop은 EBUSY
```

따라서 남은 가능성은 더 아래 계층이다.

```text
remoteproc driver 내부 상태
rproc-virtio subdevice 상태
TI K3 R5F remoteproc driver stop path
RPMsg/virtio teardown sequence
R5F firmware graceful shutdown 미지원
AM64x current SDK의 graceful shutdown 제약
```

## Decision

현재 개발 baseline은 reboot 기반 firmware reload로 둔다.

```text
R5F firmware 빌드
/usr/lib/firmware에 복사
symlink 갱신
sync
reboot
부팅 후 A53 app으로 RPMsg echo test
```

runtime stop/start는 별도 연구 항목으로 분리한다.

## Open Question

1. `78000000.r5f`만 stop이 실패하는가, 아니면 다른 R5F도 동일한가?
2. `78000000.r5f`의 `state=running` 상태에서 RPMsg bus entry가 없는 이유는 무엇인가?
3. 현재 R5F firmware가 Linux remoteproc graceful shutdown callback을 구현했는가?
4. TI Processor SDK Linux 12 / kernel 6.18.13 조합에서 R5F runtime graceful shutdown이 공식적으로 지원되는가?
5. stop 실패 시 dmesg에 어떤 remoteproc/rpmsg/virtio 로그가 남는가?

## Action Item

### 1. stop 실패 dmesg 원문 확보

```sh
dmesg -w
```

다른 터미널에서:

```sh
echo stop > /sys/class/remoteproc/remoteprocX/state
```

필터:

```sh
dmesg | grep -i -E "remoteproc|rproc|rpmsg|virtio|shutdown|busy|78000000|r5f" | tail -n 200
```

### 2. core별 stop 가능 여부 matrix 작성

대상:

```text
78000000.r5f
78200000.r5f
78400000.r5f
78600000.r5f
5000000.m4fss
```

기록 항목:

```text
remoteproc path
name
firmware
state before stop
rpmsg bus entry 존재 여부
fuser 결과
stop 결과
state after stop
dmesg 요약
```

### 3. R5F firmware source에서 graceful shutdown 구현 확인

확인 항목:

```text
shutdown IPC message callback
RPMsg endpoint cleanup
main loop exit condition
resource table
IPC/RPMessage deinit path
```

### 4. 자동화 스크립트 작성 시 name 기준 사용

`remoteprocX` 번호는 고정하지 않는다.

예:

```sh
TARGET_NAME="78000000.r5f"
for r in /sys/class/remoteproc/remoteproc*; do
    if [ "$(cat "$r/name" 2>/dev/null)" = "$TARGET_NAME" ]; then
        echo "target=$r"
    fi
 done
```

## 관련 문서

- `docs/common/am64x-remoteproc-firmware-name-flow.md`
- `docs/research/2026-05-19_sk-am64b_r5f0_0_remoteproc_stop_ebusy.md`
- `docs/boards/SK-AM64B/issues/2026-05-15_r5f-remoteproc-module-sync-and-rpmsg-race.md`
