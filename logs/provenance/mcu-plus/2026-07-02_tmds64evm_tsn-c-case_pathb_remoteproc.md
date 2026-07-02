# 2026-07-02 TMDS64EVM TSN C Case MCU+ Path B remoteproc integration

## 대상 자산

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
```

## export 상태

```text
main repo patch : bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch
series entry    : not added
```

## 성격

이 자산은 현재 clean mailbox patch가 아니라,

- `ipc_rpmsg_echo_linux` scaffold
- `gptp_icssg_switch` donor
- Path B remoteproc-hosted ownership 조정

을 합친 실제 통합 diff reference다.

즉 현재 용도는 다음과 같다.

1. workspace 변경 보존
2. trace/clock skip/boot wrapper 통합 내용을 repo에 고정
3. 이후 clean replay patch 세트로 정리할 때 기준선 제공

## 핵심 포함 내용

- `main.c`, `ipc_rpmsg_echo.c`의 remoteproc bootstrap wrapper
- `rproc_trace_status.h` 기반 trace 삽입
- `example.syscfg`와 generated make/syscfg 산출물 정합
- `ti_power_clock_config.remoteproc.c`와 `subdir_rules.mk` 기반 remoteproc-hosted clock skip 유지
- `tsnapp_icssg_main.c`, `tsninit.c`, `gptp_init.c`, `default_flow_icssg.c`의 Path B trace 보강

## 현재 판단

이 integration reference는 bring-up 성공 상태를 보존하는 데는 충분하다.

다만 다음 단계에서 별도 정리가 필요하다.

1. generated output 의존을 줄인 clean replay patch 재구성
2. debug trace 중 장기 유지할 것과 제거할 것 분리
3. `.icss_mem` / `.enet_dma_mem` parity 검토 후 patch 재정리
