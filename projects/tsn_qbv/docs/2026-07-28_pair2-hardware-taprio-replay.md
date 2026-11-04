# 2026-07-28 Pair 2 Hardware Taprio Replay

## 목적

기존 Phase A/Phase B의 기준 경로인 `SK eth0(CPSW) -> TMDS eth1(CPSW)`에서
hardware `taprio` functional replay를 수행했다. 이 기록은 P2의 PTP raw-HW
latency 계측과 분리한다.

## 공통 조건

```text
VLAN: 311
SK eth0.311: 10.33.0.1/24
TMDS eth1.311: 10.33.0.2/24
taprio map: 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0
```

- SK `eth0`: TX queue 3, `p0-rx-ptype-rrobin=off`, link 1 Gbit/s full duplex.
- `UDP/5001 -> skb priority 3 -> TC2 -> wire PCP 7`.
- `UDP/5002 -> skb priority 2 -> TC1 -> wire PCP 6`.
- VLAN egress map은 `2:6`, `3:7`을 사용했다.
- 양쪽의 P2 `ptp4l` process는 run 전후 살아 있었다.

`board/prepare_endpoint_target.sh`의 기본 classifier와 egress map도 위
internal priority/PCP 조합으로 수정했다. 기존 `priority 7/6`은 이 `taprio map`
기준에서 TC2/TC1을 의도대로 선택하지 않는다.

## B0: 500 us Hardware Replay

적용 schedule:

```text
0x4 125000 ns  # TC2
0x2 125000 ns  # TC1
0x1 250000 ns  # TC0
```

관측 결과:

- `tc qdisc`에 `flags 0x2`, `cycle-time 500000`가 표시됐다.
- 새로운 `fetch RAM` 또는 taprio offload error는 없었다.
- TMDS lower device `eth1` capture에서 VLAN 311 PCP 7 및 PCP 6 frame을 확인했다.
- `UDP/5001`, `UDP/5002`를 각각 `20 Mbit/s`, 10초 동안 동시 송신했고 양쪽 모두 receiver loss `0/17267`, `0/17266`이었다.
- SK taprio child queue `100:3`과 `100:2` 및 두 egress classifier counter가 모두 증가했다.

판정: Phase A의 hardware Qbv offload, classifier-to-TC mapping, wire PCP 보존
functional evidence를 재현했다.

## B2: Timing Observation

### Single Flow

PCP 7 `20 Mbit/s` traffic을 TMDS `eth1.311`에서 text capture했다.

```text
captured packets: 17000
inter-packet gap median: 570.059 us
```

이 값은 500 us cycle과 같은 차수의 burst/capture cadence를 보이지만, sender pacing과
receiver capture coalescing을 분리한 all-open control이 없으므로 gate phase proof로
해석하지 않는다.

### Dual Flow

PCP 7 및 PCP 6를 각각 `80 Mbit/s`, 20초 동안 동시 송신했다.

```text
UDP/5001 receiver: 80.0 Mbit/s, loss 0/138125
UDP/5002 receiver: 80.0 Mbit/s, loss 0/138139
capture packets: 29998
PCP 7: 15027
PCP 6: 14971
PCP runs: 21237
per-PCP run-start median delta: 163 us
```

두 PCP가 clean alternating group으로 나타나지 않았다. 따라서 이 run은 Phase B의
strong B2 criterion을 충족하지 않으며, 기존 Phase B의 dual-flow timing 한계와
일치한다.

## B3: Gate-Close Stress

PCP 7 single-flow `300 Mbit/s`, 8초 run을 추가로 수행했다.

```text
sender: 300 Mbit/s, 0/207184 loss
receiver: 299 Mbit/s, 648/207184 loss (0.31%)
taprio requeues: 0
```

이번 run은 기존 Phase B B3에 기록된 500 us stress result
(`receiver ~=154.18 Mbit/s`)를 재현하지 못했다. 따라서 B3 gate-close rate-limiting
claim을 이 run으로 갱신하거나 강화하지 않는다. 기존 B3 원시 실행 조건과 비교 가능한
offered-load, capture, qdisc-counter baseline을 확보한 뒤 별도 재현해야 한다.

## 종료 상태

selective schedule 검증을 마친 뒤 live P2 session을 보존하기 위해 SK `eth0`을
hardware all-open schedule로 복귀했다.

```text
0x7 500000 ns
flags 0x2
```

이 상태는 Qbv gate-protection 검증용 schedule이 아니다. P2 raw-HW latency 또는
release-delay 결과에 Qbv 효과를 부여하지 않는 안전한 resting state다.

## 현재 판정

```text
hardware Qbv offload/functionality: PASS (기존 Phase A와 이번 B0 replay)
clean dual-flow timing causality: PARTIAL / 미확보
gate-close stress rate-limiting 재현: 미완
PTP raw-HW latency를 통한 Qbv protection claim: 미검증
```

다음 재현은 기존 B3와 직접 비교 가능한 원시 command/artifact를 먼저 확보하고,
all-open control과 selective schedule을 같은 sender rate 및 같은 capture 방식으로
paired run 해야 한다.
