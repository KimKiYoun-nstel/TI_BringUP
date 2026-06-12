# Early Boot Heartbeat Candidate Source Set

## 목적

이 문서는 early-boot heartbeat firmware를 완전히 새로 만들지 않고,
기존 repo-managed R5F project에서 어떤 source 조합을 최소 후보로 볼지 정리한다.

현재 단계는 source 복사나 build 실행이 아니라
후속 작업을 위한 후보 축소 단계이다.

## 1차 후보: `projects/am64x-r5f-hw-control-lab/r5f`

선정 이유:

- 기존 Phase 1 실보드 검증에서 RPMsg + trace + 상태 응답이 확인되었다.
- 관련 문서에서 SHM/heartbeat 관찰 방향이 이미 정리되어 있다.
- early-boot heartbeat에서 우선 보고 싶은 `seq`, `heartbeat`, `shm_update_count` 계열 개념과 가장 가깝다.

최소 source 후보:

| 파일 | 용도 | early-boot 후보 판단 |
|---|---|---|
| `main.c` | FreeRTOS main task entry | 재사용 적합 |
| `example.syscfg` | Linux IPC + memory/linker/pinmux 기반 | GPIO 항목 축소 검토 필요 |
| `ipc_rpmsg_echo.c` | 현재는 RPMsg command + GPIO hook 중심 | SHM/heartbeat 최소화 관점에서는 축소 필요 |

주의:

- 현재 `example.syscfg`에는 `GPIO_LAB_OUT` 관련 설정이 포함되어 있다.
- early-boot heartbeat 최소 후보로 줄일 때는 GPIO 의존성을 제거하거나 보류하는 편이 안전하다.

## 2차 후보: `projects/sk-am64b-rpmsg-test/r5f`

선정 이유:

- Linux IPC echo baseline으로 더 단순하다.
- `example.syscfg`가 GPIO 없이 `ipc.enableLinuxIpc = true` 중심이라 구조가 가볍다.

최소 source 후보:

| 파일 | 용도 | early-boot 후보 판단 |
|---|---|---|
| `main.c` | FreeRTOS main task entry | 재사용 적합 |
| `example.syscfg` | Linux IPC 활성 기본형 | 재사용 적합 |
| `ipc_rpmsg_echo.c` | echo + announce baseline | heartbeat-only 관점에서는 여전히 축소 가능 |

## 현재 판단

### heartbeat / SHM 우선 경로

다음 조합을 1차 후보로 본다.

```text
base entry: projects/am64x-r5f-hw-control-lab/r5f/main.c
syscfg base: projects/sk-am64b-rpmsg-test/r5f/example.syscfg 또는 hw-control-lab syscfg 축소본
logic base: hw-control-lab의 SHM/heartbeat 개념을 반영한 최소 firmware
```

해석:

- `main.c`는 두 프로젝트 모두 거의 동일하므로 진입점 차이는 크지 않다.
- `syscfg`는 GPIO 없는 단순형인 `sk-am64b-rpmsg-test` 쪽이 초기 early-boot 최소화에 더 유리할 수 있다.
- heartbeat/SHM 관찰 개념은 `hw-control-lab` 문서와 실보드 검증 결과를 우선 참고한다.

### RPMsg attach 확장 경로

RPMsg attach 검증으로 확장할 때는 다음 순서를 권장한다.

1. `projects/sk-am64b-rpmsg-test/r5f` echo baseline
2. `projects/am64x-r5f-hw-control-lab/r5f` 기능 확장형

## 관련 문서

- `projects/am64x-r5f-hw-control-lab/docs/completion.md`
- `projects/am64x-r5f-hw-control-lab/docs/shm-status-field-reference.md`
- `projects/sk-am64b-rpmsg-test/docs/plan.md`

## 현재 단계에서 하지 않는 것

- source copy-in
- build 실행
- multicore appimage 생성
- 보드 반영
