# Phase A Endpoint Egress Qbv

## 역할

이 문서는 `projects/tsn_qbv`의 Phase A closeout 문서다.

- `switch_mode=true` TSN switch/gPTP blocker 트랙과 분리된
- `switch_mode=false` direct endpoint path 기준
- 단방향 Qbv egress 검증 결과를 현재 기준으로 마무리한다.

현재 프로젝트에서 Phase A와 관련된 **single source of truth**는 이 문서다.

다른 날짜별 문서는 증거 로그와 세부 실험 기록으로만 유지한다.

## 범위

포함하는 direct endpoint 경로:

1. `SK eth0(CPSW) -> TMDS eth1(CPSW)`
2. `SK eth1(CPSW) -> TMDS eth2(ICSSG)`
3. `TMDS eth2(ICSSG) -> SK eth1(CPSW)`

제외:

- `TMDS eth1(CPSW) -> SK eth0(CPSW)`
  - 이유: 현재 TMDS `eth0` control-port 유지 조건 때문에 `p0-rx-ptype-rrobin off` prerequisite를 안전하게 맞출 수 없음

## 기본 환경

### 보드 제어 기준

- SK-AM64B: control Ethernet 포트 없음, 항상 UART 기준
- TMDS64EVM: `eth0`가 control 포트, `eth1`/`eth2`는 test 포트

### direct pair

```text
Pair 1: SK eth1 (CPSW) <-> TMDS eth2 (ICSSG)
Pair 2: SK eth0 (CPSW) <-> TMDS eth1 (CPSW)
```

### 공통 함정

- VLAN subinterface가 재시험 중 `169.254.x.x`로 drift할 수 있다.
- 실제 실패 원인이 `taprio`가 아니라 IP drift였던 경우가 반복되었다.
- 따라서 각 run 시작 전 항상 `ip -4 addr show dev ethX.Y`로 test IP를 재확인해야 한다.

## 최종 Matrix

| Direction | SW taprio egress | HW taprio egress | SW + gPTP coexistence | HW + gPTP coexistence | 최종 판정 |
|---|---|---|---|---|---|
| `SK eth0 -> TMDS eth1` | success | success | success | success | 가장 안정적인 reference path |
| `SK eth1 -> TMDS eth2` | success | success | success | partial | HW path는 traffic은 유지되지만 gPTP state가 불안정 |
| `TMDS eth2 -> SK eth1` | success | success | success | fail | HW path는 `tx timestamp timeout`으로 gPTP failure |

## 판단 기준

### Qbv egress 검증 success 기준

다음 4개를 함께 본다.

1. `taprio` apply 성공
2. sender traffic 또는 filter counter 증가
3. receiver iperf success
4. receiver wire capture에서 intended PCP 확인

### hardware taprio success 근거

- `tc -s qdisc show dev <iface>`에 `flags 0x2`

### software taprio success 근거

- `tc -s qdisc show dev <iface>`에 `clockid TAI`

### gPTP coexistence success 기준

- concurrent traffic 중 `MASTER -> UNCALIBRATED -> SLAVE` 수렴 또는 stable `SLAVE` 유지
- 동시에 다음 failure signature가 없어야 한다.
  - `FAULTY`
  - `timed out while polling for tx timestamp`
  - `send peer delay request failed`
  - `master sync timeout`
  - `master tx announce timeout`

## 경로별 closeout

### 1. SK eth0(CPSW) -> TMDS eth1(CPSW)

결론:

```text
SW/HW taprio 모두 성공
SW/HW 모두 gPTP coexistence 성공
```

핵심 근거:

- hardware `taprio`:
  - TI reference `500 us` cycle (`125 us / 125 us / 250 us`) success
  - TMDS wire capture `vlan 311, p7` / `vlan 311, p6`
- hardware coexistence:
  - `TC0 always-open` hardware schedule (`0x5/0x3`)에서 TMDS `eth1`이 `MASTER -> UNCALIBRATED -> SLAVE`
  - concurrent traffic `20 Mbits/sec`, loss `0`
- software coexistence:
  - same `0x5/0x3` schedule의 software `taprio`에서도 TMDS `eth1`이 `MASTER -> UNCALIBRATED -> SLAVE`
  - concurrent traffic `20 Mbits/sec`, loss `0`

현재 Phase A 기준 가장 안정적인 replay/reference 조합이다.

### 2. SK eth1(CPSW) -> TMDS eth2(ICSSG)

결론:

```text
SW/HW taprio egress는 모두 성공
SW + gPTP coexistence는 성공
HW + gPTP coexistence는 partial / unstable
```

핵심 근거:

- hardware egress:
  - `500 us` hardware `taprio(flags 2)` success
  - TMDS wire capture `vlan 301, p7` / `vlan 301, p6`
- software coexistence:
  - same direct path에서 `p7/p6` traffic과 gPTP `SLAVE` 유지 성공
  - `FAULTY`, `tx timestamp timeout`, `send peer delay request failed` 없음
- hardware coexistence:
  - `TC0 always-open` hardware schedule에서 traffic은 유지됨
  - 그러나 SK `ptp4l`은 `LISTENING -> FAULTY -> LISTENING -> GRAND_MASTER`
  - TMDS `ptp4l`은 `LISTENING -> UNCALIBRATED -> SLAVE` 후 `SLAVE -> MASTER -> UNCALIBRATED -> SLAVE` 재천이

따라서 same-port hardware `taprio + gPTP`는 아직 stable success로 판정하지 않는다.

### 3. TMDS eth2(ICSSG) -> SK eth1(CPSW)

결론:

```text
SW/HW taprio egress는 모두 성공
SW + gPTP coexistence는 성공
HW + gPTP coexistence는 실패
```

핵심 근거:

- hardware egress:
  - ICSSG minimum cycle 제약 때문에 `1 ms` cycle 필요
  - `TX=3`, VLAN `egress-qos-map` 필요
  - 그 조건에서는 hardware `taprio(flags 2)` success
- software coexistence:
  - software `taprio(clockid CLOCK_TAI)` + `1 ms` `TC0 always-open` schedule에서
  - TMDS `eth2`는 `MASTER -> UNCALIBRATED -> SLAVE`
  - concurrent traffic `20 Mbits/sec`, loss `0`
- hardware coexistence failure:
  - `timed out while polling for tx timestamp`
  - `send peer delay request failed`
  - `LISTENING -> FAULTY`

즉 reverse ICSSG sender path는 egress Qbv 자체는 되지만,
현재 same-port hardware `taprio + gPTP`는 실패한다.

## 최종 프로젝트 결론

### 1. Phase 5에서 분리된 단방향 Qbv 검증 closeout

Phase 5에서 분리된 endpoint egress Qbv 트랙은 현재 기준으로 closeout 가능하다.

closeout statement:

```text
Phase A endpoint egress Qbv closeout:

- direct endpoint path에서 단방향 Qbv egress effect는 SW/HW taprio 모두로 재현 가능하다.
- CPSW sender path는 HW taprio와 same-port gPTP coexistence까지 비교적 안정적으로 성립한다.
- ICSSG sender path는 SW taprio는 coexistence가 되지만, HW taprio는 same-port gPTP에서 아직 불안정하거나 실패한다.
```

### 2. 현재 실무적 의미

- direct endpoint 기준에서 hardware Qbv capability 자체는 이미 증명되었다.
- 다만 `same-port gPTP coexistence`는 sender endpoint 종류에 따라 다르다.
- 따라서 다음 단계에서 hardware Qbv sender의 실무 기준 경로는 우선 `CPSW sender path`를 기준으로 삼는 편이 안전하다.

## 재시험 기준 자산

### canonical replay guide

- `docs/phaseA-replay-guide.md`

### 유지 기준 helper

- `board/prepare_endpoint_target.sh`
- `board/apply_taprio.sh`
- `board/write_gptp_cfg.sh`

위 3개 스크립트를 현재 재시험 기준으로 본다.

기존 `setup_phaseA_*` 스크립트는 초기 진행 흔적이므로,
새 replay 기준은 `phaseA-replay-guide.md`와 위 helper에 맞춘다.

## 증거 문서

다음 문서는 canonical summary가 아니라 evidence log다.

- `docs/2026-06-29_am64x-cpsw-hardware-taprio-est-minimal-validation.md`
- `docs/2026-06-29_bidirectional-endpoint-hardware-taprio-validation.md`
- `docs/2026-06-29_pair2-cpsw-to-cpsw-hardware-taprio-validation.md`
- `docs/2026-06-29_endpoint-taprio-coexistence-matrix.md`
- `docs/2026-06-29_hw-vs-sw-taprio-summary.md`

필요할 때 근거를 재확인하는 용도로만 참조한다.
