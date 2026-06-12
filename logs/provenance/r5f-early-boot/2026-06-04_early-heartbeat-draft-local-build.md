# 2026-06-04 Early Heartbeat Draft Local Build

## 목적

이 문서는 `projects/sk-am64b-r5f-early-boot/r5f/draft/` 기준
early-boot heartbeat buildable draft의 local build 실행 사실을 기록한다.

중요:

- 이 문서는 local build provenance 이다.
- 보드 반영 또는 UART boot 성공을 의미하지 않는다.

## source 기준

- Main project: `projects/sk-am64b-r5f-early-boot/`
- Draft source:
  - `projects/sk-am64b-r5f-early-boot/r5f/draft/main.c`
  - `projects/sk-am64b-r5f-early-boot/r5f/draft/ipc_rpmsg_echo.c`
  - `projects/sk-am64b-r5f-early-boot/r5f/draft/example.syscfg`
  - `projects/sk-am64b-r5f-early-boot/r5f/draft/early_heartbeat_status.h`
  - `projects/sk-am64b-r5f-early-boot/r5f/draft/ti-arm-clang/example.projectspec`

## 실행 명령

```bash
./tools/build/build-r5f-early-boot-app.sh r5f Release
```

## 결과 artifact

| 항목 | 경로 |
|---|---|
| CCS output ELF | `out/sk-am64b-r5f-early-boot/ccs_projects/sk_am64b_r5f_early_boot_heartbeat_r5fss0_0_freertos_ti_arm_clang/Release/sk_am64b_r5f_early_boot_heartbeat_r5fss0_0_freertos_ti_arm_clang.out` |
| repo alias | `out/sk-am64b-r5f-early-boot/am64-main-r5f0_0-fw` |

확인 결과:

- `.out` 생성 확인
- repo alias 생성 확인

## 해석

현재 draft는 다음 상태로 본다.

```text
buildable draft: yes
board-validated: no
appimage-generated: no
flashed: no
```

즉 task-unit-2 기준으로는
`heartbeat first draft source -> buildable draft` 단계까지는 진입한 것으로 본다.
