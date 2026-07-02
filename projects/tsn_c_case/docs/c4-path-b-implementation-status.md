# AM64x TSN C Case C4 Path B Implementation Status

## 목적

`ipc_rpmsg_echo_linux` 기반 remoteproc-ready scaffold 위에 `ICSSG gPTP` app skeleton을 얹는 Path B 구현 진행 상태를 기록한다.

## 현재 작업 위치

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
```

이 디렉터리는 `ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang`를 복제한 integration work area다.

## 현재 반영한 것

### 1. remoteproc-ready scaffold 유지

- `example.syscfg`의 Linux IPC / memory_configurator 구조를 유지했다.
- `.resource_table`과 DDR carveout 모델은 scaffold 쪽을 따른다.

### 2. ICSSG/TSN source 골격 추가

project root에 다음 source를 가져왔다.

- `tsnapp_icssg_main.c`
- `tsninit.c`
- `gptp_init.c`
- `debug_log.c`
- `default_flow_cfg.c`
- `default_flow_icssg.c`
- `nrt_flow/dataflow.h`
- 관련 header copy (`enetapp_icssg.h`, `tsninit.h`, `debug_log.h`, `common.h`, `tsnapp_porting.h`)

### 3. wrapper 진입점 구성

- copied scaffold의 `ipc_rpmsg_echo.c`는 integration wrapper로 교체했다.
- 기존 함수명 `ipc_rpmsg_echo_main()`은 유지하고, 내부에서 `EnetApp_mainTask()`를 호출하도록 바꿨다.

### 4. trace logging 추가

`rproc_trace_status.h`를 추가하고 다음 포인트에 trace를 심었다.

- `boot`
- `enet_init`
- `icssg_init`
- `phy_link`
- `gptp_state`
- `error code`

현재 binary `strings`에서 `[RPROC_TRACE]` 포맷 문자열이 실제로 확인된다.

## build 상태

### 결과

- `Release/ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang.out`
  - **link 성공**

### log

- build log:
  - `projects/tsn_c_case/logs/2026-06-30_pathb_scaffold_build.log`

### post-build 상태

- `makefile_ccs_bootimage_gen`의 post-build `mcelf` 생성은 실패했다.
- 실패 원인:

```text
TypeError: ELFFile.iter_segments() got an unexpected keyword argument 'type'
```

이것은 current host-side Python tool 문제로 보이며, **remoteproc에 필요한 raw ELF `.out` 자체가 링크된 사실과는 별개**다.

## remoteproc 적합성 결과

새 scaffold output의 `readelf` 결과는 다음 특징을 가진다.

- `.resource_table` 존재
- `.resource_table @ 0xA0100000`
- `.bss @ 0xA0101000`
- `.text @ 0xA0199300`
- `.data @ 0xA01FDA40`

즉 기존 `gptp_icssg_switch.release.out`의 `MSRAM 0x7008xxxx` 모델에서 벗어나,
Linux remoteproc carveout 계열인 `0xA0100000` 기반 모델로 들어왔다.

## trace coverage 상태

현재 source 기준으로 다음 상태 로그 문자열이 binary 안에 존재한다.

- `main start`
- `system and board init complete`
- `main task created`
- `remoteproc scaffold entry`
- `dispatching into EnetApp_mainTask`
- `gptp icssg main task start`
- `driver init start`
- `peripherals=%u`
- `per_idx=%u inst=%u mac_ports=%u`
- `driver open failed ...`
- `starting TSN modules`
- `all TSN modules started`
- `TSN and gPTP tasks started`
- `netdev_count=%d`
- `gptpman_run failed`
- `gptpman_run exited cleanly`
- `mac_port=%u`

### 현재 판단

- boot / enet init / icssg init / phy link / gptp state / error code 관측용 최소 trace 포인트는 source에 반영됨

## 현재 남은 문제

1. output 파일명과 project naming이 아직 scaffold 이름을 그대로 사용함
2. post-build `mcelf` 생성 Python tool이 깨짐
3. live board에 올려 `remoteproc start`를 아직 안 해봄
4. 실제 runtime에서 trace가 `/sys/kernel/debug/remoteproc/...` 또는 다른 경로로 어떻게 보이는지 미확인

## 다음 단계

1. raw ELF `.out`를 target firmware candidate로 사용
2. live board에 임시 배치 후 `remoteprocX/firmware` 교체 시도
3. `state=start`, `dmesg`, remoteproc trace, link log를 함께 관찰

## 현재 판정

- Path B skeleton source integration: 완료
- Path B remoteproc-friendly ELF link: 완료
- Path B runtime load test: 다음 단계
