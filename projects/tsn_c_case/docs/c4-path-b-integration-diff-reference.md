# AM64x TSN C Case C4 Path B Integration Diff Reference

## 목적

이 문서는 `remoteproc-friendly scaffold + gptp_icssg app logic` 방식으로 진행한 Path B 이식 작업을 외부 검토하기 쉽게 정리한 참조 문서다.

핵심 목표는 다음 두 가지다.

1. 현재 workspace에서 일반 `git diff`가 왜 바로 유효하지 않은지 설명
2. 실제로 어떤 예제를 기준으로 어떤 대상에게 어떻게 이식했는지, 그리고 그 변경점이 어떤 diff artifact에 담겼는지 설명

## diff artifact 위치

검토용 diff 파일은 다음 경로에 저장했다.

```text
projects/tsn_c_case/logs/2026-07-01_pathb_integration_reference.diff
```

## 왜 일반 git diff가 바로 안 되나

현재 `workspace/mcu_plus_sdk_am64x_12_00_00_27`는 독립 Git repo가 아니다.

- 실제 Git top-level은 `TI_Bringup` 상위 repo다.
- `workspace/`는 상위 repo에서 ignore 대상이다.

따라서 다음 형태의 일반 `git diff`는 이번 이식 작업만 정확히 보여주지 못한다.

```text
git diff
```

그래서 이번 검토용 artifact는 다음 방식으로 만들었다.

```text
git diff --no-index
```

즉 Git tracked change가 아니라,

- scaffold 원본과 integration 결과를 비교한 diff
- donor 원본과 integration 결과를 비교한 diff

를 합쳐 만든 참조용 diff다.

## 이식 대상 work area

실제 작업 디렉터리:

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
```

이 디렉터리는 새로 만든 integration work area이며, 출발점은 `ipc_rpmsg_echo_linux` CCS project 복제본이다.

## 기준 예제와 donor

### 1. remoteproc scaffold 기준

다음 Linux remoteproc-ready 예제를 scaffold 기준으로 사용했다.

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/ipc/
  ipc_rpmsg_echo_linux/am64x-evm/r5fss0-0_freertos/example.syscfg

workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
```

이 scaffold에서 유지하려 한 핵심은 다음이다.

- `ipc.enableLinuxIpc = true`
- `DDR_0 = 0xA0100000`
- `DDR_1 = 0xA0101000`
- `.resource_table` 배치
- Linux remoteproc carveout과 맞는 memory model

### 2. gPTP/ICSSG donor 기준

주 donor는 다음 경로다.

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/
  gptp_icssg_app/gptp_icssg_switch/am64x-evm/r5fss0-0_freertos/
```

실제 source donor는 다음 공통 TSN source도 함께 포함한다.

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/
workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/nrt_flow/
```

## 이번 이식의 성격

이번 작업은 `gptp_icssg_switch` 예제를 통째로 remoteproc-ready로 재구성한 것이 아니다.

정확히는 다음에 가깝다.

```text
ipc_rpmsg_echo_linux scaffold
  +
TSN/ICSSG app source graft
```

즉 성격상:

- full example port
- 보다는
- remoteproc scaffold 위에 gPTP ICSSG app body를 얹은 integration

이다.

## diff artifact 구성

diff 파일은 두 부류로 나뉜다.

### 1. scaffold -> integration

다음 항목은 `ipc_rpmsg_echo_linux` 기반에서 어떻게 바뀌었는지 보여준다.

- `main.c`
- `ipc_rpmsg_echo.c`
- `example.syscfg`
- `Release/subdir_vars.mk`
- `Release/subdir_rules.mk`
- `Release/makefile`

### 2. donor -> integration

다음 항목은 TSN donor source를 가져온 뒤 얼마나 수정했는지 보여준다.

- `tsnapp_icssg_main.c`
- `tsninit.c`
- `gptp_init.c`
- `debug_log.c`
- `default_flow_cfg.c`
- `default_flow_icssg.c`

여기서 `debug_log.c`, `default_flow_cfg.c`는 diff가 비어 있으므로 사실상 원본 그대로 복사한 파일이다.

## 실제로 무엇을 옮겼나

integration project에는 다음 TSN/ICSSG source를 추가했다.

- `tsnapp_icssg_main.c`
- `tsninit.c`
- `gptp_init.c`
- `debug_log.c`
- `default_flow_cfg.c`
- `default_flow_icssg.c`
- `common.h`
- `debug_log.h`
- `tsninit.h`
- `enetapp_icssg.h`
- `nrt_flow/dataflow.h`

추가된 source 등록은 diff 파일의 다음 구간에서 확인할 수 있다.

```text
=== scaffold -> integration: Release/subdir_vars.mk ===
```

## 실제 구조 변경의 핵심

### 1. `ipc_rpmsg_echo.c`는 사실상 완전 교체했다

원래 scaffold의 RPMsg echo app 본체를 제거하고, entry point 이름만 유지한 wrapper로 바꿨다.

즉 현재 구조는:

```text
ipc_rpmsg_echo_main()
  -> EnetApp_mainTask()
```

이다.

이 변화는 diff 파일의 다음 구간에서 가장 크게 보인다.

```text
=== scaffold -> integration: ipc_rpmsg_echo.c ===
```

### 2. `main.c`는 scaffold `main.c`를 유지했다

현재 integration `main.c`는 기본적으로 scaffold의 `main.c`를 유지하고 trace만 추가한 형태다.

즉 다음 흐름이다.

```text
System_init()
Board_init()
task create
  -> ipc_rpmsg_echo_main()
     -> EnetApp_mainTask()
```

### 3. 원본 `gptp_icssg_switch`의 bootstrap은 그대로 옮기지 않았다

원본 `gptp_icssg_switch`의 `main.c`는 task 안에서 다음을 수행한다.

```text
Drivers_open()
Board_driversOpen()
EnetApp_mainTask()
Board_driversClose()
Drivers_close()
```

반면 현재 integration에서는 이 경로를 직접 사용하지 않았다.

이 점은 외부 검토에서 가장 먼저 봐야 할 구조 차이다.

## SysCfg 병합 방식

`example.syscfg`는 scaffold 것을 기반으로 유지하면서, 아래 peripheral block을 수동 추가했다.

- `eeprom`
- `gpio`
- `i2c`
- `pruicss`
- `enet_icss`
- `ethphy_cpsw_icssg`
- `udma`

즉 memory/resource_table 쪽은 scaffold 기준,
ICSSG peripheral 쪽은 TSN donor 기준으로 합친 구조다.

해당 구간은 diff 파일의 다음 section에서 확인 가능하다.

```text
=== scaffold -> integration: example.syscfg ===
```

## build system 변경

### 추가 source 등록

`Release/subdir_vars.mk`에 TSN source를 추가했다.

### SysCfg regenerate workaround

`Release/subdir_rules.mk`에 다음 workaround를 넣었다.

```text
sed -i 's/gIpcSharedMem\[\]/gIpcSharedMem[0]/g' syscfg/ti_drivers_config.c
```

이유는 merged SysCfg 결과물에서 `gIpcSharedMem[]` 선언 사용 때문에 build 문제가 있었기 때문이다.

### link library 확장

`Release/makefile`에 다음 계열 library path/link flag를 추가했다.

- ENET library
- TSN library
- TSN stack license library
- gPTP 관련 compile define

이 변경은 다음 section에서 확인 가능하다.

```text
=== scaffold -> integration: Release/makefile ===
```

## donor source에 가한 수정 수준

TSN donor source 자체는 대규모 재작성하지 않았다.

실질적으로는 다음 성격의 변경이 대부분이다.

- `rproc_trace_status.h` include 추가
- boot/enet/icssg/phy/gptp 상태 trace 추가
- include path 1건 수정

즉 donor source 변경은 주로 instrumentation 수준이다.

대략적인 diff 규모는 다음과 같다.

- `tsnapp_icssg_main.c`: trace 추가 중심
- `tsninit.c`: trace 추가 중심
- `gptp_init.c`: trace 추가 중심
- `default_flow_icssg.c`: include path 수정 1건
- `debug_log.c`: 변경 없음
- `default_flow_cfg.c`: 변경 없음

## 현재 결과를 해석할 때 중요한 점

현재 실보드 결과는 다음만 확정한다.

1. remoteproc-friendly ELF 형태는 만들어졌다.
2. Linux remoteproc가 이 ELF를 실제로 load했다.
3. 그러나 이것이 `gptp_icssg` 예제를 정상 이식했다는 뜻은 아니다.

그 이유는 현재 integration의 가장 큰 구조 차이가 다음에 있기 때문이다.

- 원본 TSN example bootstrap 미반영
- scaffold entry 유지
- RPMsg 본체 제거 후 wrapper화
- SysCfg 수동 병합

즉 현재 검토 포인트는 단순히 trace 유무가 아니라,

```text
이식 구조 자체가 원본 example의 runtime 전제를 깨뜨렸는가?
```

이다.

## 외부 검토 시 우선 포인트

1. `main.c` bootstrap 차이
2. `Drivers_open()` / `Board_driversOpen()` 생략 영향
3. `ipc_rpmsg_echo.c`를 wrapper로 축소한 접근이 타당한지
4. `example.syscfg`의 memory/resource_table 유지 + ICSSG peripheral 수동 병합이 적절한지
5. single-EMAC / dual-mac / switch 기대 구성과 현재 SysCfg가 일치하는지
6. TSN donor source는 거의 그대로지만, scaffold runtime model 위에서 동작할 전제가 맞는지

## 한 줄 요약

이번 Path B는

```text
gptp_icssg example full port
```

가 아니라,

```text
Linux remoteproc scaffold 위에 gptp_icssg app source를 graft한 integration 실험
```

이다.

검토는 반드시 아래 두 파일을 함께 봐야 한다.

```text
projects/tsn_c_case/logs/2026-07-01_pathb_integration_reference.diff
projects/tsn_c_case/docs/c4-path-b-integration-diff-reference.md
```
