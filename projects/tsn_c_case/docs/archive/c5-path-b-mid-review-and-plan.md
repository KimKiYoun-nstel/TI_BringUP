# AM64x TSN C Case C5 Path B 중간 점검 및 실검증 계획

## 목적

현재 Path B 이식 상태를 중간 점검하고,

- 현재 어디까지 정상인지
- 실패 단계가 무엇인지
- 다음 수정 우선순위가 무엇인지
- Path B를 유지할지, Path A 재검토가 필요한지
- 보드 실검증을 어떤 순서로 진행할지

를 정리한다.

## 현재 결론 요약

현재 Path B는 다음까지는 성공했다.

1. Linux remoteproc가 ELF를 실제로 load하고 `running` 상태로 전환한다.
2. `.resource_table` 기반 Linux carveout 모델은 성립했다.
3. C2 ownership 분리 상태와 결합한 boot-time 실검증도 성공했다.

하지만 아직 다음은 성립하지 않았다.

1. 원본 `gptp_icssg_switch/dualmac` bootstrap이 보존되지 않았다.
2. donor의 ICSSG/DMA memory placement가 보존되지 않았다.
3. firmware는 현재 `boot entry` 이후 초반에서 더 진행하지 못한다.

따라서 현재 실패 단계는 다음처럼 보는 것이 맞다.

```text
A remoteproc load            = 성공
B firmware boot trace        = 실패
C Enet/ICSSG init trace      = 아직 못 감
D PHY/link                   = 아직 못 감
E L2 forwarding              = 아직 못 감
F gPTP                       = 아직 못 감
```

즉 **현재 문제는 gPTP 기능 문제가 아니라, bootstrap/scaffold/layout 등가성 문제**다.

## 1. bootstrap / init call graph 점검

### 원본 gptp_icssg_switch / dualmac

원본 예제의 초기화 순서는 동일하다.

```text
main()
  -> System_init()
  -> Board_init()
  -> create freertos_main()

freertos_main()
  -> Drivers_open()
  -> Board_driversOpen()
  -> EnetApp_mainTask()
  -> Board_driversClose()
  -> Drivers_close()
```

기준 파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/gptp_icssg_app/gptp_icssg_switch/am64x-evm/r5fss0-0_freertos/main.c`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/gptp_icssg_app/gptp_icssg_dualmac/am64x-evm/r5fss0-0_freertos/main.c`

### 현재 Path B

현재 Path B는 다음 흐름이다.

```text
main()
  -> System_init()
  -> Board_init()
  -> create freertos_main()

freertos_main()
  -> ipc_rpmsg_echo_main()
  -> EnetApp_mainTask()
```

즉 다음 호출이 빠져 있다.

- `Drivers_open()`
- `Board_driversOpen()`
- `Board_driversClose()`
- `Drivers_close()`

기준 파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/main.c`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/ipc_rpmsg_echo.c`

### 판단

이 항목만으로도 현재 Path B는 원본 bootstrap 보존 상태가 아니다.

특히 `Board_driversOpen()` 생략은 단순 cleanup 문제가 아니라,

- EEPROM open
- board handle 초기화
- MAC address fallback 경로

와 직접 연결된다.

따라서 **RPMsg echo 복구보다 donor bootstrap 복원이 우선**이라는 판단이 맞다.

## 2. SysCfg generated output 점검

비교 대상:

- `ti_enet_config.c`
- `ti_drivers_config.c`
- `ti_board_config.c`
- `ti_pinmux_config.c`
- `ti_drivers_open_close.c`
- `ti_board_open_close.c`

### 확인 결과 요약

#### 현재 Path B는 dualmac가 아니라 switch 계열이다

현재 generated output은 **switch donor와는 거의 일치**하고,
**dualmac donor와는 구조적으로 다르다**.

즉 현재 Path B는 다음 성격이다.

```text
ICSSG switch mode 1 instance + 2 MAC ports
```

반면 dualmac donor는 다음 성격이다.

```text
ICSSG dualmac mode 2 instance + 각 1 port
```

### ICSSG instance / port

- 현재 Path B: switch 스타일, peripheral 1개, port 2개
- dualmac donor: dualmac 스타일, peripheral 2개, port 각 1개

즉 현재 경로는 **bridge/forwarding 목표라면 switch 방향**으로 해석해야 한다.

### pinmux / MDIO / PHY

현재 generated output 기준으로:

- `RGMII1` 생성됨
- `RGMII2` 생성됨
- `PRU_ICSSG1_MDIO` 생성됨
- PHY addr는 기존 donor와 같은 `15` / `3` 조합

즉 pinmux/MDIO/PHY address 자체는 현재 SysCfg generated 결과에서 크게 틀어진 정황은 적다.

### UDMA / ring / channel

현재 generated output은 switch donor와 맞고, dualmac donor와는 다르다.

즉:

- TX/RX DMA 채널 구성은 switch donor 계열
- packet pool 크기도 switch donor 계열

### board config 누락 여부

- `ti_board_config.c`
- `ti_board_open_close.c`

자체는 switch donor와 거의 동일하다.

문제는 generated output 누락이 아니라,
**현재 bootstrap이 이 generated open/close 경로를 안 타고 있다는 점**이다.

### 판단

SysCfg generated output만 놓고 보면,
현재 Path B의 주요 문제는

- pinmux 생성 누락
- MDIO 생성 누락
- PHY address 오기입

보다는,

- switch/dualmac mode 선택 확정 필요
- donor bootstrap과 generated driver/board open path 불일치

에 있다.

## 3. linker map / section 배치 점검

### loadability 측면

현재 Path B는 remoteproc용으로는 맞다.

- `.resource_table` 존재
- `.resource_table @ 0xA0100000`
- Linux reserved carveout 범위 안에 image가 들어감

즉 A 단계 관점의 `loadability`는 통과했다.

### runtime 배치 측면

하지만 donor와는 다르다.

원본 donor는 다음 자원을 MSRAM 쪽에 둔다.

- `.icss_mem`
- `.enet_dma_mem`
- ICSSG pool/scratch/queue memory
- DMA descriptor/ring/pkt pool

현재 Path B는 이 전용 section을 유지하지 못했고,
해당 자원들이 대부분 DDR `.bss`로 들어간다.

즉 현재 상태는:

```text
donor:   hot ICSSG/DMA working set -> MSRAM
Path B:  hot ICSSG/DMA working set -> DDR .bss
```

### 위험

이 차이는 단순 주소 차이가 아니라 다음 위험으로 이어진다.

1. donor와 다른 latency 특성
2. cache maintenance 의존성 증가
3. DMA buffer/cacheable DDR 배치 위험
4. ICSSG working memory가 donor 전제와 달라질 가능성

### 판단

현재 Path B는

- `remoteproc loadability`는 확보했지만
- `runtime memory equivalence to donor`는 확보하지 못했다.

즉 C 단계 이전에 **memory placement parity 복원 작업이 필요**하다.

## 4. PRU / RTU / TX_PRU firmware 포함 여부

확인 결과 현재 Path B ELF 안에는 switch 계열 ICSSG firmware resource가 포함되어 있다.

즉:

- `RX_PRU_*`
- `RTU_*`
- `TX_PRU_*`

배열/리소스 자체가 통째로 빠진 정황은 현재 없다.

### 판단

현재 `Enet_open` 이전 failure를 firmware blob 누락으로 보는 것은 우선순위가 낮다.

즉 현재 핵심 문제는:

- PRU firmware missing

보다는,

- bootstrap mismatch
- memory placement mismatch
- donor runtime precondition mismatch

다.

## 5. FreeRTOS runtime 자원 점검

### main task priority / stack

원본 donor:

- priority = `2`
- stack = `8 KiB`

현재 Path B:

- priority = `configMAX_PRIORITIES - 1`
- 즉 보통 `31`
- stack = `16 KiB`

### 의미

현재 Path B는 donor보다 main task 우선순위가 과도하게 높다.

또한 이 high-priority task가 donor처럼 짧은 bootstrap wrapper가 아니라,
사실상 `EnetApp_mainTask()`로 길게 이어지는 구조다.

즉 init phase에서 donor와 scheduling 성질이 달라진다.

### heap / task stack

heap 자체는 donor보다 더 커서,
현재 가장 유력한 immediate blocker를 단순 heap 부족으로 볼 근거는 약하다.

### 판단

현재 RTOS 자원 항목에서 가장 위험한 것은:

1. main task priority 과상향
2. donor와 다른 bootstrap/task lifetime 구조

다.

## 6. 실보드 기준 현재 단계 판정

### A. remoteproc load 검증

판정: **성공**

근거:

- `state=running`
- firmware name override 적용 성공
- dmesg에서 immediate load error 없음

증적 문서:

- `projects/tsn_c_case/docs/c5-r5f-icssg-runtime-check.md`

### B. firmware boot trace 검증

판정: **실패**

근거:

- trace는 `main start` 한 줄만 확인
- `system and board init complete` 미확인
- `main task created` 미확인
- `EnetApp_mainTask entry` 미확인

즉 firmware는 entry까지는 진입했지만,
현재는 boot trace 기준으로 donor bootstrap 초반도 통과하지 못했다.

### C. Enet/ICSSG 초기화 trace 검증

판정: **진입 전**

근거:

- `EnetApp_updateCfg`
- `EnetApp_driverInit`
- `EnetApp_driverOpen`

관련 trace가 아직 안 나옴

### D. PHY/link 검증

판정: **미진행**

### E. L2 forwarding 검증

판정: **미진행**

### F. gPTP 검증

판정: **미진행**

## 7. 다음 수정 우선순위

우선순위는 다음 순서가 맞다.

### 1순위: donor bootstrap 복원

현재 Path B main 흐름을 donor 쪽으로 되돌려야 한다.

필수 조건:

```text
System_init()
Board_init()
Drivers_open()
Board_driversOpen()
EnetApp_mainTask()
Board_driversClose()
Drivers_close()
```

즉 `ipc_rpmsg_echo_main()` wrapper 중심 구조보다,
**원본 gptp_icssg main/bootstrap을 remoteproc 환경에 맞게 유지하는 형태**가 우선이다.

### 2순위: switch vs dualmac 목표 고정

현재 generated output은 switch 기준이다.

또한 사용자 목표의 D/E/F 단계는 bridge/forwarding 검증에 더 가깝다.

따라서 **현재 C5는 switch 기준으로 고정**하는 것이 맞다.

즉 지금은 dualmac 동시 추적보다:

- `gptp_icssg_switch`
- ICSSG bridge/forwarding
- gPTP bridge

를 기준으로 좁혀야 한다.

### 3순위: generated output parity 유지한 상태에서 boot 재검증

SysCfg generated output 자체는 switch donor와 꽤 가깝다.

그러므로 먼저 bootstrap parity를 복원한 뒤,
같은 generated output으로 B/C 단계 재검증을 해야 한다.

### 4순위: `.icss_mem` / `.enet_dma_mem` placement 복원

loadability는 확보했으므로,
이제 donor runtime parity를 위해 hot ICSSG/DMA memory를 donor와 비슷한 전용 영역으로 복원할 필요가 있다.

이 항목은 최소 C 단계 이전에 검토해야 한다.

### 5순위: trace 세분화는 bootstrap parity 이후

trace 세분화 자체는 필요하지만,
지금 가장 먼저 해야 할 일은 trace 포인트를 더 자르는 것이 아니라
**틀린 bootstrap 구조를 donor와 가깝게 되돌리는 것**이다.

## 8. Path B 유지 여부 판단

### 현재 판단

**지금은 Path B를 유지하는 것이 맞다.**

이유:

1. A 단계는 이미 통과했다.
2. Path A는 아직 `.resource_table` / carveout / memory model 문제를 다시 풀어야 한다.
3. 현재 blocker는 remoteproc loadability가 아니라 bootstrap/layout parity 쪽이다.

즉 현재는:

```text
Path B 방향 자체가 틀린 것은 아님
하지만 구현된 현재 Path B 구조가 donor 등가성을 충분히 보존하지 못한 것
```

으로 보는 것이 맞다.

### Path A 재검토 조건

다음 조건이면 Path A 재검토를 고려할 수 있다.

1. donor bootstrap 복원
2. switch mode 고정
3. generated output parity 확보
4. memory placement parity 일부 복원

까지 했는데도 B/C 단계에서 계속 같은 방식으로 멈출 때

그 경우에는

- donor를 remoteproc memory model로 직접 재링크하는 Path A

를 다시 평가할 가치가 생긴다.

하지만 **현재 시점에서 곧바로 Path A로 되돌아갈 필요는 낮다**.

## 9. C5 실검증 계획

실검증은 다음 순서만 유지한다.

### C5-1. bootstrap parity 수정 후 재빌드

목표:

- donor main/bootstrap 복원
- `Drivers_open()` / `Board_driversOpen()` 경로 복원
- main task priority donor 수준으로 복귀 검토

성공 조건:

- source 구조상 donor bootstrap과 등가

### C5-2. A단계 재검증: remoteproc load

확인:

- `/sys/class/remoteproc/remoteprocX/name`
- `/sys/class/remoteproc/remoteprocX/firmware`
- `/sys/class/remoteproc/remoteprocX/state`
- dmesg에서 carveout/resource_table/load error

성공 조건:

- `state=running`
- load error 없음

### C5-3. B단계 재검증: firmware boot trace

최소 trace 목표:

- `boot entry`
- `Drivers_open start/done`
- `Board_driversOpen start/done`
- `EnetApp_mainTask entry`
- `alive counter`

성공 조건:

- firmware가 `EnetApp_mainTask()` 또는 steady loop까지 진입

### C5-4. C단계: Enet/ICSSG init trace

trace 경계:

- `EnetApp_updateCfg`
- `EnetApp_driverInit`
- `EnetApp_driverOpen`
- ICSSG instance/port config
- MDIO init
- PHY detect

성공 조건:

- 실패 status 없이 ICSSG open 단계 통과

### C5-5. D단계: PHY/link 검증

확인:

- port0/port1 PHY detect
- port0/port1 link state
- 외부 endpoint `ethtool` link up

성공 조건:

- 양 포트 link up

### C5-6. E단계: L2 forwarding 검증

확인:

- endpoint A/B 수동 IP
- `arp`
- `ping`
- `tcpdump`

성공 조건:

- ARP/ICMP frame이 ICSSG bridge를 실제 통과

### C5-7. F단계: gPTP 검증

확인:

- endpoint A/B `ptp4l`
- R5F trace의 gPTP task start
- port state
- `asCapable`
- sync/pdelay event

성공 조건:

- endpoint `ptp4l` 상태 안정화
- R5F trace에서 gPTP bridge 동작 확인

## 최종 판단

현재 Path B는 **A 단계만 통과했고, B 단계에서 실패 중**이다.

실패 원인의 1차 후보는 다음이다.

1. donor bootstrap 미보존
2. `Board_driversOpen()` 생략으로 인한 board/EEPROM/MAC init 전제 붕괴
3. donor와 다른 ICSSG/DMA memory placement
4. donor와 다른 main task priority / scheduling 성질

따라서 다음 액션은

```text
trace를 더 많이 추가한다
```

가 아니라,

```text
Path B 구조를 donor bootstrap 우선으로 재정렬하고,
그 다음 A -> B -> C 순서로 다시 실검증한다
```

가 맞다.
