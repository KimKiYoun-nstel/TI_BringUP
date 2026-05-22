# 프로토콜

현재 프로젝트 프로토콜은 RPMsg `rpmsg_chrdev` endpoint `14`를 통한 텍스트 기반 프로토콜이다.

이 문서는 원래 Phase 2 button-event 실험용 규약을 정리했지만,
현재 baseline은 여기에 **Phase 3 1차 slice**를 반영한 상태다.

즉 현재는 다음 두 요구를 함께 만족한다.

- SW1 입력 event 경로 유지
- GPIO output/status/query command 재통합

## 명령

| A53 CLI | R5F command | 기대 응답 |
|---|---|---|
| `r5ctl ping` | `PING` | `OK PONG` |
| `r5ctl status` | `STATUS` | multi-line `OK STATUS ...` |
| `r5ctl gpio list` | `GPIO_LIST` | multi-line `OK GPIO_LIST ...` |
| `r5ctl gpio get <id>` | `GPIO_GET <id>` | multi-line `OK GPIO_GET ...` |
| `r5ctl gpio set <id> <0|1>` | `GPIO_SET <id> <0|1>` | `OK GPIO_SET ...` |
| `r5ctl event get` | `EVENT_GET` | `GPIO_EVENT ...` 또는 `OK EVENT_GET event=none ...` |
| `r5ctl event monitor` | `EVENT_MONITOR` | subscribe ack 후 이벤트 |

기존 Phase 2 회귀 확인을 위해 다음 command도 유지한다.

| 호환 CLI | R5F command | 비고 |
|---|---|---|
| `r5ctl button status` | `BUTTON_STATUS` | SW1 상태 확인용 legacy alias |
| `r5ctl button wait [timeout_ms]` | `BUTTON_WAIT <timeout_ms>` | 제한 시간 대기 |
| `r5ctl button monitor` | `BUTTON_MONITOR` | `event monitor`와 동일한 subscribe 경로 |

## GPIO 자원 기준

```text
Output GPIO:
  id     = mcu_gpio0_8
  signal = MCU_GPIO0_8
  name   = phase1_out

Input GPIO:
  id     = mcu_gpio0_6
  signal = MCU_GPIO0_6
  name   = phase2_sw1
  source = SW1
```

## 상태 응답 형식

`r5ctl status`는 현재 multi-line text 응답을 사용한다.

예:

```text
OK STATUS
firmware_version=0.3.0
core=78000000.r5f
service=rpmsg_chrdev
endpoint=14
uptime_ms=26161
output_gpio_id=mcu_gpio0_8
output_gpio_signal=MCU_GPIO0_8
output_gpio_name=phase1_out
output_state=0
input_gpio_id=mcu_gpio0_6
input_gpio_signal=MCU_GPIO0_6
input_gpio_name=phase2_sw1
input_state=1
input_state_name=released
event_count=0
last_event_type=none
last_event_timestamp_us=678
last_error=OK
```

## 이벤트 형식

현재 generic event 형식은 다음과 같다.

```text
GPIO_EVENT source=SW1 gpio_id=mcu_gpio0_6 signal=MCU_GPIO0_6 name=phase2_sw1 value=<0|1> state=<pressed|released> edge=<falling|rising> count=<n> timestamp_us=<t>
```

상태 매핑:

| Raw value | State | Edge |
|---:|---|---|
| `0` | `pressed` | `falling` |
| `1` | `released` | `rising` |

`event monitor`와 `button monitor`는 모두 이 event stream을 수신한다.

## 구현 메모

이벤트는 30 ms 소프트웨어 debounce 구간이 지난 뒤 task context에서 생성된다.
ISR은 bank status clear, pin sample, timestamp capture, pending sequence 증가만 수행한다.

현재 transport는 single endpoint 구조를 유지한다.
따라서 long-running command나 timeout 이후 stale reply 가능성은 여전히 protocol 상 주의사항으로 남아 있다.
