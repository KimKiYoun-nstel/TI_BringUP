# AM64x Qbv Endpoint Egress Validation Guide

> Project: `projects/tsn_qbv`  
> Document: `docs/phaseA-endpoint-egress-qbv.md`  
> Scope: Qbv/taprio 기능을 **switch_mode=true TSN switch**가 아니라, 두 보드의 **endpoint egress scheduler** 관점에서 먼저 검증한다.

---

## 1. 목적

기존 Qbv roadmap은 원래 SK-AM64B CPSW를 switch candidate로 사용해 `mqprio -> CBS -> taprio/Qbv -> gPTP 통합` 순서로 검증하는 흐름이었다. 하지만 Phase 5 분리 검증 결과, 현재 blocker는 taprio/Qbv 자체가 아니라 `switch_mode=true` 상태에서 gPTP가 안정적으로 SLAVE lock 되지 않는 문제로 분리되었다.

따라서 본 문서는 기존 roadmap은 유지하되, 우선 **선택지 A: endpoint/egress scheduler 방식**으로 Qbv 기능 자체를 검증하기 위한 별도 실행 가이드다.

핵심 목표는 다음이다.

```text
switch_mode=false direct endpoint path에서
PCP -> TC/queue -> taprio/Qbv gate schedule이 실제 egress 송신 패턴을 제어하는지 확인한다.
```

---

## 2. 검증 범위

이번 단계에서 검증하는 것:

```text
1. SK CPSW endpoint egress Qbv
   SK eth1(CPSW) -> TMDS eth2(ICSSG)

2. TMDS ICSSG endpoint egress Qbv
   TMDS eth2(ICSSG) -> SK eth1(CPSW)
```

선택적으로 추가 가능한 것:

```text
3. SK eth0(CPSW) -> TMDS eth1(CPSW)
4. TMDS eth1(CPSW) -> SK eth0(CPSW)
```

이번 단계에서 검증하지 않는 것:

```text
- SK CPSW switch_mode=true 기반 TSN switch
- gPTP time-aware bridge
- TMDS eth2 -> SK switchdev -> TMDS eth1 형태의 중간 switch forwarding
- switch_mode=true 상태에서 gPTP relay/bridge 동작
```

즉 이번 검증은 **Qbv 기능 자체를 endpoint egress 기준으로 확인**하는 단계다.

---

## 3. 현재까지 확보한 전제

기존 `tsn_dscp_pcp` 및 `tsn_qbv` 선행 실험에서 확보된 사실:

```text
- SK CPSW direct sender는 prerequisite 적용 후 VLAN PCP p7/p6 emit 가능
- TMDS eth2 ICSSG sender는 VLAN PCP p7/p6 emit 가능
- p0-rx-ptype-rrobin off 적용 가능
- mqprio hw 1 mode channel 적용 가능
- taprio/Qbv schedule 적용 경로 자체는 동작한 이력이 있음
- switch_mode=false direct gPTP는 안정 SLAVE lock 성공 이력이 있음
```

현재 분리된 blocker:

```text
- switch_mode=true 상태에서 gPTP stable SLAVE lock 실패
```

따라서 이번 문서에서는 `switch_mode=false`를 고정한다.

---

## 4. 추천 테스트 토폴로지

현재 케이블 구성 기준:

```text
TMDS eth1 <----> SK eth0
TMDS eth2 <----> SK eth1
TMDS eth0 = control port, 192.168.0.220
SK는 필요 시 UART control 사용
```

본 문서의 우선 경로:

```text
Path A: SK CPSW egress Qbv

SK eth1(CPSW sender / Qbv egress)
  -> TMDS eth2(ICSSG receiver)

Path B: TMDS ICSSG egress Qbv

TMDS eth2(ICSSG sender / Qbv egress)
  -> SK eth1(CPSW receiver)
```

주의:

```text
Path A와 Path B는 같은 물리 링크의 반대 방향 검증이다.
동시에 실행하지 말고 한 방향씩 수행한다.
```

---

## 5. Phase A0 - 공통 상태 점검 및 clean baseline

### 목적

Qbv endpoint 실험 전에 보드가 복잡한 switchdev/bridge 상태에 남아 있지 않은지 확인한다.

### SK에서 확인

```bash
hostname
uname -a
ip -br link
ip -br addr
ps -ef | grep -E "ptp4l|phc2sys" | grep -v grep || true

devlink dev param show platform/8000000.ethernet || true
bridge link || true
bridge -d vlan show || true

tc qdisc show dev eth0 || true
tc qdisc show dev eth1 || true
ethtool --show-priv-flags eth0 || true
ethtool --show-priv-flags eth1 || true
ethtool -T eth0
ethtool -T eth1
```

### TMDS에서 확인

```bash
hostname
uname -a
ip -br link
ip -br addr
ps -ef | grep -E "ptp4l|phc2sys" | grep -v grep || true

tc qdisc show dev eth1 || true
tc qdisc show dev eth2 || true
ethtool -i eth1
ethtool -i eth2
ethtool -T eth1
ethtool -T eth2
```

### Clean 상태로 정리

SK:

```bash
pkill ptp4l 2>/dev/null
pkill phc2sys 2>/dev/null

tc qdisc del dev eth0 root 2>/dev/null || true
tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth0 clsact 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true

ip link del br-tsn 2>/dev/null || true
devlink dev param set platform/8000000.ethernet name switch_mode value false cmode runtime 2>/dev/null || true

ip link set eth0 down
ip link set eth1 down
sleep 1
ip link set eth1 up
```

TMDS:

```bash
pkill ptp4l 2>/dev/null
pkill phc2sys 2>/dev/null

tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth2 root 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true
tc qdisc del dev eth2 clsact 2>/dev/null || true

ip link set eth1 down 2>/dev/null || true
ip link set eth2 down
sleep 1
ip link set eth2 up
```

### 성공 조건

```text
- SK switch_mode=false
- br-tsn 없음
- taprio/mqprio 잔여 qdisc 없음
- SK eth1 link up
- TMDS eth2 link up
```

---

## 6. Phase A1 - direct gPTP baseline 재확인

### 목적

Qbv를 적용하기 전에 direct endpoint 경로에서 gPTP가 안정적으로 lock 되는지 확인한다.

### 대상 경로

```text
SK eth1(CPSW) <-> TMDS eth2(ICSSG)
```

### gPTP config

양쪽에 생성:

```bash
cat > /tmp/gptp-endpoint-qbv.cfg <<'EOF'
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
tx_timestamp_timeout 100
EOF
```

### 실행

SK:

```bash
ptp4l -i eth1 -f /tmp/gptp-endpoint-qbv.cfg -m
```

TMDS:

```bash
ptp4l -i eth2 -f /tmp/gptp-endpoint-qbv.cfg -m
```

### 성공 조건

```text
- 한쪽 MASTER, 한쪽 SLAVE
- TMDS 또는 SK 중 slave가 UNCALIBRATED -> SLAVE 진입
- rms/freq/path delay 출력
- 최소 2~3분 stable
- tx timestamp timeout 없음
- FAULTY 없음
```

### 다음 단계 진입 조건

이 단계가 통과되어야 Qbv endpoint egress 검증을 진행한다.

---

## 7. Phase A2 - SK CPSW endpoint egress Qbv

### 목적

SK CPSW 포트가 endpoint sender로 동작할 때 taprio/Qbv gate schedule이 egress 송신 패턴을 제어하는지 확인한다.

### 경로

```text
SK eth1(CPSW sender / Qbv egress)
  -> TMDS eth2(ICSSG receiver)
```

### SK eth1 prerequisite

SK:

```bash
pkill ptp4l 2>/dev/null
pkill phc2sys 2>/dev/null

tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true
ip link del eth1.301 2>/dev/null || true

ip link set eth1 up
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off || true
ethtool --show-priv-flags eth1 || true
```

### TMDS receiver 설정

TMDS:

```bash
ip link del eth2.301 2>/dev/null || true
ip addr flush dev eth2
ip link set eth2 up

ip link add link eth2 name eth2.301 type vlan id 301
ip addr add 10.31.0.2/24 dev eth2.301
ip link set eth2.301 up

ip -br addr show eth2 eth2.301
```

### SK sender VLAN 및 PCP marking

SK:

```bash
ip link add link eth1 name eth1.301 type vlan id 301
ip link set eth1.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip addr add 10.31.0.1/24 dev eth1.301
ip link set eth1.301 up

# PCP 7 / PCP 6 marking
tc qdisc add dev eth1.301 clsact

tc filter add dev eth1.301 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff \
  action skbedit priority 7

tc filter add dev eth1.301 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff \
  action skbedit priority 6
```

### mqprio 적용

SK:

```bash
tc qdisc replace dev eth1 root handle 100: mqprio num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 hw 1 mode channel

tc -s qdisc show dev eth1
```

의도한 기본 매핑:

```text
priority 3 -> TC0
priority 2 -> TC1
priority 0/1/4/5/6/7 -> TC2
```

주의: 이 매핑은 초기 예제용이다. 실제 p7/p6를 서로 다른 TC로 분리하려면 map을 조정해야 한다. Phase A2의 첫 목적은 taprio 적용 가능성과 gate effect 관찰이므로, 필요하면 더 단순한 map으로 조정한다.

### taprio 적용성 확인

처음에는 너무 짧은 cycle을 쓰지 말고 관찰하기 쉬운 큰 cycle로 시작한다.

예: 100 ms cycle

```text
0~50 ms: TC2 open
50~100 ms: TC0/TC1 open
```

SK:

```bash
BASE=$(($(date +%s%N) + 5000000000))

tc qdisc replace dev eth1 parent root handle 200: taprio \
  num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 \
  base-time $BASE \
  sched-entry S 04 50000000 \
  sched-entry S 03 50000000 \
  flags 2
```

주의:

```text
- flags 2는 hardware offload를 의미하는 경우가 많다.
- 현재 kernel/driver에서 reject되면 dmesg를 확인한다.
- reject되면 flags 없이 software taprio 적용도 별도 기록한다.
```

상태 확인:

```bash
tc -s qdisc show dev eth1
dmesg | grep -iE "taprio|tas|est|cpsw|offload|mqprio" | tail -n 120
```

### Traffic 생성 및 관찰

TMDS:

```bash
iperf3 -s -D -p 5001
iperf3 -s -D -p 5002

tcpdump -i eth2 -e -ttt -n "vlan and udp"
```

SK:

```bash
iperf3 -c 10.31.0.2 -u -b 20M -t 20 -p 5001 || true
iperf3 -c 10.31.0.2 -u -b 20M -t 20 -p 5002 || true

tc -s filter show dev eth1.301 egress
tc -s qdisc show dev eth1
ethtool -S eth1 | grep -Ei "ale|drop|vlan|pri|prio|queue|fifo|tx|rx" || true
```

### 성공 조건

최소 성공:

```text
- taprio qdisc 적용 성공
- traffic이 계속 흐름
- receiver에서 VLAN PCP p7/p6 유지 확인
```

강한 성공:

```text
- taprio schedule 변경에 따라 receiver packet arrival pattern이 달라짐
- 특정 flow가 gate window에 맞춰 burst/지연/throughput 차이를 보임
```

---

## 8. Phase A3 - TMDS ICSSG endpoint egress Qbv

### 목적

TMDS eth2 ICSSG 포트가 endpoint sender로 동작할 때 Qbv/taprio egress scheduling이 가능한지 확인한다.

### 경로

```text
TMDS eth2(ICSSG sender / Qbv egress)
  -> SK eth1(CPSW receiver)
```

### 주의

ICSSG Linux driver의 taprio/Qbv offload 지원 범위는 CPSW와 다를 수 있다. 따라서 이 단계는 다음 두 가지를 분리해 기록한다.

```text
1. taprio qdisc 적용 자체가 가능한가?
2. hardware offload가 accepted 되는가?
```

### SK receiver 설정

SK:

```bash
pkill ptp4l 2>/dev/null
pkill phc2sys 2>/dev/null

tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true
ip link del eth1.302 2>/dev/null || true

ip addr flush dev eth1
ip link set eth1 up
ip link add link eth1 name eth1.302 type vlan id 302
ip addr add 10.32.0.2/24 dev eth1.302
ip link set eth1.302 up

ip -br addr show eth1 eth1.302
```

### TMDS eth2 sender 설정

TMDS:

```bash
tc qdisc del dev eth2 root 2>/dev/null || true
tc qdisc del dev eth2 clsact 2>/dev/null || true
ip link del eth2.302 2>/dev/null || true

ip addr flush dev eth2
ip link set eth2 up

ip link add link eth2 name eth2.302 type vlan id 302
ip link set eth2.302 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip addr add 10.32.0.1/24 dev eth2.302
ip link set eth2.302 up

tc qdisc add dev eth2.302 clsact

tc filter add dev eth2.302 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff \
  action skbedit priority 7

tc filter add dev eth2.302 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff \
  action skbedit priority 6
```

### TMDS eth2 taprio 적용 시도

TMDS:

```bash
BASE=$(($(date +%s%N) + 5000000000))

tc qdisc replace dev eth2 root handle 200: taprio \
  num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 \
  base-time $BASE \
  sched-entry S 04 50000000 \
  sched-entry S 03 50000000 \
  flags 2
```

결과 확인:

```bash
tc -s qdisc show dev eth2
dmesg | grep -iE "taprio|tas|est|icssg|prueth|offload|mqprio" | tail -n 120
```

만약 hardware offload가 reject되면, flags 없이 software taprio도 별도 시도하고 결과를 구분 기록한다.

```bash
tc qdisc replace dev eth2 root handle 200: taprio \
  num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 \
  base-time $BASE \
  sched-entry S 04 50000000 \
  sched-entry S 03 50000000
```

### Traffic 생성 및 관찰

SK:

```bash
iperf3 -s -D -p 5001
iperf3 -s -D -p 5002

tcpdump -i eth1 -e -ttt -n "vlan and udp"
```

TMDS:

```bash
iperf3 -c 10.32.0.2 -u -b 20M -t 20 -p 5001 || true
iperf3 -c 10.32.0.2 -u -b 20M -t 20 -p 5002 || true

tc -s filter show dev eth2.302 egress
tc -s qdisc show dev eth2
ethtool -S eth2 | grep -Ei "ale|drop|vlan|pri|prio|queue|fifo|tx|rx" || true
```

### 성공 조건

최소 성공:

```text
- taprio qdisc 적용 가능 여부 확인
- receiver에서 VLAN PCP p7/p6 유지 확인
```

강한 성공:

```text
- taprio schedule 변경에 따라 packet arrival pattern 변화 확인
```

실패도 중요한 결과:

```text
- ICSSG Linux driver에서 taprio hardware offload가 지원되지 않거나 제한될 수 있음
- 이 경우 TMDS ICSSG는 PCP-capable sender로는 사용하되, Qbv egress 검증 대상은 SK CPSW로 우선 제한한다.
```

---

## 9. Phase A4 - gPTP와 endpoint Qbv 공존 확인

### 목적

switch_mode=false direct endpoint 구조에서 gPTP lock 상태와 taprio/Qbv가 공존 가능한지 확인한다.

### 진행 순서

```text
1. direct gPTP stable lock 확보
2. gPTP 유지 상태에서 taprio 적용
3. ptp4l state가 계속 SLAVE인지 확인
4. Qbv traffic pattern 확인
```

### 판정

성공:

```text
switch_mode=false endpoint 환경에서
ptp4l SLAVE lock이 유지되고,
taprio schedule도 적용되며,
traffic pattern 변화가 관찰됨
```

실패:

```text
taprio 적용 직후 tx timestamp timeout / FAULTY / SLAVE 이탈 발생
```

이 경우는 switch_mode issue가 아니라 endpoint taprio/gPTP coexistence issue로 별도 분류한다.

---

## 10. 결과 보고서 형식

```md
# AM64x Qbv Endpoint Egress Validation

## 1. Purpose

## 2. Topology

## 3. Baseline State

## 4. Phase A1 direct gPTP Result

## 5. Phase A2 SK CPSW egress Qbv Result

### taprio apply result
### traffic result
### tcpdump evidence
### qdisc/counter evidence
### decision

## 6. Phase A3 TMDS ICSSG egress Qbv Result

### taprio apply result
### traffic result
### tcpdump evidence
### qdisc/counter evidence
### decision

## 7. Phase A4 gPTP + endpoint Qbv coexistence Result

## 8. Conclusion

Choose:

- SK CPSW endpoint Qbv works / not works
- TMDS ICSSG endpoint Qbv works / software-only / not supported
- gPTP + endpoint Qbv coexistence works / blocked

## 9. Next Action

- Continue endpoint Qbv refinement
- Revisit switch_mode gPTP issue in separate track
- Investigate MCU+ SDK TSN bridge path in separate track
```

---

## 11. Go / No-Go 기준

| Step | Go 조건 | No-Go 조건 |
|---|---|---|
| A0 | switch_mode=false clean 상태 확보 | qdisc/bridge/switchdev 잔여 제거 실패 |
| A1 | direct gPTP SLAVE stable | gPTP baseline 실패 |
| A2 | SK CPSW taprio 적용 및 traffic pattern 변화 | taprio reject 또는 traffic dead |
| A3 | TMDS ICSSG taprio 적용 가능성 확인 | ICSSG taprio unsupported로 판정 |
| A4 | gPTP lock 유지 + Qbv 동작 | taprio 적용 후 gPTP 이탈 |

---

## 12. 현재 판단

### Decision

`switch_mode=true` 기반 TSN switch 검증은 별도 이슈로 분리한다.

본 문서에서는 다음을 우선 검증한다.

```text
SK -> TMDS 단방향 Qbv egress
TMDS -> SK 단방향 Qbv egress
```

### Assumption

```text
switch_mode=false direct endpoint 환경에서는 gPTP baseline이 안정화 가능하다.
Qbv endpoint egress 기능은 switch_mode=true 없이도 검증 가능하다.
```

### Open Question

```text
SK CPSW taprio hardware offload가 현재 kernel/rootfs에서 accepted 되는가?
TMDS ICSSG taprio hardware offload가 지원되는가?
PTP/gPTP traffic이 taprio gate schedule에 의해 방해받지 않는가?
```

### Action Item

```text
1. 이 문서를 projects/tsn_qbv/docs/phaseA-endpoint-egress-qbv.md로 저장
2. Phase A0/A1로 clean direct gPTP baseline 재확인
3. Phase A2에서 SK CPSW endpoint egress Qbv 검증
4. Phase A3에서 TMDS ICSSG endpoint egress Qbv 가능성 확인
5. Phase A4에서 gPTP + endpoint Qbv 공존 확인
```
