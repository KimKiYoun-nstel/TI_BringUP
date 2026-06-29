# Phase 5 gPTP Integrated Qbv

## 목적

Qbv를 PHC / gPTP 시간 기준과 연결해 재현 가능한 schedule 동작을 확인한다.

## 준비 자산

- Phase 4 결과
- gPTP 상태 확인 절차

## 1차 pass 기준

- gPTP 동기화 상태에서 taprio/Qbv schedule이 안정적으로 적용됨
- receiver traffic pattern이 schedule에 맞게 재현됨

## 현재 상태

- 진행 중

## 이번 확인 상태

- `Phase 4 selective schedule` 상태에서 `SK eth0 <-> TMDS ep1/eth1` 경로로 직접 gPTP를 먼저 시도했다.
- 이 경로에서는 SK `ptp4l`이 다음 증상으로 바로 불안정해졌다.

```text
timed out while polling for tx timestamp
send peer delay request failed
LISTENING to FAULTY
```

- 즉 현재 selective schedule과 같은 port에서 gPTP를 직접 돌리는 경로는 Phase 5 시작점으로 부적합했다.

## 공통 PHC 경로로 재구성

실무적으로 더 의미 있는 경로는
`SK eth1 <-> TMDS eth2` direct gPTP를 이용해 **SK의 공통 PHC `/dev/ptp0`**를 동기화하는 것이다.

이유:

- SK `eth0`, `eth1`는 같은 PHC `/dev/ptp0`를 공유한다.
- 따라서 `eth1`에서 gPTP가 잡히면 `eth0 taprio`도 같은 시간 기준을 쓸 수 있다.

이번에 확인한 장치 매핑:

- SK `eth1` -> `/dev/ptp0`
- TMDS `eth2` -> `/dev/ptp2`

## gPTP 상태 확인 결과

### direct path role formation

SK `eth1`:

```text
LISTENING -> MASTER
selected local clock 70ff76.fffe.1ff287 as best master
```

TMDS `eth2`:

```text
new foreign master 70ff76.fffe.1ff287-1
selected best master clock 70ff76.fffe.1ff287
... -> UNCALIBRATED on RS_SLAVE
```

즉 현재 live Phase 5 상태에서 다음은 확인되었다.

1. direct path BMCA / best master selection은 된다.
2. slave path 진입 직전인 `UNCALIBRATED`까지는 내려간다.
3. 그러나 아직 stable `SLAVE`와 `rms/delay/freq` 안정화는 재현하지 못했다.

`priority1` 차이와 `transportSpecific 1` 설정을 추가해도 결과는 같았다.

추가로 다음 분리 실험도 수행했다.

1. `eth0` selective `taprio`를 완전히 제거한 상태
2. `switch_mode=false` + `br-tsn` 제거 상태
3. `phc_ctl /dev/ptp0 set`, `phc_ctl /dev/ptp2 set`로 PHC epoch를 wall clock에 정렬한 상태
4. `tx_timestamp_timeout 1000`을 넣은 `ptp4l` 설정

결과:

- direct path `SK eth1 <-> TMDS eth2`는 여전히 stable `SLAVE`로 내려가지 않았다.
- 특히 `switch_mode=false` direct 형상에서는 SK `eth1`에서 다음이 반복 재현되었다.

```text
timed out while polling for tx timestamp
send peer delay request failed
LISTENING to FAULTY
```

즉 현재까지는 `taprio` 공존 여부보다 **SK eth1 direct gPTP runtime 자체의 불안정성**이 더 직접적인 blocker로 보인다.

## PTP frame 교환 관찰

`tcpdump ether proto 0x88f7`로 direct path raw frame을 확인했다.

확인된 것:

- `Sync`
- `Follow_Up`
- `Announce`
- `Pdelay_Req`
- `Pdelay_Resp`
- `Pdelay_Resp_Follow_Up`

예:

```text
SK -> 01:80:c2:00:00:0e  Pdelay_Req
TMDS -> 01:80:c2:00:00:0e  Pdelay_Resp
TMDS -> 01:80:c2:00:00:0e  Pdelay_Resp_Follow_Up
```

즉 BMCA와 peer delay 교환 자체는 direct path에서 실제로 왕복하고 있다.

## PHC 기준 taprio base-time 적용

gPTP stable `SLAVE`는 아직 아니지만,
PHC 기준 미래 시각을 읽어 `taprio base-time`에 넣는 경로 자체는 확인했다.

SK에서:

```text
phc_ctl /dev/ptp0 get -> current PHC time
BASE_TIME = current PHC + 2s
```

적용 결과:

```text
qdisc taprio 8008: root ...
base-time 32276502750402
index 0 cmd S gatemask 0x1 interval 50000000
index 1 cmd S gatemask 0x4 interval 50000000
```

즉 **PHC 기준 미래 base-time으로 selective schedule을 다시 생성하는 경로**는 확보되었다.

## 현재 판정

Phase 5는 아직 완료가 아니다.

재부팅 후 2026-06-29 분리 검증으로 다음이 추가 확인되었다.

1. 같은 부팅 세션에서 clean direct `SK eth1 <-> TMDS eth2` baseline은 장시간 시험으로 다시 확보했다.
2. software `bridge only` (`switch_mode=false`, `eth1`만 `br-tsn` slave) 상태에서는 `TMDS eth2`가 stable `SLAVE`로 내려간다.
3. 그러나 `switch_mode=true`를 켜는 순간 `mqprio` 없이도 `TMDS eth2`는 `UNCALIBRATED`에서 멈춘다.
4. 이때 SK `eth1`에서는 `master sync timeout`, `master tx announce timeout`가 반복된다.
5. `eth1 mqprio`를 추가해도 failure signature는 같아서, 이번 runtime에서 최초 failure point는 `mqprio`가 아니라 `switch_mode`다.

현재까지 확인된 것:

1. gPTP direct path에서 BMCA / master selection 가능
2. selective schedule과 같은 port에서는 gPTP가 `tx timestamp timeout`으로 깨질 수 있음
3. 별도 direct path를 사용하면 `UNCALIBRATED`까지는 내려감
4. PHC 기준 future `base-time`으로 taprio schedule 재생성 가능
5. `taprio` 제거, `switch_mode=false`, PHC epoch 정렬, `tx_timestamp_timeout` 증가 후에도 stable `SLAVE`는 아직 재현되지 않음
6. direct path에서 `Sync/Announce/Pdelay_Req/Resp/Resp_Fup` frame 교환은 실제로 왕복함
7. 재부팅 후 분리 실험 기준으로 `bridge only`는 통과하지만 `bridge + switch_mode`부터 stable `SLAVE`가 깨짐

아직 미확인:

1. `switch_mode=true` 상태에서 stable `SLAVE`
2. `switch_mode=true` 상태에서 `rms/delay/freq` 안정화 로그
3. stable gPTP 상태에서 selective Qbv schedule 재현

## 현재 live 유지 상태

Phase 5 조사 상태를 그대로 유지한다.

- `eth0`: PHC-based selective `taprio` schedule 유지
- SK `eth1`: gPTP master 시도 상태
- TMDS `eth2` (root namespace): gPTP slave 시도 상태
- TMDS `ep1/eth1`: receiver path 유지

현재 복구된 live 기준:

- SK `switch_mode=true`
- SK `br-tsn=10.50.0.2/24`
- SK `br-tsn.301=10.31.0.3/24`
- SK `eth0`: selective `taprio` schedule 유지
