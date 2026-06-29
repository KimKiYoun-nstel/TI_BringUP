# 2026-06-29 Phase 5 gPTP Split State Check

## 목적

재부팅 직후 현재 runtime을 기준으로 Phase 5 blocker를 더 잘게 분리했다.

대상 direct path:

- `SK eth1 <-> TMDS eth2`

확인 순서:

1. clean direct
2. `bridge only`
3. `bridge + switch_mode`
4. `bridge + switch_mode + eth1 mqprio only`

## 재부팅 직후 baseline state

- SK:
  - `switch_mode=false`
  - `br-tsn` 잔여 존재
  - `eth0`, `eth1`는 기본 `mq + pfifo_fast`
  - `ptp4l`, `phc2sys` 자동 실행 없음
  - `eth1 -> /dev/ptp0`
- TMDS:
  - `ptp4l`, `phc2sys` 자동 실행 없음
  - `ti-tsn-dscp-pcp-tmds.service`는 active/exited
  - `eth2 -> /dev/ptp2`

## Case 0. clean direct

형상:

- `switch_mode=false`
- `br-tsn` 제거
- `eth1` direct only

관찰:

- 이번 짧은 재시험에서는 `TMDS eth2`가 `MASTER -> UNCALIBRATED`까지만 보이고 `SLAVE` grep은 남지 않았다.
- 다만 같은 부팅 세션에서 조금 앞선 Step 2 장시간 시험에서는 다음이 이미 확인되었다.
  - `TMDS eth2: UNCALIBRATED -> SLAVE`
  - `rms`, `freq`, `delay 438~440 ns`

판정:

- 이번 문서의 기준 baseline은 같은 부팅 세션의 장시간 Step 2 결과를 따른다.
- 즉 clean direct gPTP baseline은 확보된 것으로 본다.

## Case 1. bridge only

형상:

- `switch_mode=false`
- software `br-tsn` 생성
- `eth1`만 `br-tsn` slave
- `mqprio` 없음

TMDS `eth2` 관찰:

```text
LISTENING to MASTER
MASTER to UNCALIBRATED on RS_SLAVE
UNCALIBRATED to SLAVE on MASTER_CLOCK_SELECTED
rms ...
freq ...
delay 438~440 ns
```

SK `eth1` 관찰:

```text
selected /dev/ptp0 as PTP clock
LISTENING to MASTER
selected local clock 70ff76.fffe.1ff287 as best master
```

판정:

- software bridge membership alone은 direct gPTP를 깨지 않는다.

## Case 2. bridge + switch_mode

형상:

- `switch_mode=true`
- `br-tsn` 생성
- `eth1`만 `br-tsn` slave
- `mqprio` 없음

TMDS `eth2` 관찰:

```text
LISTENING to MASTER
MASTER to UNCALIBRATED on RS_SLAVE
delay timeout 반복
```

- `UNCALIBRATED -> SLAVE` 미진입
- `rms/freq` 안정화 출력 없음

SK `eth1` 관찰:

```text
LISTENING to MASTER
master sync timeout
master tx announce timeout
```

추가 counter:

```text
ale_drop: 1131
rx_port_mask_drop: 1131
```

판정:

- `switch_mode=true`가 들어가는 시점부터 gPTP stable `SLAVE`가 깨진다.
- 이번 분리 실험 기준으로 첫 failure point는 `mqprio`가 아니라 `switch_mode`다.

## Case 3. bridge + switch_mode + eth1 mqprio only

형상:

- Case 2 + `eth1` only `mqprio hw 1 mode channel`

TMDS `eth2` 관찰:

```text
LISTENING to MASTER
MASTER to UNCALIBRATED on RS_SLAVE
delay timeout 반복
```

SK `eth1` 관찰:

```text
LISTENING to MASTER
master sync timeout
master tx announce timeout
```

추가 counter:

```text
ale_drop: 1501
rx_port_mask_drop: 1501
```

판정:

- `mqprio`를 추가해도 failure signature는 이미 Case 2와 동일하다.
- 즉 이번 runtime에서는 `mqprio` 이전에 `switch_mode` 단계에서 이미 direct gPTP가 붕괴한다.

## 최종 결론

이번 재부팅 후 분리 검증 기준 결론:

1. clean direct baseline은 같은 부팅 세션에서 장시간 시험으로 확보됨
2. `bridge only`는 문제 없음
3. `bridge + switch_mode`부터 `TMDS stable SLAVE`가 깨짐
4. `mqprio`는 그 이후 동일 failure를 유지할 뿐, 최초 원인은 아님

즉 현재 Phase 5 blocker는 `taprio coexistence` 이전 단계인
`switch_mode=true 상태에서의 gPTP 유지 실패`로 더 좁혀졌다.
