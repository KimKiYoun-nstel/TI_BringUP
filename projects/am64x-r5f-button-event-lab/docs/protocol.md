# 프로토콜

Phase 2 프로토콜은 RPMsg `rpmsg_chrdev` endpoint `14`를 통한 텍스트 기반 프로토콜이다.

## 명령

| A53 CLI | R5F command | 기대 응답 |
|---|---|---|
| `r5ctl ping` | `PING` | `OK PONG` |
| `r5ctl status` | `STATUS` | `OK STATUS ...` |
| `r5ctl button status` | `BUTTON_STATUS` | `OK BUTTON_STATUS ...` |
| `r5ctl button wait [timeout_ms]` | `BUTTON_WAIT <timeout_ms>` | `BUTTON_EVENT ...` 또는 timeout text |
| `r5ctl button monitor` | `BUTTON_MONITOR` | subscribe ack 후 이벤트 |
| `r5ctl event monitor` | `EVENT_MONITOR` | subscribe ack 후 이벤트 |

Phase 1의 GPIO output 명령은 의도적으로 Phase 2 workflow에 포함하지 않는다. `GPIO_*` 명령이 firmware까지 들어가면 `ERR UNSUPPORTED_CMD phase=button_event_lab`를 반환한다.

## 이벤트 형식

```text
BUTTON_EVENT source=SW1 gpio=MCU_GPIO0_6 value=<0|1> state=<pressed|released> edge=<falling|rising> count=<n> timestamp_us=<t>
```

상태 매핑:

| Raw value | State | Edge |
|---:|---|---|
| `0` | `pressed` | `falling` |
| `1` | `released` | `rising` |

이벤트는 30 ms 소프트웨어 debounce 구간이 지난 뒤 task context에서 생성된다. ISR은 bank status clear, pin sample, timestamp capture, pending flag 설정만 수행한다.
