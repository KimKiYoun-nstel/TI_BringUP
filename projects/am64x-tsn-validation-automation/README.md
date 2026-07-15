# AM64x TSN Validation Automation

이 문서는 `SK-AM64B`와 `TMDS64EVM`에서 UART-only automation이 실제로 수행하는
설정, traffic 시험, 증적 수집, PASS/FAIL 판정을 정의하는 **프로젝트 대표 운용 문서**다.

runner 구현의 source of truth는 `board/tsn_validate.py`다. 이 문서는 그 구현을 사람이
검토하고 동일한 시험을 해석할 수 있도록 설명한다.

## 시험 대상과 물리 배선

```text
SK eth0  <-> TMDS eth1   CPSW <-> CPSW, Qbv/Qbu D1
SK eth1  <-> TMDS eth2   CPSW <-> ICSSG, gPTP/DSCP-PCP ingress
```

제어 경로는 두 보드의 UART daemon `sk`, `tmds`다. TMDS SSH 또는 management Ethernet은
필수 조건이 아니다.

`preflight`는 아래를 모두 만족해야 한다.

1. SK `eth0`, `eth1`, TMDS `eth1`, `eth2`의 1 Gbps/full carrier
2. SK `eth0` source MAC ARP probe가 TMDS `eth1`에서 수신됨
3. SK `eth1` source MAC ARP probe가 TMDS `eth2`에서 수신됨

carrier만으로 peer port를 추정하지 않는다. ARP source-MAC pair proof 실패는 physical
topology invalid이며 모든 기능 시험을 중단한다.

```bash
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py preflight
```

data port가 administratively down이면 아래처럼 carrier 확인 전에만 올릴 수 있다.

```bash
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py \
  preflight --bring-up-links
```

## 공통 Baseline

모든 기능은 `shared-clean-v1`에서 시작하고, 성공 또는 실패 후 동일 baseline으로 복귀한다.
자동화는 임의의 기존 runtime을 snapshot/restore하지 않는다. 기존 TSN 상태를 보존해야 하는
세션에는 실행하면 안 된다.

| 항목 | SK | TMDS |
|---|---|---|
| data port IP | `eth0`, `eth1` 없음 | `eth1`, `eth2` 없음 |
| bridge/netns | `br-tsn` 없음 | `ep1`, `ep2` 없음 |
| switch/QoS | `switch_mode=false`, custom qdisc 없음 | custom qdisc 없음 |
| MAC Merge | CPSW ports pMAC/TX/verify off | `eth1` pMAC/TX/verify off |
| TX queue | CPSW `8` | TMDS `eth1` `8` |
| test process | `ptp4l`, `phc2sys`, `iperf3` 없음 | 전항목 및 `tcpdump` 없음 |

TMDS `eth2` ICSSG의 idle `pMAC enabled: on`은 driver baseline으로 허용한다.

```bash
# 상태를 바꾸지 않고 baseline 적합성만 확인
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py baseline check

# 명시적으로 baseline 적용: bridge/VLAN/qdisc/netns/MM/test process 제거
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py \
  baseline apply --execute
```

`run <feature> --execute`는 preflight와 baseline check를 통과한 경우에만 stateful test를
시작한다. 종료 cleanup도 baseline check까지 다시 통과해야 한다.

## 실행 순서

```bash
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py baseline check
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py --runtime-sec 20 run gptp --execute
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py --runtime-sec 6 run dscp-pcp --execute
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py --runtime-sec 6 run qbv --execute
python3 projects/am64x-tsn-validation-automation/board/tsn_validate.py --runtime-sec 30 run qbu --execute
```

`--runtime-sec`은 gPTP observation 또는 iperf traffic duration이다. Qbu는 packet overlap을
만들기 위해 30 seconds를 기준으로 사용한다.

## gPTP 검증

### 경로와 설정

```text
SK eth1 (CPSW /dev/ptp0) <-> TMDS eth2 (ICSSG /dev/ptp2)
```

양 보드는 다음 `/tmp/tsn-auto-gptp.cfg`를 생성하고 `ptp4l -m`을 background로 실행한다.

```ini
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
```

```bash
# SK
ptp4l -i eth1 -f /tmp/tsn-auto-gptp.cfg -m

# TMDS
ptp4l -i eth2 -f /tmp/tsn-auto-gptp.cfg -m
```

runner는 지정 시간 후 양 log를 수집하고 process를 종료한다. PHC epoch 보정과 `phc2sys`는
자동으로 수행하지 않는다.

### PASS 기준

TMDS log에 아래 전이가 있어야 한다.

```text
MASTER -> UNCALIBRATED -> SLAVE
```

`result.json`의 `evidence.tmds_slave=true`가 PASS 조건이다. delay/RMS 안정화는
`tmds-ptp.log`에서 추가 확인한다.

### 범위 제외

- `CLOCK_REALTIME` discipline (`phc2sys`)
- SK switchdev를 경유하는 gPTP
- external PPS/perout 측정

## DSCP/PCP Preservation 검증

### 경로와 traffic class

```text
TMDS ep2 / eth2.301 / 10.31.0.1
  -> SK eth1 ingress -> br-tsn switchdev -> SK eth0 egress
  -> TMDS ep1 / eth1.301 / 10.31.0.2
```

| UDP port | sender skb priority | intended VLAN PCP |
|---|---:|---:|
| `5001` | 7 | 7 |
| `5002` | 6 | 6 |

### board 설정 sequence

SK는 다음 상태로 전환한다.

```bash
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
devlink dev param set platform/8000000.ethernet \
  name switch_mode value true cmode runtime
ip link add br-tsn type bridge
ip link set eth0 up
ip link set eth1 up
ip link set eth0 master br-tsn
ip link set eth1 master br-tsn
ip link set br-tsn up
ip link set br-tsn type bridge vlan_filtering 1
bridge vlan add dev br-tsn vid 1 pvid untagged self
bridge vlan add dev eth0 vid 301 master
bridge vlan add dev eth1 vid 301 master
bridge vlan add dev br-tsn vid 301 self
tc qdisc replace dev eth0 root handle 100: mqprio ... hw 1 mode channel
tc qdisc replace dev eth1 root handle 100: mqprio ... hw 1 mode channel
```

TMDS는 `ep1`/`ep2` namespace를 만들고 `eth1`/`eth2`를 각각 이동한다. `eth2.301`에
VLAN egress map `0:0 ... 7:7`을 적용하고, egress `clsact` filter로 UDP 5001/5002를
priority 7/6으로 mark한다. `ep1`에는 두 `iperf3` server를 실행한다.

```bash
ip netns exec ep2 iperf3 -c 10.31.0.2 -u -b 20M -t <runtime-sec> -p 5001
ip netns exec ep2 iperf3 -c 10.31.0.2 -u -b 20M -t <runtime-sec> -p 5002
```

receiver parent port `ep1/eth1`에서 `vlan and udp` pcap을 수집한다. VLAN subinterface
`eth1.301`는 outer VLAN header를 제거하므로 PCP wire 판정 capture point로 사용하지 않는다.

### PASS 기준

pcap decode에서 아래 두 frame이 각각 있어야 한다.

```text
vlan 301, p 7 ... > 10.31.0.2.5001
vlan 301, p 6 ... > 10.31.0.2.5002
```

`result.json`의 `evidence.pcp7=true` 및 `evidence.pcp6=true`가 동시에 필요하다. SK local
tcpdump가 비어 있는 것은 hardware-offloaded forwarding의 알려진 관측 한계로 단독 FAIL이 아니다.

## Qbv Phase A Hardware Egress 검증

### 경로와 traffic class

```text
SK eth0.311 / 10.33.0.1 (CPSW sender)
  -> TMDS eth1.311 / 10.33.0.2 (CPSW receiver)
```

UDP 5001은 PCP 7, UDP 5002는 PCP 6으로 mark한다. VLAN interface가 up된 뒤 networkd가
link-local address를 다시 넣을 수 있으므로 runner는 settle 후 test IP를 `flush`/`add`한다.

### SK sender 설정

```bash
ip link set eth1 down
ip link set eth0 down
ethtool -L eth0 tx 3
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ip link set eth0 up
sleep 5                         # PHY carrier settle
ip link add link eth0 name eth0.311 type vlan id 311
ip link set eth0.311 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip link set eth0.311 up
sleep 2
ip addr flush dev eth0.311
ip addr add 10.33.0.1/24 dev eth0.311
tc qdisc add dev eth0.311 clsact
tc filter add dev eth0.311 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff action skbedit priority 7
tc filter add dev eth0.311 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff action skbedit priority 6
```

TI reference minimum EST schedule을 hardware offload로 적용한다.

```bash
tc qdisc replace dev eth0 parent root handle 100: taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 125000 \
  sched-entry S 02 125000 \
  sched-entry S 01 250000 \
  flags 2
```

TMDS receiver는 다음처럼 VLAN link settle 후 `eth1.311`에 test IP, port 5001/5002
`iperf3` server, parent `eth1` pcap capture를 준비한다.

```bash
ip link set eth1 up
ip link add link eth1 name eth1.311 type vlan id 311
ip link set eth1.311 up
sleep 5
ip addr flush dev eth1.311
ip addr add 10.33.0.2/24 dev eth1.311
iperf3 -s -D -B 10.33.0.2 -p 5001
iperf3 -s -D -B 10.33.0.2 -p 5002
tcpdump -i eth1 -w /tmp/tsn-auto-qbv.pcap 'vlan and udp' &
```

sender는 각각 20 Mbps UDP flow를 전송한다.

### PASS 기준

`tc -s qdisc show dev eth0`에 다음이 있어야 한다.

```text
qdisc taprio
flags 0x2
cycle-time 500000
```

TMDS capture에서 다음을 모두 관측해야 한다.

```text
vlan 311, p 7 ... > 10.33.0.2.5001
vlan 311, p 6 ... > 10.33.0.2.5002
```

이는 direct endpoint hardware Qbv egress PASS다. closed-gate timing strong proof,
future base-time phase, hardware Qbv + gPTP coexistence는 이 runner의 PASS 주장에 포함하지 않는다.

## Qbu D1 Actual Frame Preemption 검증

### 경로와 traffic class

```text
TMDS eth1 / 192.168.107.30 (CPSW sender)
  -> SK eth0 / 192.168.107.20 (CPSW receiver)
```

| UDP port | class | offered traffic |
|---|---|---:|
| `5002` | TC2 preemptible | 200 Mbps, 1472-byte UDP |
| `5003` | TC3 express | 50 Mbps, 1472-byte UDP |

### receiver와 sender 설정

SK receiver와 TMDS sender 모두 sibling CPSW port를 down한 뒤 target port를 TX queue 4로
전환한다. MAC Merge는 verify-on으로 설정하고 link-up 뒤 8초를 기다린다.

```bash
# SK receiver eth0
ip link set eth1 down
ip link set eth0 down
ethtool -L eth0 tx 4
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ethtool --set-mm eth0 pmac-enabled on tx-enabled on verify-enabled on \
  verify-time 10 tx-min-frag-size 124
ip link set eth0 up
sleep 8
ip addr add 192.168.107.20/24 dev eth0

# TMDS sender eth1
ip link set eth0 down
ip link set eth1 down
ethtool -L eth1 tx 4
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
ethtool --set-mm eth1 pmac-enabled on tx-enabled on verify-enabled on \
  verify-time 10 tx-min-frag-size 124
ip link set eth1 up
sleep 8
ip addr add 192.168.107.30/24 dev eth1
```

TMDS sender는 frame-preemption class를 포함한 `mqprio`와 egress filter를 설치한다.

```bash
tc qdisc replace dev eth1 handle 100: root mqprio \
  num_tc 4 map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 \
  queues 1@0 1@1 1@2 1@3 hw 1 mode dcb fp P P P E
tc qdisc replace dev eth1 clsact
tc filter add dev eth1 egress protocol ip prio 1 u32 \
  match ip dport 5002 0xffff action skbedit priority 2
tc filter add dev eth1 egress protocol ip prio 2 u32 \
  match ip dport 5003 0xffff action skbedit priority 3
```

SK는 port 5002/5003 `iperf3` server를 실행한다. TMDS에서는 두 UDP flow를 동시에 30초
전송한다. traffic 전후 양쪽 `ethtool -S`와 `ethtool --include-statistics --show-mm`을
수집한다.

```bash
iperf3 -c 192.168.107.20 -u -b200M -l1472 -t30 -p5002 &
iperf3 -c 192.168.107.20 -u -b50M  -l1472 -t30 -p5003 &
wait
```

### PASS 기준

같은 traffic window에서 아래를 모두 만족해야 한다.

```text
TMDS eth1: TX active: on
TMDS eth1: Verification status: SUCCEEDED
TMDS eth1: MACMergeFragCountTx 또는 iet_tx_frag delta > 0
SK eth0:   MACMergeFrameAssOkCount 또는 iet_rx_assembly_ok delta > 0
```

MAC Merge set command, `mqprio` 수용, filter counter 증가만으로는 PASS가 아니다. sender
fragment와 receiver reassembly의 positive counter delta가 actual Qbu dataplane 증거다.

## 증적, 결과 해석, 종료 상태

각 실행은 아래 경로에 보관된다.

```text
logs/YYYYMMDD-HHMMSS-<feature>/
  result.json
  preflight-*.txt
  baseline-*.txt
  command-<target>-<step>.json
  *-ptp.log | *-capture.txt | *-qdisc.txt | *-stats-before.txt | *-stats-after.txt
```

`result.json`을 우선 확인한다.

```json
{
  "feature": "qbu",
  "pass": true,
  "topology": { "pairs": { "sk-eth0__tmds-eth1": true } },
  "baseline": { "...": "test start state" },
  "evidence": { "...": "feature-specific pass evidence" },
  "restored_baseline": { "...": "test end state" }
}
```

- `pass=false`와 `error`가 있으면 setup/traffic/transport 단계가 실패한 것이다. 해당
  `command-*.json`의 `output`과 raw evidence를 확인한다.
- `pass=false`인데 error가 없으면 기능 evidence가 PASS 기준에 도달하지 못한 것이다.
- `restored_baseline`이 없거나 cleanup error면 run은 invalid다. 다음 test 전에
  `baseline apply --execute`를 수행한다.

모든 target script는 board shell exit status marker를 반환한다. UART request의 전송 성공만으로
board command 성공으로 간주하지 않는다. 대용량 pcap text를 UART로 전송하지 않고 target
`/tmp` pcap에서 UDP port별 최소 증적만 decode한다.

## 안전성 및 범위

- persistent rootfs network file과 systemd enable state는 runner가 변경하지 않는다.
- Qbu 실행 전 DSCP/PCP auto-apply rootfs profile이 남아 있으면 기존 Qbu clean baseline overlay를
  배포하고 reboot해야 한다.
- test가 시작된 뒤 성공/실패와 무관하게 shared-clean-v1 cleanup을 수행한다.
- 실제 UART 전체 증적의 기준은 계속 `logs/runtime_log`다. project `logs/`는 run별 추출 증적이다.

추가 계약 문서:

- [runtime baseline](docs/runtime-baselines.md)
- [pass/fail matrix](docs/test-matrix.md)
- [첫 실보드 자동 실행 결과](docs/2026-07-14_first-automated-validation.md)
