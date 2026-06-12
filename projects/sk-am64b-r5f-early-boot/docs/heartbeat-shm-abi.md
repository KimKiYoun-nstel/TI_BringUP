# Early Boot Heartbeat SHM ABI Draft

## 목적

이 문서는 `early-boot-heartbeat` first draft가 사용하는
최소 SHM ABI를 별도 구조체 관점에서 정리한다.

현재 단계의 목표는 다음 두 가지다.

- R5F writer 쪽 field 집합을 고정한다
- 이후 A53 reader 쪽이 같은 field 집합을 기준으로 붙을 수 있게 한다

이 문서는 draft ABI 문서이며,
실보드 검증 완료 ABI 선언이 아니다.

## 관련 파일

- `draft/early_heartbeat_status.h`
- `draft/ipc_rpmsg_echo.c`
- `heartbeat-minimal-feature-set.md`

## SHM 위치

현재 draft 기준 값:

```text
base = 0xA5800000
size = 0x1000
```

의미:

- early-boot heartbeat writer는 이 주소를 기준으로 상태를 publish 한다.
- 이후 A53 reader는 같은 physical address를 기준으로 snapshot을 읽어야 한다.

## ABI 상수

현재 draft header는 다음 상수를 둔다.

| 항목 | 값 | 의미 |
|---|---|---|
| `EARLY_HEARTBEAT_SHM_BASE_ADDR` | `0xA5800000` | SHM base |
| `EARLY_HEARTBEAT_SHM_SIZE_BYTES` | `0x1000` | carveout size |
| `EARLY_HEARTBEAT_SHM_MAGIC` | `0x52354653` | ASCII `R5FS` |
| `EARLY_HEARTBEAT_SHM_VERSION` | `0x00010000` | ABI version |
| `EARLY_HEARTBEAT_CORE_ID_MAIN0_0` | `0x78000000` | draft target core id |
| `EARLY_HEARTBEAT_PERIOD_USEC` | `100000` | 100 ms publish target |

## 최소 구조체

현재 draft 구조체는 다음 필드만 포함한다.

| 필드 | 의미 |
|---|---|
| `magic` | 구조체 식별값 |
| `version` | ABI 버전 |
| `abi_size` | writer가 쓰는 구조체 크기 |
| `seq` | publish sequence |
| `uptime_ms` | R5F uptime |
| `heartbeat` | health counter |
| `shm_update_count` | SHM write 누적 횟수 |
| `shm_update_period_ms` | 목표 publish 주기 |
| `core` | writer core id |

## 필드 선택 이유

현재 draft는 다음 질문에 답하는 데 필요한 필드만 남긴다.

```text
R5F가 Linux 이전부터 살아 있었는가?
지금도 계속 SHM을 갱신 중인가?
A53가 기대하는 ABI와 같은 구조체를 보고 있는가?
```

이 질문에 최소로 필요한 것은:

- 식별: `magic`, `version`, `abi_size`
- 생존성: `seq`, `heartbeat`, `shm_update_count`
- 시간성: `uptime_ms`, `shm_update_period_ms`
- writer 구분: `core`

## 현재 ABI에서 의도적으로 제외한 것

다음 field는 현재 draft ABI에 넣지 않는다.

- `rpmsg_endpoint`
- `rpmsg_rx_count`, `rpmsg_tx_count`, `rpmsg_error_count`
- `last_command_id`, `last_error`
- GPIO 상태 관련 field
- event telemetry 관련 field
- VTM temperature 관련 field

이유:

- 초기 early-boot heartbeat 검증에는 과하다.
- ABI를 작게 유지해야 writer/reader 동시 변경 부담이 줄어든다.

## writer 동작 기대치

현재 draft writer는 주기적으로 다음을 갱신한다.

```text
magic
version
abi_size
seq
uptime_ms
heartbeat
shm_update_count
shm_update_period_ms
core
```

운영 중 기대되는 관찰은 다음과 같다.

- `magic == 0x52354653`
- `version == 0x00010000`
- `abi_size == sizeof(EarlyHeartbeatStatus)`
- `seq`, `heartbeat`, `shm_update_count`가 계속 증가
- `shm_update_period_ms == 100`

## 다음 단계

이 ABI draft 이후의 자연스러운 후속 작업은 다음이다.

1. A53 reader 쪽 기대 field 목록 정리
2. draft source가 이 header만 참조하도록 유지
3. build 가능한 source tree로 승격할 때 packing/alignment 필요성 재검토
