# 프로토콜

현재 프로젝트 프로토콜은 RPMsg `rpmsg_chrdev` endpoint `14`를 통한 텍스트 기반 프로토콜이다.
Phase 4 2차 slice에서도 이 RPMsg 프로토콜 자체는 변경하지 않고, 별도 reserved-memory SHM status block을 A53이 `/dev/mem`으로 읽는 경로를 유지한다.
추가로 R5F는 SoC internal VTM sensor 0/1의 raw code와 milli-Celsius 값을 SHM에 기록하고, A53 `r5ctl shm-status`는 Linux hwmon 값과 delta를 같이 출력한다.

이 문서는 원래 Phase 2 button-event 실험용 규약을 정리했지만,
현재 baseline은 여기에 **Phase 3 command/event 모델 + Phase 4 SHM/VTM telemetry**까지 반영한 상태다.

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

`r5ctl shm-status`는 RPMsg command를 보내지 않는다. SK-AM64B 전용 reserved-memory `r5f-status-shm@a5800000`의 status block을 읽고 `seq_begin == seq_end` 조건으로 snapshot 일관성을 확인한 뒤 주요 runtime/GPIO/event metadata와 Linux `main0_thermal`, `main1_thermal` hwmon 기준값을 출력한다.

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

## Phase 4 SHM 상태 블록

이번 slice의 SHM ABI는 `projects/am64x-r5f-button-event-lab/include/r5f_status_shm.h`에 둔다.

```text
base = 0xa5800000
size = 0x00001000
magic = 0x52354653
version = 0x00010000
writer = R5F firmware
reader = A53 r5ctl shm-status
```

R5F는 `seq_begin`을 먼저 갱신하고 status field를 기록한 뒤 `seq_end`를 같은 값으로 맞춘다. A53은 retry하면서 `magic`, `version`, `size`, `seq_begin`, `seq_end`를 검증한다.

온도 관련 `soc_temp0/*`, `soc_temp1/*` 필드는 현재 R5F가 실제로 채운다. R5F는 VTM sensor index `0/1`의 raw code를 읽고 Linux `k3_j72xx_bandgap` driver와 같은 lookup 방식으로 milli-Celsius를 계산해 SHM에 기록한다. A53은 비교 기준으로 Linux hwmon의 `main0_thermal`, `main1_thermal` 값을 함께 출력한다.
