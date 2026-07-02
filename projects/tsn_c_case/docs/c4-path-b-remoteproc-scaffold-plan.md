# AM64x TSN C Case C4 Path B Remoteproc Scaffold Plan

## 선택한 경로

이번 C4는 `gptp_icssg_switch`를 직접 remoteproc-ready로 재링크하는 대신,

```text
Linux remoteproc-ready R5 scaffold
  +
ICSSG gPTP app logic
```

형태로 이식하는 경로를 사용한다.

## 왜 Path B를 선택하는가

현재 static 분석 결과:

- `gptp_icssg_switch.release.out`
  - `MSRAM 0x7008xxxx` 중심
  - `.resource_table` 없음
- 현재 TMDS working remoteproc firmware
  - `0xa0100000` carveout 중심
  - `.resource_table` 존재

즉 현재 `gptp_icssg_switch`를 직접 고쳐서 remoteproc 메모리 모델까지 맞추는 것보다,
이미 Linux remoteproc 구조가 성립된 scaffold 위에 `ICSSG TSN app`를 얹는 편이 리스크가 작다.

## 기준 scaffold

### remoteproc-ready 예제

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/
  examples/drivers/ipc/ipc_rpmsg_echo_linux/
```

핵심 특징:

- `ipc.enableLinuxIpc = true`
- `memory_configurator`로 `DDR_0`, `DDR_1`, `LINUX_IPC_SHM_MEM`, `RTOS_NORTOS_IPC_SHM_MEM` 정의
- `.resource_table`을 `DDR_0 @ 0xA0100000`에 배치
- program header가 Linux carveout 모델과 정합

### 이식할 app logic 기준

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/
  source/networking/enet/core/examples/tsn/
    tsnapp_icssg_main.c
    tsninit.c
    gptp_init.c
    debug_log.c
    default_flow_icssg.c
    default_flow_cfg.c
    tsnapp_icssg.h
    tsninit.h
```

## 무엇을 scaffold에서 가져와야 하나

### 반드시 유지할 것

1. `example.syscfg`의 Linux IPC / memory_configurator 구조
2. `.resource_table` 배치
3. `DDR_0 = 0xA0100000`, `DDR_1 = 0xA0101000` 계열 메모리 모델
4. Linux remoteproc가 기대하는 `firmware-name`, carveout, vring shared memory 구조와의 정합

### 초기 단계에서 재사용 가치가 큰 것

1. R5 startup / FreeRTOS main skeleton
2. `Drivers_open()` / `Board_driversOpen()` 중심 초기화 흐름
3. Linux와 통신 가능한 최소 RPMsg endpoint 하나

## 무엇을 gptp_icssg_switch에서 가져와야 하나

### 1. ICSSG app main flow

`tsnapp_icssg_main.c`

가져갈 핵심:

- `EnetApp_mainTask()`
- `EnetApp_updateCfg()`
- `EnetApp_initTsn()`
- `EnetApp_updateIcssgInitCfg()`
- `EnetApp_portLinkStatusChangeCb()`

### 2. TSN init / gPTP stack init

- `tsninit.c`
- `gptp_init.c`
- `default_flow_cfg.c`
- `default_flow_icssg.c`
- `debug_log.c`

### 3. SysCfg-generated ICSSG board config 방향

`gptp_icssg_switch`의 `example.syscfg`에서 참고할 것:

- `CONFIG_ENET_ICSS0`
- `PRU_ICSS1`
- `RGMII1`, `RGMII2`
- MDIO manual mode
- timesync enable
- ICSSG용 DMA 채널 구성

## 이식 전략

### Phase B1. remoteproc scaffold 복제

새 예제 작업 디렉터리를 별도로 만든다.

예시 개념:

```text
examples/drivers/ipc/ipc_rpmsg_echo_linux   (원본 유지)
-> examples/networking/tsn/gptp_icssg_linux_remoteproc   (새 work area)
```

실제 위치는 workspace 안에서 별도 topic branch로 정한다.

### Phase B2. memory/syscfg는 scaffold 기준 유지

초기에는 `ipc_rpmsg_echo_linux`의 memory_configurator를 그대로 유지한다.

이 단계 원칙:

- `DDR_0` / `DDR_1` / shared memory 배치는 건드리지 않는다.
- 먼저 remoteproc-friendly image를 유지한 상태에서 ICSSG app logic만 옮긴다.

### Phase B3. app main을 TSN 쪽으로 교체

`ipc_rpmsg_echo_linux`의 `main task` 대신:

- `EnetApp_mainTask()` 중심 구조로 바꾼다.

단, 초기 버전에서는 다음 중 하나를 선택한다.

1. RPMsg endpoint 유지 + TSN task 추가
2. RPMsg app logic 제거, resource_table/memory model만 유지

현재 추천은 **1번**이다.

이유:

- remoteproc readiness를 Linux에서 관찰할 endpoint가 남는다.
- firmware가 살아 있는지 사용자 공간에서 확인하기 쉽다.

### Phase B4. ICSSG SysCfg 병합

가장 어려운 지점은 여기다.

`ipc_rpmsg_echo_linux` syscfg에는 ICSSG peripheral 설정이 없고,
`gptp_icssg_switch` syscfg에는 Linux IPC memory_configurator가 없다.

따라서 최종 방향은:

- `ipc_rpmsg_echo_linux example.syscfg`
  + `gptp_icssg_switch example.syscfg`의 ICSSG peripheral section

형태의 **수동 병합**이다.

핵심 병합 대상:

- `/drivers/ipc/ipc`
- `/memory_configurator/*`
- `/networking/enet_icss/enet_icss`
- `/drivers/pruicss/pruicss`
- `/board/ethphy_cpsw_icssg/ethphy_cpsw_icssg`
- `/drivers/udma/udma`
- `debug_log`

## 가장 먼저 구현할 최소 목표

처음부터 full gPTP bridge까지 가지 않는다.

### 목표 M1

```text
remoteproc로 올라가는 R5 firmware
  +
ICSSG open/init까지 수행
  +
UART/trace로 link status 또는 init success log 확인
```

즉 첫 iteration은 `gPTP fully running`이 아니라:

- resource_table 유지
- remoteproc start 성공
- ICSSG init code 진입
- port/link 관련 로그 확보

여기까지면 충분하다.

## file-level merge plan

### scaffold 쪽에서 유지

- `example.syscfg`의 memory_configurator / ipc section
- remoteproc friendly linker output 구조
- RPMsg service endpoint 관련 최소 골격

### TSN 쪽에서 추가

- `tsnapp_icssg_main.c`
- `tsninit.c`
- `gptp_init.c`
- `default_flow_icssg.c`
- `default_flow_cfg.c`
- `debug_log.c`
- 관련 header (`tsnapp_icssg.h`, `tsninit.h`, `debug_log.h`)

### 나중에 조정 필요

- generated `ti_enet_*` files
- generated `ti_board_*`, `ti_pinmux_*`, `ti_power_clock_*`
- linker memory section names

## 현재 위험 요소

1. `ipc_rpmsg_echo_linux`의 memory_configurator와 ICSSG-generated code가 충돌할 수 있음
2. ICSSG app가 `MSRAM` 전제를 일부 암묵적으로 가질 수 있음
3. TSN stack가 Linux IPC shared memory와 캐시 정책 충돌을 낼 수 있음
4. RPMsg endpoint를 유지할지 제거할지에 따라 task model이 복잡해질 수 있음

## 다음 구현 순서

1. workspace에서 topic branch 생성
2. `ipc_rpmsg_echo_linux` 예제 구조 복제
3. `example.syscfg`에 ICSSG peripheral block 병합
4. resource_table 유지된 ELF가 다시 생성되는지 확인
5. 그 뒤 app main을 TSN init flow로 점진 교체

## 현재 판정

- Path B 선택: 완료
- file-level adaptation strategy: 정리 완료
- 실제 workspace 구현: 다음 단계
