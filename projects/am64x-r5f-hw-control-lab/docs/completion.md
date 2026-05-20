# Phase 1 현재 결과

## 요약

`am64x-r5f-hw-control-lab` 프로젝트를 실제 SK-AM64B 보드에 적용했고, 1차 목표였던 **A53 CLI ↔ R5F firmware RPMsg 상호동작**과 **A53/OS 측 trace 확인**을 검증했다.

이번 단계에서 확인한 범위는 다음과 같다.

1. 새 firmware를 `am64-main-r5f0_0-fw`로 배포하고 reboot 기반으로 적용할 수 있다.
2. `78000000.r5f`가 새 firmware로 `running` 상태가 된다.
3. A53 `r5ctl`이 `ping`, `status`, `gpio set` 명령으로 R5F와 정상 통신한다.
4. `r5ctl trace`가 `remoteproc` trace를 읽어 `[AM64X R5F HWLAB]` 로그를 보여준다.
5. SysConfig pinmux가 `MCU_SPI1_D0 -> MCU_GPIO0_8 (mode 7)`로 생성됨을 확인했다.

아직 남아 있는 범위는 **외부 LED/멀티미터를 사용한 실제 전압 변화 검증**이다.

## 실보드 검증 결과

### 1. firmware 적용

- 적용 전 active target: `/usr/lib/firmware/mcusdk-benchmark_demo/am64-main-r5f0_0-fw`
- 적용 후 active target: `/usr/lib/firmware/ti-bringup/am64x-r5f-hw-control-lab/am64-main-r5f0_0-fw`

재부팅 후 확인:

```text
remoteproc target: 78000000.r5f
state: running
firmware: am64-main-r5f0_0-fw
```

### 2. A53 CLI ↔ R5F 통신

실제 확인한 명령:

```text
r5ctl ping
  TX: PING
  RX: OK PONG

r5ctl status
  RX: OK STATUS core=78000000.r5f service=rpmsg_chrdev endpoint=14 gpio=0 gpio_candidate=MCU_GPIO0_8 uptime_ms=...

r5ctl gpio set 1
  RX: OK GPIO_SET value=1
```

위 세 명령은 모두 exit code `0`으로 완료되었다.

### 3. trace 확인

`r5ctl trace`는 최종적으로 exit code `0`으로 동작했고, 다음과 같은 로그를 확인했다.

```text
[AM64X R5F HWLAB] rx cmd=PING
[AM64X R5F HWLAB] tx rsp=OK PONG
[AM64X R5F HWLAB] rx cmd=STATUS
[AM64X R5F HWLAB] tx rsp=OK STATUS ...
[AM64X R5F HWLAB] rx cmd=GPIO_SET 1
[AM64X R5F HWLAB] gpio configured candidate=MCU_GPIO0_8 base=0x04201000 pin=8
[AM64X R5F HWLAB] gpio candidate=MCU_GPIO0_8 value=1
```

trace resolved path는 보드 상태에 따라 달라질 수 있으며, 이번 재부팅 후에는 `remoteproc1`이 `78000000.r5f`에 대응했다.

## boot / runtime 관찰

UART 동기화 로그 `logs/runtime_log` 기준으로 다음 커널 메시지를 확인했다.

```text
remoteproc remoteproc1: Booting fw image am64-main-r5f0_0-fw, size 465264
virtio_rpmsg_bus virtio0: creating channel rpmsg_chrdev addr 0xe
remoteproc remoteproc1: remote processor 78000000.r5f is now up
```

즉 부팅 단계에서 remoteproc/RPMsg 생성까지는 정상적으로 진행되었다.

## SysConfig GPIO pinmux 확인

generated SysConfig 결과에서 다음을 확인했다.

```text
GPIO_LAB_OUT_BASE_ADDR = CSL_MCU_GPIO0_BASE
GPIO_LAB_OUT_PIN       = 8
GPIO_LAB_OUT_DIR       = GPIO_DIRECTION_OUTPUT
```

또한 generated pinmux 주석에서:

```text
MCU_GPIO0_8 -> MCU_SPI1_D0 (C7)
PIN_MODE(7)
```

을 확인했다.

이 정보는 **SoC/package pinmux 수준 확인**까지를 의미한다. 아직 board connector pin 번호나 외부 LED 배선 검증 완료를 뜻하지는 않는다.

## 해석

현재 상태는 다음과 같이 정리한다.

1. RPMsg 통신 경로는 정상이다.
2. R5F firmware trace는 A53/OS 측에서 확인 가능하다.
3. `MCU_GPIO0_8`에 대한 SysConfig pinmux 구현은 repo에 반영되었다.
4. 남은 일은 사용자가 실제 보드에서 외부 LED 또는 측정기로 전압 변화/점멸을 확인하는 것이다.

## Blink / 계측 해석 메모

`gpio set 0/1`은 멀티미터로 정적 0V / 3.3V 근처를 확인하는 데 적합하다.

반면 `gpio blink <count>`는 200ms 단위로 상태가 바뀌므로, 일반 멀티미터로는 평균값처럼 보이거나 기대한 ON/OFF 반복이 뚜렷하지 않을 수 있다. blink 관측은 외부 LED, 로직 애널라이저, 오실로스코프가 더 적합하다.

또한 `GPIO_BLINK 10`처럼 긴 명령은 R5F가 전체 blink를 마친 뒤 응답을 보내므로, host timeout이 너무 짧으면 CLI timeout 후 kernel에 `msg received with no recipient`가 남을 수 있다. 이는 blink loop 자체 실패가 아니라 늦은 reply와 endpoint close의 조합으로 해석해야 한다.

추가로 현재 A53 CLI는 명령마다 endpoint를 새로 여는 구조이므로, timeout 뒤 늦게 도착한 응답이 다음 명령에서 stale reply로 읽힐 가능성도 있다. 예를 들어 `gpio blink 10` timeout 직후 `status`가 이전 `OK GPIO_BLINK ...` 응답을 받는 현상이 가능하다. 이 문제를 근본적으로 없애려면 요청 ID 기반 응답 매칭 또는 persistent endpoint 구조가 필요하다.

## 남은 수동 검증

사용자가 직접 해야 하는 마지막 확인은 아래와 같다.

1. `MCU_GPIO0_8`에 해당하는 실제 connector pin 번호 재확인
2. GND / 3.3V 위치 재확인
3. 외부 LED + 저항 또는 멀티미터 연결
4. `r5ctl gpio set 1`, `r5ctl gpio set 0`, `r5ctl gpio blink 3` 실행
5. 실제 전압 변화 또는 LED 점멸 관찰

## 주의

- lab firmware 적용 후 baseline 서비스가 재부팅 뒤 다시 올라오면 trace에 `ERR UNKNOWN_CMD`가 반복적으로 남을 수 있다.
- 전용 lab 검증 전에는 `benchmark_server.service`, `rpmsg_json.service`를 중지한 뒤 확인하는 편이 좋다.
- generated `GPIO_init()`은 boot 시점에 대상 GPIO를 low로 초기화할 수 있으므로, 외부 회로 연결 상태를 먼저 점검해야 한다.
