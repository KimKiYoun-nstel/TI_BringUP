# Phase 4 정리 - SHM Status Block + Internal Temperature Telemetry

## 목적

이 문서는 `am64x-r5f-button-event-lab` 기준으로 진행한
Phase 4 작업 전체를 한 번에 정리하는 summary 문서다.

Phase 4의 핵심은 다음 두 가지였다.

1. **R5F -> A53 단방향 SHM status block**
2. **R5F internal temperature telemetry + A53 Linux 기준값 비교**

---

## 최종 구조

```text
R5F firmware
  -> runtime/RPMsg/GPIO/event 상태 수집
  -> VTM sensor0/sensor1 raw code read
  -> raw -> milli-Celsius 변환
  -> reserved-memory SHM에 주기적 write

A53 Linux r5ctl shm-status
  -> /dev/mem mmap으로 SHM snapshot read
  -> magic/version/size/seq 일관성 확인
  -> SHM telemetry 출력
  -> Linux hwmon(main0_thermal/main1_thermal) read
  -> delta 출력
```

---

## 구현 범위

### 1. SHM carveout

SK-AM64B DTS에 다음 reserved-memory를 추가했다.

```text
node : r5f-status-shm@a5800000
base : 0xa5800000
size : 0x1000
type : shared-dma-pool
attr : no-map
```

주의:

```text
이 carveout이 booted DTB에 먼저 반영되지 않으면
R5F가 Linux 일반 RAM을 덮어쓸 수 있다.
따라서 DTB 선반영은 필수 전제다.
```

### 2. SHM ABI

공유 구조체는 다음 헤더에 둔다.

```text
projects/am64x-r5f-button-event-lab/include/r5f_status_shm.h
```

포함 필드 범주:

1. SHM header / ABI 식별
2. runtime counters
3. RPMsg telemetry
4. GPIO / event telemetry
5. temperature telemetry

### 3. R5F writer

R5F는 100 ms 주기로 SHM status block을 갱신한다.

현재 기록하는 값:

```text
- uptime_ms
- heartbeat
- shm_update_count
- main_loop_count
- rpmsg_rx_count / tx_count / error_count
- last_command_id / last_error
- output_state / input_state
- event_count / last_event_type / timestamp
- soc_temp0/1 raw / milli_celsius / status
```

일관성은 `seq_begin -> field write -> seq_end` 순서로 보장한다.

### 4. VTM temperature telemetry

R5F는 `main_vtm0` sensor index `0/1`을 읽는다.

구현 방식:

```text
1. VTM status register 3회 read
2. 3개 샘플 중 가장 가까운 두 값 평균 선택
3. low 10-bit raw code 추출
4. Linux k3_j72xx_bandgap driver와 같은 golden polynomial 기반 lookup으로 milli-Celsius 변환
```

### 5. A53 reader

`r5ctl shm-status`는 RPMsg command가 아니라 A53 userspace reader다.

동작:

```text
1. /dev/mem open
2. SHM physical address mmap
3. snapshot copy + seq retry
4. SHM telemetry 출력
5. Linux hwmon main0_thermal/main1_thermal read
6. R5F SHM 값과 Linux 값 delta 출력
```

---

## 실보드 검증 결과

상세 원본 기록:

```text
docs/bringup-logs/2026-05-22_SK-AM64B_phase4_shm_vtm_live_validation.md
```

최종 확인된 사실:

1. running DT에 `r5f-status-shm@a5800000` 존재
2. `/proc/iomem`에 `9e800000-a5800fff : reserved` 반영
3. `r5ctl shm-status`에서 `magic/version/abi_size/seq` 정상
4. `seq`, `heartbeat`, `shm_update_count` 지속 증가
5. RPMsg command 후 `rpmsg_*` counter와 `last_command_id` 반영
6. GPIO set 후 `output_state`가 SHM에 반영
7. R5F temperature raw와 A53 `devmem2` raw 후보가 대응
8. R5F milli-Celsius와 Linux hwmon 값이 수백 mC 수준 차이로 수렴

예시:

```text
soc_temp0_raw=344
soc_temp0_millicelsius=44981
main0_thermal=44981
soc_temp0_delta_millicelsius=0

soc_temp1_raw=343
soc_temp1_millicelsius=44753
main1_thermal=44981
soc_temp1_delta_millicelsius=-228
```

---

## 문서 위치

Phase 4 관련 참고 문서:

```text
README.md
docs/board-apply.md
docs/protocol.md
docs/resource-ownership.md
docs/test-procedure.md
docs/completion.md
docs/phase4-shm-vtm-summary.md
```

필드별 설명이 필요하면 다음 문서를 본다.

```text
projects/am64x-r5f-hw-control-lab/docs/shm-status-field-reference.md
```

---

## 현재 판단

```text
Phase 4 1차 slice:
  SHM status block 구현/검증 완료

Phase 4 2차 slice:
  VTM raw + milli-Celsius telemetry 구현/검증 완료
```

즉 현재 baseline은 단순 RPMsg Phase 3 수준을 넘어,
**SHM status + internal temperature telemetry까지 포함한 Phase 4 baseline**으로 볼 수 있다.
