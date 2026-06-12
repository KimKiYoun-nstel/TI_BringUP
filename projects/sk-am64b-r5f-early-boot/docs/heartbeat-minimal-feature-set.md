# Early Boot Heartbeat Minimal Feature Set

## 목적

이 문서는 SK-AM64B R5F early boot heartbeat firmware의
**최소 기능 집합**을 정의하는 설계 문서다.

현재 단계는 source 구현이 아니라
기존 canonical R5F project에서 어떤 기능을 남기고 어떤 기능을 뒤로 미룰지
명확히 고정하는 단계다.

## 범위

이 문서가 다루는 대상은 다음 3개 파일 기준의 최소화 방향이다.

```text
main.c
example.syscfg
ipc_rpmsg_echo.c
```

source basis:

- entry/task shell: `projects/am64x-r5f-hw-control-lab/r5f/main.c`
- GPIO-free syscfg base: `projects/sk-am64b-rpmsg-test/r5f/example.syscfg`
- runtime logic upper baseline: `projects/am64x-r5f-hw-control-lab/r5f/ipc_rpmsg_echo.c`

## Non-goals

현재 최소 기능 집합에는 다음을 포함하지 않는다.

- RPMsg echo 기능 완성
- Linux userspace round-trip 검증
- GPIO output / input / blink 제어
- VTM temperature telemetry
- event counter / command parser / trace command
- build 실행
- appimage 생성
- 보드 반영

## 1. `main.c`에서 유지할 것

유지 대상:

- `System_init()`
- `Board_init()`
- static FreeRTOS task 생성 패턴
- `vTaskStartScheduler()`

이유:

- `projects/am64x-r5f-hw-control-lab/r5f/main.c`와
  `projects/sk-am64b-rpmsg-test/r5f/main.c`는 사실상 같은 구조다.
- early-boot heartbeat의 핵심 차이는 entry shell이 아니라 runtime logic 쪽에 있다.

현재 판단:

```text
main.c는 최소 기능 관점에서 거의 그대로 유지 가능
```

## 2. `example.syscfg`에서 유지할 것

우선 기준:

- `projects/sk-am64b-rpmsg-test/r5f/example.syscfg`

유지 대상:

- `ipc.enableLinuxIpc = true`
- 기본 memory/linker/MPU skeleton
- FreeRTOS + AM64x R5F context

이유:

- 초기 early-boot heartbeat는 GPIO 의존성 없이도 설계 가능하다.
- `sk-am64b-rpmsg-test` 쪽 syscfg는 `GPIO_LAB_OUT` 같은 board-specific GPIO 구성이 없어 더 단순하다.

보류/제거 대상:

- `projects/am64x-r5f-hw-control-lab/r5f/example.syscfg`에 있는 `GPIO_LAB_OUT`
- GPIO pin assignment
- GPIO 관련 generated symbol 전제

현재 판단:

```text
초기 heartbeat draft는 GPIO 없는 syscfg baseline을 우선 채택
```

## 3. `ipc_rpmsg_echo.c`에서 유지할 개념

상위 baseline:

- `projects/am64x-r5f-hw-control-lab/r5f/ipc_rpmsg_echo.c`

유지 대상은 전체 코드가 아니라 다음 개념이다.

### 3.1 Debug/uptime 기반 runtime skeleton

유지 이유:

- `ClockP_getTimeUsec()` 기반 시간 정보는 heartbeat publish 주기와 health 판단에 유용하다.
- `DebugP_log` prefix 구조는 추후 trace 관찰 시 식별성을 높인다.

### 3.2 heartbeat / SHM publish 개념

관련 reference:

- `projects/am64x-r5f-hw-control-lab/docs/shm-status-field-reference.md`

최소 필드 후보:

- `magic`
- `version`
- `abi_size`
- `seq`
- `heartbeat`
- `shm_update_count`
- `shm_update_period_ms`
- `uptime_ms`
- `core`

이유:

- 이 필드들만으로도 A53 쪽에서
  `R5F가 Linux 이전부터 살아서 주기적으로 상태를 publish 하는가`
  를 판단할 수 있다.

## 4. `ipc_rpmsg_echo.c`에서 제거 또는 defer 할 것

### 4.1 GPIO 관련 경로

defer 대상:

- `#include <drivers/gpio.h>`
- `AddrTranslateP_getLocalAddr()` 기반 GPIO base 계산
- `app_gpio_configure_if_needed()`
- `app_gpio_apply()`
- `app_gpio_init()`
- `APP_GPIO_NAME`, `APP_BLINK_DELAY_USEC`, `APP_BLINK_MAX_COUNT`

이유:

- early-boot heartbeat 최소 검증의 본질은 GPIO가 아니라
  `Linux 이전 heartbeat 생존` 확인이다.
- GPIO는 peripheral ownership / pinmux / SYSFW RM 충돌을 다시 끌고 올 수 있다.

### 4.2 RPMsg command/echo path

defer 대상:

- `PING`, `STATUS`, `GPIO_SET`, `GPIO_TOGGLE`, `GPIO_BLINK` command 처리
- `RPMessage_recv()` loop 중심 구조
- 문자열 parser / response formatter
- endpoint announce를 최소 기능 필수 조건으로 간주하는 것

이유:

- early-boot heartbeat는 Linux가 아직 준비되지 않아도 먼저 살아 있어야 한다.
- 따라서 최소 기능 구현이 `RPMessage_waitForLinuxReady()`에 묶이면 목적과 어긋난다.

### 4.3 고급 상태 필드

defer 대상:

- `rpmsg_endpoint`, `rpmsg_rx_count`, `rpmsg_tx_count`, `rpmsg_error_count`
- `last_command_id`, `last_error`
- `output_gpio_id`, `output_state`, `input_gpio_id`, `input_state`
- `event_count`, `last_event_*`
- `soc_temp*_*`

이유:

- 초기 heartbeat 검증에는 과하다.
- 필드가 많을수록 구현/reader ABI 부담이 커진다.

## 5. 최소 runtime shape

향후 구현 목표 shape는 다음에 가깝다.

```text
System_init / Board_init
  -> FreeRTOS task start
  -> SHM header init
  -> fixed period loop
       - uptime 갱신
       - seq / heartbeat / shm_update_count 증가
       - SHM publish
       - optional DebugP_log (rate-limited)
```

중요:

- 최소 heartbeat는 Linux ready를 기다리지 않는다.
- 즉 `RPMessage_waitForLinuxReady()`는 최소 heartbeat 경로의 필수 선행조건이 아니다.

## 6. A53 관찰 기대치

이 문서는 아직 runtime 결과를 주장하지 않는다.

다만 최소 heartbeat 구현이 완료되면 A53 측에서 우선 기대하는 관찰 포인트는 다음과 같다.

- SHM physical address가 기대값과 일치하는가
- `magic` / `version` / `abi_size`가 맞는가
- `seq`, `heartbeat`, `shm_update_count`가 시간이 지나며 증가하는가

## 7. 후속 구현 전 체크리스트

구현 전에 다음이 확정되어야 한다.

1. SHM 최소 필드 ABI
2. SHM physical address / reserved-memory 대응 방침
3. GPIO-free syscfg 유지 여부
4. `RPMessage_waitForLinuxReady()`를 최소 heartbeat 경로에서 제거할지 여부

## 관련 문서

- `../README.md`
- `heartbeat-source-selection.md`
- `../r5f/draft/README.md`
- `projects/am64x-r5f-hw-control-lab/docs/shm-status-field-reference.md`
