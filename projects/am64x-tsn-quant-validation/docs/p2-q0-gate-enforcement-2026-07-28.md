# P2-Q0 Qbv Gate Enforcement Qualification

## 목적

P2 `QBV_MULTICLASS_01`의 ON window validation 전에, P2 critical PTP event frame 자체가 CPSW hardware
EST gate의 영향을 받는지 TX/RX raw-HW timestamp로 확인했다.

## 결론

```text
PCP 7 P2 critical frame: Qbv gate-controlled traffic으로 사용할 수 없음
PCP 2 P2 critical frame: gate enforcement PASS
P2-Q3 multiclass ON window qualification: 진행 가능
```

## 원인 분리

초기 P2는 raw Ethernet frame 안에 VLAN PCP 7을 직접 넣고 `SO_PRIORITY=3`을 설정했다.
`taprio map 0 0 1 2 ...`와 `0x5 125 us -> 0x1 375 us` schedule에서 TC2-closed phase
`200 us`에 송신해도 다음 현상이 반복됐다.

```text
TX raw-HW phase: 214~304 us
RX raw-HW phase: 214~304 us
TX release delay p50: 약 19 us
```

양쪽 `ptp4l`을 중지한 동일 시험에서도 결과가 같으므로, gPTP Sync의 16-bit sequence
timestamp collision은 원인이 아니다. SK taprio child queue `100:3` counter도 증가했으므로
socket priority/classifier 누락도 아니다.

동일 frame, 동일 `SO_PRIORITY=3`, 동일 schedule에서 VLAN PCP만 2로 바꾸자 결과가
바뀌었다. 따라서 P2 raw frame의 직접 VLAN PCP 7 설정이 CPSW EST timed class와 맞지
않았던 것으로 판정한다. `taprio flags 0x2` 수용 또는 TC child qdisc hit만으로는 이
조건을 증명할 수 없다.

## 채택 P2 Critical Contract

```text
EtherType: 0x88f7, PTPv2 L2 Sync, domain 127
frame size: 128 B
socket priority: 3
VLAN: 311
wire PCP: 2
taprio map: 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0
critical gate: bit 2
```

`p2_ptp_l2_hwts_sender.c`는 `P2_VLAN_PCP` environment variable을 지원하며, 검증된
P2 default는 PCP 2다. 다른 PCP를 사용하면 P2-Q0를 다시 통과해야 한다.

## Same-Port gPTP Q0 Result

Q0 schedule은 TC1 gPTP traffic을 전 cycle 열고, critical PCP 2/bit 2만 첫 window에
열도록 구성했다.

```text
0x6 125000 ns  # TC1 + critical bit 2
0x3 375000 ns  # TC0 + TC1
cycle 500000 ns
```

`ptp4l` 상태:

```text
SK eth0: MASTER, peerMeanPathDelay 421 ns
TMDS eth1: SLAVE, peerMeanPathDelay 420 ns
TMDS steady offset: -11 .. -1 ns
```

### Closed Phase

critical planned phase는 `200000 ns`다.

```text
TX raw-HW: 100/100
RX raw-HW: 100/100
TX release delay: min/p50/max = 300.370 / 300.370 / 300.370 us
SK TX phase: 370 ns
TMDS RX phase: 792 .. 794 ns
```

TC2/bit-2 closed interval에서 나온 frame이 다음 cycle open window까지 약 300 us
대기한 직접 증거다.

### Open Phase

critical planned phase는 `25000 ns`다.

```text
TX raw-HW: 100/100
RX raw-HW: 100/100
TX release delay: min/p50/max = 17.106 / 21.294 / 475.370 us
TMDS RX phase median: 46659 ns
TMDS ptp4l: SLAVE
```

대부분의 open-phase frame은 즉시 release됐다. max 475.370 us sample 하나는 125 us
window 경계의 scheduler miss로 다음 cycle까지 대기한 결과이며, formal P2 run에서는
open-window guard margin과 miss count를 별도 기록한다.

## P2 다음 단계

P2는 ON/OFF release-delay 우열 비교가 아니라, PCP 2/TC2 frame이 실제 CPSW EST gate에
의해 제어된다는 이 결과를 전제로 한다. 이후 시험은 TC0 background가 자신의 allocation을
초과한 상태에서 TC2 frame이 지정 window 안에 release되는지를 정량화한다. 정확한 schedule,
traffic contract와 validity gate는 `p2-q3-multiclass-window-validation-plan-2026-07-28.md`를
따른다.
