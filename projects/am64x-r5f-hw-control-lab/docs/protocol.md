# RPMsg Text Command Protocol

## 목적

이 문서는 A53 `r5ctl`과 R5F firmware 사이에서 사용하는 Phase 1 text command 규약을 정리한다.

## Transport

- A53 library: `libti_rpmsg_char`
- Remote core id: `R5F_MAIN0_0`
- Service name: `rpmsg_chrdev`
- Endpoint: `14`
- A53 endpoint name: `am64x-r5ctl`
- 메시지 최대 크기: 496 byte

## A53 CLI와 R5F 명령 매핑

| A53 명령 | R5F text command | 기대 응답 |
|---|---|---|
| `r5ctl ping` | `PING` | `OK PONG` |
| `r5ctl status` | `STATUS` | `OK STATUS ...` |
| `r5ctl gpio set 0` | `GPIO_SET 0` | `OK GPIO_SET value=0` |
| `r5ctl gpio set 1` | `GPIO_SET 1` | `OK GPIO_SET value=1` |
| `r5ctl gpio toggle` | `GPIO_TOGGLE` | `OK GPIO_TOGGLE value=<0|1>` |
| `r5ctl gpio blink <count>` | `GPIO_BLINK <count>` | `OK GPIO_BLINK count=<count> value=0` |
| `r5ctl trace` | RPMsg 미사용 | local trace file 출력 |

R5F는 알 수 없는 명령에 `ERR UNKNOWN_CMD`, 잘못된 인자에 `ERR INVALID_ARG`를 반환한다. A53 CLI는 `OK`로 시작하지 않는 응답을 실패로 처리한다.

## Trace

R5F firmware는 `DebugP_log`에 `[AM64X R5F HWLAB]` prefix를 붙인다. 보드에서 trace는 remoteproc 번호가 바뀔 수 있으므로 이름 기반 경로를 우선 확인한다.

```bash
cat /sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc*/trace0
```

`r5ctl trace`는 위 경로와 debugfs의 `/sys/kernel/debug/remoteproc/remoteproc*/trace0` 후보를 순서대로 읽는다.

## GPIO 후보

현재 firmware hook은 SysConfig generated 설정을 통해 `MCU_SPI1_D0` pad를 `MCU_GPIO0_8` mode 7 출력으로 다룬다. package ball 주석은 `C7`이지만, connector-level 검증은 아직 완료되지 않았다. 또한 generated GPIO init은 boot 시점에 pinmux와 output-low 초기화를 수행할 수 있으므로, 실제 외부 LED 연결 전에는 회로와 측정 지점을 반드시 다시 확인한다. 문서와 응답은 계속 `gpio_candidate=MCU_GPIO0_8`이라고 표현한다.
