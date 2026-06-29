# Pair2 CPSW-to-CPSW Hardware Taprio Validation

> Evidence-only note: current canonical summary is `docs/phaseA-endpoint-egress-qbv.md`.

## 1. Purpose

두 번째 direct pair인 `SK eth0(CPSW) <-> TMDS eth1(CPSW)`에서도 hardware `taprio` 기반 Qbv egress가 동작하는지 확인한다.

이 문서는 다음 세 가지를 분리해서 기록한다.

1. `SK eth0 -> TMDS eth1` hardware `taprio` egress 결과
2. `TMDS eth1 -> SK eth0` hardware `taprio` egress 가능 여부
3. `SK eth0 -> TMDS eth1` hardware `taprio` 상태에서 gPTP coexistence 결과

## 2. Environment Clarification

- SK-AM64B는 control Ethernet 포트가 없다.
- SK 제어 기준은 항상 UART다.
- TMDS64EVM의 control 포트는 `eth0`다.
- TMDS `eth1`, `eth2`는 실험 대상 data/test 포트다.

현재 direct pair는 둘이다.

```text
Pair 1: SK eth1 (CPSW) <-> TMDS eth2 (ICSSG)
Pair 2: SK eth0 (CPSW) <-> TMDS eth1 (CPSW)
```

이번 문서는 `Pair 2`만 다룬다.

## 3. Test Topology

- sender/receiver pair: `SK eth0 <-> TMDS eth1`
- 둘 다 driver: `am65-cpsw-nuss`
- VLAN: `311`
- IP:
  - `SK eth0.311 = 10.33.0.1/24`
  - `TMDS eth1.311 = 10.33.0.2/24`

공통 주의:

- 이번 pair에서도 `eth0.311`, `eth1.311`이 `169.254.x.x`로 drift하는 현상이 재현되었다.
- 실제 traffic 실패 원인은 여러 번 이 drift였다.

## 4. SK eth0 -> TMDS eth1

### 4.1 Prerequisite

- `SK eth0`:
  - `TX=3`
  - `p0-rx-ptype-rrobin=off`
  - VLAN `egress-qos-map` 적용
- `TMDS eth1`:
  - receiver only
  - `eth1.311=10.33.0.2/24`

### 4.2 Hardware taprio schedule

```bash
tc qdisc replace dev eth0 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 125000 \
  sched-entry S 02 125000 \
  sched-entry S 01 250000 \
  flags 2
```

### 4.3 Result

- `flags 2` apply 성공
- `tc -s qdisc show dev eth0`:
  - `flags 0x2`
  - `cycle-time 500000`
- `iperf3`:
  - `5001`: sender/receiver `20.0 Mbits/sec`, loss `0/8634`
  - `5002`: sender/receiver `20.0 Mbits/sec`, loss `0/8634`
- filter counters:
  - priority `7`: `12866128 bytes / 8649 pkt`
  - priority `6`: `12866125 bytes / 8649 pkt`
- TMDS capture saved:
  - `projects/tsn_qbv/logs/2026-06-29_sketh0-to-tmdseth1_hw_taprio.txt`
- capture count:
  - `p7 = 8635`
  - `p6 = 8635`
  - `p0 = 2`

### 4.4 Decision

`SK eth0(CPSW)`도 `SK eth1(CPSW)`와 동일하게 TI reference `500 us` cycle hardware `taprio`를 정상 지원한다.

## 5. TMDS eth1 -> SK eth0

### 5.1 Observed blocker

TMDS `eth1`도 CPSW라서 겉보기에는 같은 방식으로 될 것 같지만, 현재 프로젝트의 control model 때문에 바로 막힌다.

현재 TMDS 상태:

- control port: `eth0`
- test sender port: `eth1`
- `eth1` private flag 확인 결과:

```text
p0-rx-ptype-rrobin: on
```

이 상태에서 `eth1`에 hardware `taprio`를 넣으면 driver가 즉시 거부한다.

```text
Error: ti_am65_cpsw_nuss: p0-rx-ptype-rrobin flag conflicts with taprio qdisc.
```

그럼 `eth1`를 down 시키고 flag를 끄면 되는가를 시험했지만, 다음으로 막혔다.

```text
netlink error: Device or resource busy
```

이는 `TMDS eth0`가 같은 CPSW instance의 control port로 살아 있는 현재 운용 조건과 충돌하는 것으로 해석된다.

### 5.2 Current decision

```text
TMDS eth1 -> SK eth0 direction의 hardware taprio 검증은
현재 TMDS eth0 control-port 유지 조건에서는 blocked다.
```

즉, silicon/driver가 원천적으로 불가능하다고 결론낸 것은 아니다.
현재 프로젝트 운용 모델 때문에 prerequisite를 안전하게 맞출 수 없어서 막힌 것이다.

## 6. gPTP Coexistence on SK eth0 -> TMDS eth1

### 6.1 Schedule

gPTP frame이 기본 TC0로 계속 나갈 수 있도록 `TC0 always-open` hardware schedule을 사용했다.

```bash
tc qdisc replace dev eth0 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 05 250000 \
  sched-entry S 03 250000 \
  flags 2
```

의미:

- `0x5`: `TC0 + TC2` open
- `0x3`: `TC0 + TC1` open

### 6.2 gPTP config

양쪽 모두 다음 설정 사용:

```text
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
tx_timestamp_timeout 100
```

### 6.3 Result

- SK sender traffic:
  - `5001`: sender/receiver `20.0 Mbits/sec`, loss `0/13814`
  - `5002`: sender/receiver `20.0 Mbits/sec`, loss `0/13814`
- TMDS `ptp4l` state:

```text
LISTENING -> MASTER -> UNCALIBRATED -> SLAVE
```

- observed log:
  - `MASTER to UNCALIBRATED on RS_SLAVE`
  - `UNCALIBRATED to SLAVE on MASTER_CLOCK_SELECTED`
- no observed error pattern:
  - no `FAULTY`
  - no `timed out while polling for tx timestamp`
  - no `send peer delay request failed`
  - no `master sync timeout`
  - no `master tx announce timeout`

### 6.4 Decision

`SK eth0 -> TMDS eth1` 방향에서는 hardware `taprio(flags 2)` 상태에서도 gPTP coexistence가 성립한다.

## 7. Summary

| Direction | Port Types | HW taprio Qbv | gPTP coexistence | Status |
|---|---|---|---|---|
| `SK eth0 -> TMDS eth1` | CPSW -> CPSW | success at `500 us` | success with `TC0 always-open` schedule | pass |
| `TMDS eth1 -> SK eth0` | CPSW -> CPSW | blocked by TMDS control-port model and `p0-rx-ptype-rrobin` prerequisite | not run | blocked |

## 8. Next Action

1. `TMDS eth1` reverse-direction hardware `taprio`를 하려면 TMDS `eth0` control 유지와 충돌하지 않는 안전한 방법이 있는지 먼저 정해야 한다.
2. 현재까지 확보된 결과를 기준으로 `hardware taprio`와 `software taprio`의 차이를 endpoint 관점에서 정리한다.
