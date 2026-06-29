# 2026-06-26 Phase 5 gPTP Qbv Integration Progress

## 목적

Phase 5 목표는 gPTP로 동기화된 PHC 기준 위에서 Qbv schedule을 재현하는 것이다.

이번 세션에서는 먼저 다음 두 가지를 분리해서 확인했다.

1. 현재 live topology에서 gPTP lock이 가능한가?
2. PHC 기준 미래 `base-time`으로 selective schedule을 다시 생성할 수 있는가?

## 1. same port direct integration 시도

처음에는 현재 selective schedule이 걸린 `SK eth0 <-> TMDS ep1/eth1` 경로에서
직접 `ptp4l`을 시도했다.

결과:

```text
timed out while polling for tx timestamp
send peer delay request failed
LISTENING to FAULTY
```

즉 selective taprio와 같은 port에서 direct gPTP를 동시에 돌리는 방식은
현재 live 상태에서 안정적인 시작점이 아니었다.

## 2. 공통 PHC direct path로 전환

실무적으로 더 의미 있는 경로는
`SK eth1 <-> TMDS eth2` direct link로 SK의 공통 PHC `/dev/ptp0`를 동기화하는 것이다.

이유:

- SK `eth0`, `eth1`는 같은 PHC `/dev/ptp0`를 공유한다.
- `eth1` direct gPTP가 잡히면 `eth0 taprio`도 같은 시간 기준을 사용할 수 있다.

확인한 매핑:

- SK `eth1` -> `/dev/ptp0`
- TMDS `eth2` -> `/dev/ptp2`

## 3. direct path gPTP 상태

### SK `eth1`

```text
selected /dev/ptp0 as PTP clock
LISTENING -> MASTER
selected local clock 70ff76.fffe.1ff287 as best master
```

### TMDS `eth2`

```text
selected /dev/ptp2 as PTP clock
new foreign master 70ff76.fffe.1ff287-1
selected best master clock 70ff76.fffe.1ff287
... -> UNCALIBRATED on RS_SLAVE
```

즉 direct path에서도 다음까지만 확인되었다.

- BMCA 동작
- best master selection
- `UNCALIBRATED` 진입

하지만 아직 다음은 확보되지 않았다.

- stable `SLAVE`
- `rms/delay/freq` 안정화 로그

`priority1` 차이와 `transportSpecific 1`을 추가해도 이번 세션에서는 결과가 달라지지 않았다.

## 3-1. taprio / switch_mode / PHC epoch 분리 실험

다음 변수들을 각각 걷어내거나 보정한 direct path 비교를 추가로 수행했다.

1. `eth0` selective `taprio` 제거
2. `switch_mode=false`, `br-tsn` 제거
3. `phc_ctl /dev/ptp0 set`, `phc_ctl /dev/ptp2 set`로 PHC epoch 정렬
4. `tx_timestamp_timeout 1000` 설정

결과:

- direct path는 여전히 stable `SLAVE`로 내려가지 않았다.
- 특히 `switch_mode=false` direct 형상에서는 SK `eth1`에서 다음이 반복 재현되었다.

```text
timed out while polling for tx timestamp
send peer delay request failed
LISTENING to FAULTY on FAULT_DETECTED
```

따라서 현재 blocker는 단순히 `eth0 taprio selective schedule`과의 공존 문제로만 보기는 어렵다.
오히려 **SK eth1 direct gPTP runtime에서 tx timestamp / peer delay 경로가 불안정한 점**이 더 직접적인 원인 후보로 남는다.

## 3-2. raw PTP frame 교환 관찰

`tcpdump -i eth1/eth2 ether proto 0x88f7`로 direct path PTP frame을 직접 확인했다.

확인된 frame 종류:

- `Sync`
- `Follow_Up`
- `Announce`
- `Pdelay_Req`
- `Pdelay_Resp`
- `Pdelay_Resp_Follow_Up`

대표 예:

```text
SK eth1 -> 01:80:c2:00:00:0e  Pdelay_Req
TMDS eth2 -> 01:80:c2:00:00:0e  Pdelay_Resp
TMDS eth2 -> 01:80:c2:00:00:0e  Pdelay_Resp_Follow_Up
```

즉 현재 direct path에서는 **BMCA와 peer delay message 자체는 실제로 왕복**한다.
그럼에도 ptp4l state machine은 stable `SLAVE`까지 내려가지 않는다.

## 4. PHC 기준 future base-time 적용

gPTP stable lock은 아직 아니지만,
same PHC 기반 future `base-time` 적용 경로는 확인했다.

SK에서:

```text
phc_ctl /dev/ptp0 get
BASE_TIME = current PHC + 2s
```

적용 결과:

```text
qdisc taprio 8008
base-time 32276502750402
index 0 cmd S gatemask 0x1 interval 50000000
index 1 cmd S gatemask 0x4 interval 50000000
```

즉 **PHC 기준 미래 절대시각을 schedule에 넣는 경로 자체는 현재 live에서 유효**하다.

## 5. 현재 판단

Phase 5는 아직 완료가 아니다.

확정된 사실:

1. same-port selective taprio + gPTP direct 조합은 불안정할 수 있다.
2. 별도 direct path를 사용하면 BMCA와 `UNCALIBRATED`까지는 내려간다.
3. PHC 기준 future `base-time`으로 selective schedule 재생성은 가능하다.
4. `taprio` 제거, `switch_mode=false`, PHC epoch 정렬, `tx_timestamp_timeout` 증가로도 stable `SLAVE`는 아직 재현되지 않았다.
5. raw PTP frame 기준 `Sync/Announce/Pdelay_Req/Resp/Resp_Fup` 교환은 direct path에서 실제로 왕복한다.

현재 blocker:

```text
TMDS side stable SLAVE 미진입
```

## 현재 live 상태

- `eth0`: PHC-based selective taprio schedule 유지
- SK `eth1`: gPTP master 시도 상태
- TMDS `eth2` root namespace: gPTP slave 시도 상태
- TMDS `ep1/eth1`: receiver path 유지

복구 후 현재 live 형상:

- SK `switch_mode=true`
- SK `br-tsn=10.50.0.2/24`
- SK `br-tsn.301=10.31.0.3/24`
- SK `eth0`: selective taprio schedule 유지
