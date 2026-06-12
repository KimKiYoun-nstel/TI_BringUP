# SK-AM64B R5F/A53 Communication Plan

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` early-boot 후속 작업에서
`R5F firmware <-> A53 Linux app` 통신을 어떤 단계로 구현할지 정리한다.

중요:

```text
최종 목표는 RPMsg 기반 app-to-app 통신이다.
다만 첫 구현 체크포인트는 SHM으로 R5F early-boot 동작을 Linux가 확인하는 것이다.
```

이 문서는 TI baseline service인 `benchmark_server.service`, `rpmsg_json.service`를
목표 설계에 포함하지 않는다.

## 현재 해석

현재 확보한 사실:

- SBL OSPI Linux dual-boot는 이미 성공했다.
- custom early-boot R5F draft는 `0xA5800000` SHM heartbeat publish 방향이다.
- repo 안에는 working RPMsg reference로 `projects/sk-am64b-rpmsg-test/`가 있다.
- 따라서 다음 단계는 boot-chain이 아니라 firmware/app behavior 정합성이다.

현재 주의:

```text
M1 checker 구현과 build path는 확보했지만,
현재 draft의 0xA5800000 SHM base는 generated SysConfig/shared-memory model과
정합성 재확인이 필요한 상태다.
```

## 목표 구조

현재 프로젝트의 목표 구조는 다음 두 층으로 나눈다.

### 1. checkpoint path = SHM

역할:

- R5F가 Linux보다 먼저 올라와 실제로 동작했는지 확인
- Linux boot 이후에도 heartbeat가 계속 갱신되는지 확인
- A53 custom app이 SHM snapshot을 읽어 최소 ABI를 검증

의미:

```text
SHM은 최종 app protocol이 아니라 early-boot liveness proof 경로다.
```

### 2. final app transport = RPMsg

역할:

- 최종적으로 R5F app과 A53 app이 실제 command/reply 또는 payload exchange 수행
- service name / endpoint / userspace open 경로는 repo-managed RPMsg test project를 reference로 삼는다.

의미:

```text
RPMsg는 이후 M2/M3에서 붙일 real app transport다.
```

## 단계별 계획

### M1. SHM-based firmware activity confirmation

이번 구현의 1차 목표다.

구성:

- R5F firmware
  - `0xA5800000` SHM 상태 블록을 주기 갱신
  - 최소 field는 현재 `docs/heartbeat-shm-abi.md` 기준 유지
- A53 Linux app
  - `/dev/mem` read-only path로 SHM snapshot read
  - `magic/version/abi_size` 확인
  - 일정 시간 간격으로 2회 읽어 `seq/heartbeat/shm_update_count` 증가 확인

성공 기준:

```text
Linux app이 R5F heartbeat SHM을 읽고,
두 snapshot 사이에서 seq/heartbeat/shm_update_count 증가를 보고 PASS를 출력한다.
```

M1 범위에서 하지 않는 것:

- RPMsg endpoint create
- Linux-ready wait에 의존한 app protocol
- systemd auto-start
- TI baseline service 연동

현재 미해결 항목:

- `0xA5800000` ABI 기대치와 current generated SysConfig/shared-memory model 정합성
- current-source R5F appimage clean reflashing 여부

### M2. RPMsg endpoint bring-up on early-boot firmware

M1 이후 단계다.

구성:

- SHM writer는 그대로 유지
- Linux ready 이후에만 RPMsg endpoint 생성
- service announce 및 A53 custom client open 경로 추가

reference:

- `projects/sk-am64b-rpmsg-test/r5f/ipc_rpmsg_echo.c`
- `projects/sk-am64b-rpmsg-test/a53/src/main.c`

성공 기준:

- A53 custom RPMsg client가 own service/endpoint에 연결 가능
- 최소 payload 왕복 또는 command/reply 1종 성공

### M3. own app protocol 정의 및 확장

M2 이후 단계다.

후보:

- echo payload
- status request/reply
- simple command/ack

성공 기준:

- R5F/A53 양쪽이 같은 protocol contract를 사용
- message format이 project 문서에 고정됨

## 현재 구현 우선순위

현재는 다음 순서로 진행한다.

1. `docs/heartbeat-shm-abi.md` 기준 M1 reader 구현
2. local build
3. R5F multicore appimage regenerate
4. 보드에 SBL OSPI artifact set 적용 후 boot
5. Linux shell에서 custom checker app 수동 실행

중요:

```text
M1은 Linux app auto-start가 아니라 수동 실행형 checker 기준이다.
```

## 파일/컴포넌트 기준

R5F 기준 파일:

- `r5f/draft/main.c`
- `r5f/draft/ipc_rpmsg_echo.c`
- `r5f/draft/example.syscfg`
- `r5f/draft/early_heartbeat_status.h`

A53 기준 파일:

- `a53/src/main.c`
- `a53/Makefile`

문서 기준:

- `docs/plan.md`
- `docs/gates.md`
- `docs/heartbeat-shm-abi.md`
- `docs/communication-plan.md`

## 검증 방식

M1 검증은 다음 순서를 따른다.

1. R5F draft ELF build
2. R5F multicore appimage 생성
3. 기존 success-compatible SBL/U-Boot/Linux appimage와 함께 boot
4. Linux shell 확보
5. custom A53 checker app 복사 및 수동 실행
6. `STATUS: PASS` 확인

보조 확인:

- UART boot log에서 Linux login prompt 도달
- 필요 시 `devmem2` raw read와 checker 결과 교차 확인

## 현재 판단

현재 프로젝트의 가장 현실적인 표현은 다음과 같다.

```text
M1:
  SHM으로 early-boot firmware alive 확인

M2:
  RPMsg endpoint bring-up

M3:
  own app protocol 확장
```
