# Phase B Endpoint Egress Qbv Timing Validation

> Project: `projects/tsn_qbv`  
> 범위: `switch_mode=false` direct endpoint path 전용  
> 제외: CPSW `switch_mode=true` TSN switch / time-aware bridge 검증  
> 입력 baseline: Phase A endpoint egress Qbv closeout

---

## 1. 목적

Phase A에서는 direct endpoint 경로에서 `taprio`를 적용하고, intended PCP traffic을 송신/수신할 수 있음을 확인했다.

Phase A가 주로 확인한 것은 다음이다.

```text
hardware/software taprio apply
PCP-marked traffic transmission
receiver-side PCP observation
gPTP coexistence on selected paths
```

Phase B의 목적은 endpoint egress 동작이 실제로 Qbv/TAS/EST 의미에 맞게 동작하는지 확인하는 것이다.

Phase B에서 답해야 하는 질문은 다음이다.

```text
traffic이 의도한 gate-open window에서만 egress port로 나가는가?
gate-closed window에서 traffic이 지연되거나 차단되는가?
packet burst timing이 설정한 cycle-time을 따라가는가?
future base-time을 설정했을 때 schedule 시작 phase가 예상대로 바뀌는가?
이 동작이 gPTP를 깨지 않고 공존 가능한가?
```

이 문서는 endpoint egress 검증 문서이며, switch-mode 검증 문서가 아니다.

---

## 2. Phase A 기준 현재 Baseline

### 2.1 검증된 reference path

Phase A에서 가장 안정적인 reference path는 다음이다.

```text
SK eth0(CPSW hardware taprio sender) -> TMDS eth1(CPSW receiver)
```

Phase B는 이 경로를 1순위 기준으로 사용한다.

### 2.2 보조 path

```text
SK eth1(CPSW hardware taprio sender) -> TMDS eth2(ICSSG receiver)
```

이 경로에서는 hardware egress traffic은 확인되었지만, same-port hardware taprio + gPTP coexistence가 불안정했다. reference path가 안정화된 뒤에 보조 확인용으로만 사용한다.

### 2.3 보류 path

```text
TMDS eth2(ICSSG hardware taprio sender) -> SK eth1(CPSW receiver)
```

이 경로에서는 ICSSG hardware egress traffic은 확인되었지만, hardware taprio + same-port gPTP에서 TX timestamp 관련 오류가 발생했다. 별도 ICSSG follow-up item으로 유지한다.

### 2.4 제외 path

```text
TMDS eth2 -> SK switch ingress -> SK switch egress -> TMDS eth1
```

이 경로는 `switch_mode=true`가 필요하며, 현재 switch-mode gPTP issue로 인해 별도 blocker track으로 분리한다.

---

## 3. Phase B 성공 기준

### 3.1 최소 성공 기준

CPSW reference path에서 다음을 모두 만족하면 Phase B 최소 성공으로 본다.

```text
1. hardware taprio offload가 flags 2로 성공적으로 적용된다.
2. receiver에서 의도한 VLAN PCP 값이 관측된다.
3. p7 traffic과 p6 traffic이 분리된 burst group으로 나타난다.
4. gate schedule을 변경하면 burst grouping도 함께 변경된다.
5. dmesg에 새로운 taprio/EST offload error가 발생하지 않는다.
```

### 3.2 강한 성공 기준

다음까지 만족하면 Phase B strong success로 본다.

```text
1. p7 packet은 TC2-open window에서만 관측된다.
2. p6 packet은 TC1-open window에서만 관측된다.
3. gate-close window에서는 닫힌 TC의 packet이 관측되지 않는다.
4. 측정된 burst 반복 주기가 설정한 cycle-time과 대략 일치한다.
5. future base-time을 바꾸면 traffic phase/start timing도 예상대로 바뀐다.
6. hardware taprio traffic이 동작하는 동안 gPTP가 SLAVE/stable 상태를 유지한다.
```

### 3.3 Phase B로 증명하지 않는 것

Phase B가 성공해도 다음을 주장하지 않는다.

```text
SK-AM64B가 TSN switch로 동작한다.
CPSW switch_mode=true Qbv가 동작한다.
time-aware bridge residence/correction behavior가 검증되었다.
ICSSG hardware Qbv와 same-port gPTP 문제가 완전히 해결되었다.
```

Phase B에서 주장 가능한 결론은 다음이다.

```text
AM64x CPSW endpoint egress hardware Qbv/EST timing behavior가 direct link에서 검증되었다.
```

---

## 4. Test Topology

### 4.1 Primary topology

```text
SK-AM64B eth0 / CPSW / hardware taprio sender
  -> direct cable
TMDS64EVM eth1 / CPSW / receiver
```

### 4.2 권장 VLAN/IP

```text
VID 311
SK eth0.311:   10.31.1.1/24
TMDS eth1.311: 10.31.1.2/24
```

### 4.3 Traffic class 정의

```text
TC0: best-effort / gPTP-safe traffic class
TC1: PCP 6 / UDP dport 5002
TC2: PCP 7 / UDP dport 5001
```

### 4.4 Gate mask 의미

```text
0x1 = TC0 open
0x2 = TC1 open
0x4 = TC2 open
0x3 = TC0 + TC1 open
0x5 = TC0 + TC2 open
0x7 = TC0 + TC1 + TC2 open
```

---

## 5. 공통 Setup

## 5.1 SK cleanup

SK UART에서 실행한다.

```bash
pkill ptp4l 2>/dev/null || true
pkill phc2sys 2>/dev/null || true
pkill iperf3 2>/dev/null || true

for dev in eth0 eth1 eth0.311 eth1.301 br-tsn; do
    ip link del "$dev" 2>/dev/null || true
done

tc qdisc del dev eth0 root 2>/dev/null || true
tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth0 clsact 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true

devlink dev param set platform/8000000.ethernet name switch_mode value false cmode runtime 2>/dev/null || true

ip addr flush dev eth0 2>/dev/null || true
ip addr flush dev eth1 2>/dev/null || true
ip link set eth0 down
ip link set eth1 down
```

## 5.2 SK CPSW EST prerequisite

SK UART에서 실행한다.

```bash
ethtool -L eth0 tx 3
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off

ethtool -l eth0
ethtool --show-priv-flags eth0

ip link set eth0 up
sleep 2
ethtool eth0 | grep -E "Speed|Duplex|Link detected"
```

필수 확인 항목:

```text
TX queues: 3 이상
p0-rx-ptype-rrobin: off
Link detected: yes
Speed: 1000Mb/s
Duplex: Full
```

## 5.3 TMDS receiver setup

TMDS에서 실행한다.

```bash
pkill iperf3 2>/dev/null || true
ip link del eth1.311 2>/dev/null || true
ip addr flush dev eth1 2>/dev/null || true

ip link set eth1 up
ip link add link eth1 name eth1.311 type vlan id 311
ip addr add 10.31.1.2/24 dev eth1.311
ip link set eth1.311 up

ip -br addr show eth1 eth1.311
ethtool eth1 | grep -E "Speed|Duplex|Link detected"

iperf3 -s -D -p 5001
iperf3 -s -D -p 5002
```

## 5.4 SK sender VLAN setup

SK UART에서 실행한다.

```bash
ip link add link eth0 name eth0.311 type vlan id 311
ip link set eth0.311 type vlan egress 0:0 1:1 2:6 3:7 4:4 5:5 6:6 7:7
ip addr add 10.31.1.1/24 dev eth0.311
ip link set eth0.311 up

ip -d link show eth0.311
ip -br addr show eth0 eth0.311
```

위 egress map은 internal priority `2 -> PCP 6`, `3 -> PCP 7`을 만들기 위한 기준이다.

## 5.5 Priority marking filter

SK UART에서 실행한다.

```bash
tc qdisc add dev eth0.311 clsact 2>/dev/null || true

tc filter add dev eth0.311 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff \
  action skbedit priority 3

tc filter add dev eth0.311 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff \
  action skbedit priority 2

tc -s filter show dev eth0.311 egress
```

이 문서의 `taprio map 0 0 1 2 ...` 기준에서는 internal priority `3 -> TC2`, `2 -> TC1` 조합을 사용한다.

### 5.6 Receiver capture 주의

이번 검증에서는 다음처럼 capture 역할을 나눴다.

```text
wire PCP 확인: lower dev `eth1`
timing capture: `eth1.311`
```

lower dev `eth1`에서는 VLAN offload/raw path 때문에 Phase B timing용 timestamp/text capture가 불안정할 수 있다.

---

# 6. Phase B Test Plan

---

## B0. Hardware taprio replay sanity

### 목적

Phase A에서 확인한 hardware taprio 성공이 재현 가능한지 확인한다. Timing validation 전에 반드시 수행한다.

### Schedule

TI reference와 유사한 짧은 schedule을 사용한다.

```text
cycle: 500 us
TC2 open: 125 us
TC1 open: 125 us
TC0 open: 250 us
```

### Command

SK UART에서 실행한다.

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

tc -s qdisc show dev eth0
dmesg | grep -iE "taprio|tas|est|fetch|ram|cpsw|offload|qos" | tail -n 120
```

### Traffic

SK UART에서 실행한다.

```bash
iperf3 -c 10.31.1.2 -u -b 20M -t 10 -p 5001
iperf3 -c 10.31.1.2 -u -b 20M -t 10 -p 5002
```

### Receiver capture

TMDS에서 실행한다.

```bash
tcpdump -i eth1 -e -tttt -vvv -n "vlan and udp" -w /tmp/phaseB_B0_hw_taprio_500us.pcap
```

### Pass criteria

```text
tc qdisc에 flags 0x2가 보인다.
No fetch RAM error가 없다.
receiver에서 p7/p6 frame이 보인다.
iperf가 성공한다.
```

---

## B1. Hardware cycle fixed-case validation

### 목적

TI 공식 자료 기준으로 이미 알려진 두 cycle case를 고정 baseline으로 검증한다.

```text
500 us
8 ms
```

이 문서에서는 더 긴 accepted cycle을 탐색하지 않는다.

- `500 us`: Phase A에서 재현된 짧은 reference cycle
- `8 ms`: TI 공식 자료 기준 상한 reference cycle

이후 timing 검증 항목은 두 cycle 모두에서 수행해야 한다.

### Fixed schedules

#### 500 us cycle

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

#### 8 ms cycle

```bash
tc qdisc replace dev eth0 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 2000000 \
  sched-entry S 02 2000000 \
  sched-entry S 01 4000000 \
  flags 2
```

### Per-cycle record

각 cycle case 적용 후 아래를 기록한다.

```bash
echo "===== qdisc ====="
tc -s qdisc show dev eth0

echo "===== dmesg ====="
dmesg | grep -iE "taprio|tas|est|fetch|ram|cpsw|offload|qos" | tail -n 120
```

### Pass criteria

두 cycle 모두에 대해 다음을 만족해야 한다.

```text
accepted
flags 0x2 observed
relevant dmesg error 없음
```

둘 중 하나라도 실패하면 Phase B timing closeout을 진행하지 않는다.

실패한 경우 정확한 `tc` error와 `dmesg` line을 기록한다.

---

## B2. Gate open/close timing observation

### 목적

p7 packet과 p6 packet이 gate window에 따라 분리된 burst로 나타나는지 확인한다.

### 사용할 schedule

B1에서 고정한 두 cycle을 모두 사용한다.

```text
500 us case
8 ms case
```

아래 timing 관측과 분석은 각 cycle별로 독립적으로 수행한다.

권장 구조:

```text
TC2/p7 open: cycle의 25%
TC1/p6 open: cycle의 25%
TC0 open:    cycle의 50%
```

### Capture

TMDS에서 실행한다.

```bash
rm -f /tmp/phaseB_B2_gate_timing.pcap

tcpdump -i eth1 -e -ttttt -vvv -n "vlan and udp" \
  -w /tmp/phaseB_B2_gate_timing.pcap
```

### Traffic

SK에서 p7/p6 traffic을 동시에 송신한다.

```bash
iperf3 -c 10.31.1.2 -u -b 80M -t 20 -p 5001 &
iperf3 -c 10.31.1.2 -u -b 80M -t 20 -p 5002 &
wait
```

closed window 동안 queue가 비지 않도록 충분한 offered load를 사용한다.

### 분석 목표

pcap에서 다음을 분석한다.

```text
p7 burst group
p6 burst group
p7/p6 alternating pattern
closed-window에서 닫힌 PCP packet이 나타나지 않는지
burst start-to-start interval이 configured cycle-time과 가까운지
```

### tshark 추출 예시

local host 또는 TMDS에 `tshark`가 있으면 실행한다.

```bash
tshark -r /tmp/phaseB_B2_gate_timing.pcap \
  -T fields \
  -e frame.time_epoch \
  -e vlan.priority \
  -e udp.dstport \
  > /tmp/phaseB_B2_packets.tsv
```

### Python 분석 예시

```python
import csv
from collections import Counter

path = "/tmp/phaseB_B2_packets.tsv"
rows = []
with open(path) as f:
    for line in f:
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        try:
            t = float(parts[0])
        except ValueError:
            continue
        pcp = parts[1]
        dport = parts[2]
        rows.append((t, pcp, dport))

print("packets", len(rows))
print("pcp counts", Counter(r[1] for r in rows))
print("dport counts", Counter(r[2] for r in rows))

# PCP 기준 run-length grouping
runs = []
last = None
count = 0
start = None
end = None
for t, pcp, dport in rows:
    key = pcp
    if key != last:
        if last is not None:
            runs.append((last, count, start, end, end - start if end and start else 0))
        last = key
        count = 1
        start = t
        end = t
    else:
        count += 1
        end = t
if last is not None:
    runs.append((last, count, start, end, end - start if end and start else 0))

print("first 30 runs")
for r in runs[:30]:
    print(r)

print("max runs by PCP")
for p in sorted(set(r[0] for r in runs)):
    subset = [r for r in runs if r[0] == p]
    print(p, "max_count", max(x[1] for x in subset), "runs", len(subset))

# burst start delta by PCP
for p in sorted(set(r[0] for r in runs)):
    starts = [r[2] for r in runs if r[0] == p]
    deltas = [starts[i+1] - starts[i] for i in range(len(starts)-1)]
    if deltas:
        print(p, "delta min/avg/max", min(deltas), sum(deltas)/len(deltas), max(deltas))
```

### Pass criteria

```text
500 us case와 8 ms case가 모두 아래 조건을 만족한다.
p7/p6가 랜덤하게 섞이지 않고 group으로 나타난다.
p7/p6 group이 schedule에 따라 번갈아 나타난다.
start-to-start delta가 cycle-time 또는 안정적인 cycle-time 배수에 가깝다.
```

---

## B3. Gate-close stress validation

### 목적

닫힌 gate가 실제로 traffic을 제한하는지 확인한다.

### 방법

예상 open-window capacity보다 높은 offered load를 건다.

이 검증은 `500 us` case와 `8 ms` case 각각에 대해 수행한다.

예:

```bash
iperf3 -c 10.31.1.2 -u -b 200M -t 20 -p 5001 &
iperf3 -c 10.31.1.2 -u -b 200M -t 20 -p 5002 &
wait
```

### 기대 동작

각 high-priority flow의 gate가 cycle의 25%만 열려 있다면, 각 flow는 unrestricted 200 Mbps egress처럼 동작하면 안 된다.

기대 관측:

```text
gate open window 동안 burst 발생
gate close window 동안 해당 PCP packet이 연속적으로 새어 나오지 않음
throughput이 open-window ratio의 영향을 받음
overload 상황에서 loss/drop이 증가할 수 있음
```

### 수집

```bash
tc -s qdisc show dev eth0
ethtool -S eth0 | grep -Ei "pri|prio|queue|fifo|tx|drop|tas|est" || true
dmesg | grep -iE "taprio|tas|est|fetch|ram|cpsw|offload|qos|drop" | tail -n 120
```

### Pass criteria

```text
500 us case와 8 ms case가 모두 아래 조건을 만족한다.
overload 시 throughput/loss/bursting이 gate window와 일관되게 변한다.
closed-gate PCP가 receiver에서 연속적으로 관측되지 않는다.
```

---

## B4. Schedule inversion test

### 목적

관측된 burst 순서가 iperf timing artifact가 아니라 gate schedule 때문임을 확인한다.

### 방법

두 schedule을 비교한다.

이 비교는 `500 us` case와 `8 ms` case 각각에서 수행한다.

Schedule A:

```text
p7 window first, then p6 window
0x4 -> 0x2 -> 0x1
```

Schedule B:

```text
p6 window first, then p7 window
0x2 -> 0x4 -> 0x1
```

### Schedule B 예시 command, 1 ms cycle

```bash
tc qdisc replace dev eth0 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 02 250000 \
  sched-entry S 04 250000 \
  sched-entry S 01 500000 \
  flags 2
```

### Pass criteria

```text
500 us case와 8 ms case 모두에서
schedule 순서를 반전했을 때 receiver의 burst 순서도 함께 반전된다.
```

이 테스트는 schedule causality를 보여주는 강한 검증이다.

---

## B5. Future base-time validation

### 목적

hardware taprio schedule이 단순히 즉시 적용되는 것이 아니라, 제어된 future base-time에서 시작하거나 phase-align되는지 확인한다.

### 요구 사항

SK eth0에 mapping된 PHC device를 찾는다.

```bash
ethtool -T eth0
readlink -f /sys/class/net/eth0/device/ptp/* 2>/dev/null || true
ls -l /sys/class/ptp
```

`phc_ctl`이 있으면 사용한다. 없으면 사용 가능한 local tool을 쓰거나 `/dev/ptpX`를 읽는 작은 helper를 작성한다.

### 절차

1. 현재 SK CPSW PHC time을 읽는다.
2. `base-time = current PHC time + 5 seconds`로 계산한다.
3. 해당 future base-time으로 hardware taprio를 적용한다.
4. base-time 전에 traffic을 시작한다.
5. receiver에서 packet capture를 수행한다.
6. scheduled burst pattern이 의도한 base-time 이후에 시작되거나 해당 phase에 align되는지 확인한다.

이 절차는 `500 us` case와 `8 ms` case 각각에 대해 수행하는 것을 기본으로 한다.

### Pass criteria

```text
500 us case와 8 ms case가 모두 아래 조건을 만족한다.
future base-time이 accepted 된다.
traffic/gate pattern이 configured base-time 기준으로 시작 또는 phase-align된다.
base-time을 변경하면 관측되는 traffic phase도 함께 이동한다.
```

### 주의

receiver tcpdump timestamp는 sender PHC time이 아니라 system time일 수 있다. 엄밀한 검증을 위해서는 system time을 동기화하거나, 여러 run에서 base-time 변경에 따른 상대적 phase shift를 비교한다.

---

## B6. gPTP + hardware taprio timing validation

### 목적

단순 coexistence를 넘어 timebase-aware validation으로 확장한다.

이 테스트는 “taprio가 gPTP를 깨지 않는다”를 확인하는 것에서 한 단계 더 나아가, gPTP lock 상태에서 hardware taprio timing 검증을 수행한다.

### Safe schedule

PTP traffic이 gated-out 되지 않도록 TC0 always-open schedule을 사용한다.

개념:

```text
Window A: TC0 + TC2 open = 0x5
Window B: TC0 + TC1 open = 0x3
```

### 절차

1. SK eth0와 TMDS eth1에서 ptp4l을 시작한다.
2. TMDS가 SLAVE에 진입하고 안정 유지될 때까지 기다린다.
3. `flags 2` hardware taprio를 TC0 always-open schedule로 적용한다.
4. p7/p6 traffic을 동시에 송신한다.
5. pcap을 수집한다.
6. ptp4l log를 계속 관찰한다.

이 절차는 `500 us` case와 `8 ms` case 각각에서 수행한다.

### Success criteria

```text
500 us case와 8 ms case가 모두 아래 조건을 만족한다.
TMDS가 SLAVE를 유지하거나 SLAVE로 재수렴한다.
FAULTY가 없다.
tx timestamp timeout이 없다.
send peer delay request failed가 없다.
master sync timeout이 없다.
traffic에서 scheduled p7/p6 burst behavior가 유지된다.
```

### 중요한 구분

이 테스트가 통과하면 다음을 의미한다.

```text
gPTP와 hardware taprio가 endpoint path에서 공존하며 traffic scheduling이 가능하다.
```

하지만 이것만으로 다음을 의미하지는 않는다.

```text
network-wide synchronized Qbv가 검증되었다.
```

더 강한 주장을 하려면 gPTP로 동기화된 PHC 기준의 base-time/phase validation이 필요하다.

---

## 7. Evidence Collection Checklist

모든 테스트의 시작과 끝에 아래를 수집한다.

### 7.1 SK

```bash
hostname
uname -a
ip -br link
ip -br addr

devlink dev param show platform/8000000.ethernet || true
ethtool -l eth0 || true
ethtool --show-priv-flags eth0 || true
ethtool -T eth0 || true

tc qdisc show dev eth0
tc -s qdisc show dev eth0
tc -s filter show dev eth0.311 egress || true

ethtool -S eth0 | grep -Ei "ale|drop|vlan|pri|prio|queue|fifo|tx|rx|tas|est" || true

dmesg | grep -iE "cpsw|taprio|tas|est|offload|fetch|ram|qos|ptp|cpts" | tail -n 200
```

### 7.2 TMDS

```bash
hostname
uname -a
ip -br link
ip -br addr
ethtool -i eth1
ethtool -T eth1
ip -d link show eth1.311
```

---

## 8. Result Template

```md
# Phase B Result - Endpoint Egress Qbv Timing Validation

## Summary

## Test Path

## Hardware Taprio State
- interface:
- flags 0x2 observed:
- schedule:
- cycle-time:
- accepted/rejected:
- dmesg:

## Traffic Setup
- VID:
- p7 flow:
- p6 flow:
- offered rate:

## Receiver Capture Summary
- p7 count:
- p6 count:
- run-length pattern:
- burst start delta:
- closed-window leakage:

## Base-time Test
- PHC device:
- current PHC:
- configured base-time:
- observed phase behavior:

## gPTP Coexistence
- ptp4l state:
- rms/freq/delay:
- failures:

## Decision
- minimum success:
- strong success:
- limitations:

## Next Action
```

---

## 9. Final Decision Rule

### 9.1 Phase B success closeout 가능 조건

```text
CPSW reference path에서
- B0는 500 us hardware replay sanity를 통과하고
- B1은 500 us와 8 ms 두 cycle 모두 accepted 되며
- B2, B3, B4, B6는 500 us와 8 ms 두 cycle 모두에서 통과한다.
```

### 9.2 Phase B strong success closeout 가능 조건

```text
CPSW reference path에서
- B0는 500 us hardware replay sanity를 통과하고
- B1은 500 us와 8 ms 두 cycle 모두 accepted 되며
- B2, B3, B4, B5, B6는 500 us와 8 ms 두 cycle 모두에서 통과한다.
```

### 9.3 Phase B closeout 금지 조건

```text
hardware taprio는 accepted 되었지만 p7/p6 burst timing이 schedule과 상관관계를 보이지 않는다.
또는
closed-window traffic이 연속적으로 leak된다.
또는
TC0 always-open hardware taprio 상태에서 gPTP가 실패한다.
또는
500 us case와 8 ms case 중 하나에서만 timing 검증이 성립한다.
```

---

## 10. Board Notes

### 10.1 SK-AM64B CPSW

Phase B의 primary target으로 사용한다.

```text
Recommended path:
SK eth0 -> TMDS eth1
```

이유:

```text
Phase A에서 이 경로가 가장 안정적인 CPSW hardware taprio + gPTP coexistence reference path로 확인되었다.
```

### 10.2 TMDS64EVM ICSSG

Phase B의 첫 번째 target으로 사용하지 않는다.

이유:

```text
ICSSG hardware taprio egress는 가능하지만, same-port gPTP에서 tx timestamp failure가 발생했다.
```

ICSSG는 별도 endpoint-specific investigation으로 유지한다.

### 10.3 switch_mode=true

명시적으로 제외한다.

이유:

```text
현재 환경에서 switch_mode=true 자체가 gPTP convergence를 깨는 blocker로 확인되었다.
```

별도 blocker track에서 다룬다.
