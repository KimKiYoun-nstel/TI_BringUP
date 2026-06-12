# Early Boot Heartbeat Draft Area

이 디렉터리는 early-boot heartbeat firmware의
**초기 draft file set**을 정리하기 위한 공간이다.

중요:

- 이 디렉터리는 보드 검증 완료 source tree가 아니다.
- canonical source를 그대로 복사해 두는 공간도 아니다.
- 현재 목적은 후속 작업에서 어떤 파일 조합을 최소 baseline으로 삼을지
  repo 안에 명확히 남기고, first draft source를 시작하는 것이다.

## 현재 draft 기준

CCS projectspec 관점에서 두 canonical project는 모두 다음 3개를 입력으로 사용한다.

```text
ipc_rpmsg_echo.c
main.c
example.syscfg
```

따라서 early-boot heartbeat 최소 draft도 이 3개를 기준으로 본다.

## 현재 선택 방향

| draft 대상 | 우선 참조 | 이유 |
|---|---|---|
| `main.c` | `projects/am64x-r5f-hw-control-lab/r5f/main.c` | 두 canonical project와 구조가 사실상 동일 |
| `example.syscfg` | `projects/sk-am64b-rpmsg-test/r5f/example.syscfg` | GPIO 의존성이 없는 더 단순한 Linux IPC base |
| `ipc_rpmsg_echo.c` | `projects/am64x-r5f-hw-control-lab/r5f/ipc_rpmsg_echo.c` | heartbeat/SHM/status 개념과 가장 가까운 상위 baseline |

즉 현재 의도는 다음과 같다.

```text
entry/task shell      -> simple baseline 유지
syscfg / linker base  -> GPIO 없는 단순형 우선
runtime logic         -> hw-control-lab의 SHM/heartbeat 방향을 축소
```

## 후속 작업에서 할 일

1. `ipc_rpmsg_echo.c`에서 early-boot heartbeat에 불필요한 GPIO command path를 제외할지 결정
2. SHM publish 최소 필드 집합을 별도 문서로 확정
3. `ti-arm-clang/example.projectspec`를 새 draft source set 기준으로 만들지, canonical projectspec 중 하나를 기반으로 파생할지 결정

현재 최소 기능 설계 기준은 `../../docs/heartbeat-minimal-feature-set.md`를 따른다.
현재 SHM ABI draft 기준은 `../../docs/heartbeat-shm-abi.md`와 `early_heartbeat_status.h`를 따른다.

## 현재 단계에서 하지 않는 것

- canonical project source 복사
- 새 projectspec 작성
- board 검증 주장
- appimage 생성

## 현재 상태

- `ti-arm-clang/example.projectspec` 존재
- `tools/build/build-r5f-early-boot-app.sh r5f Release` 기준 local `.out` 생성 확인
- 즉 local buildable draft 까지는 확인되었고, 이후 단계는 image generation / board 검증이다.
