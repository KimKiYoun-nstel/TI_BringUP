# P2 Qbv Control-Plane Replay 결과

## 결론

2026-07-24에 `SK eth0 -> TMDS eth1` CPSW direct path에서 P2-0 preflight, P2-T0
raw-HW timestamp qualification과 P2-G0 safe Qbv control-plane replay를 수행했다.

```text
P2-0 topology/runtime preflight: PASS
P2-T0 PTPv2 L2 TX/RX raw-HW sequence pairing: PASS
P2-G0 Qbv control replay: PASS
P2-G1 Qbv all-open latency pilot: INVALID (gPTP/probe TX timestamp coexistence)
QBV_1G_01 raw-HW timestamp/sequence-paired latency A/B: 미수행
```

이번 run은 `taprio flags 0x2`, PCP-to-TC mapping, critical/background queue hit, parent
device PCP capture, PTPv2 L2 packet별 TX/RX raw-HW sequence pairing을 재현했다. CPSW
receiver의 generic UDP RX raw-HW filter는 지원되지 않는다. PTP event 기반 pairing도
Qbv PCP 7/TC2와 same-port gPTP를 결합하면 TX timestamp coexistence failure가 발생하므로,
이 결과를 one-way latency, jitter, percentile 또는 Qbv latency improvement로 해석하지 않는다.

## P2-0: Topology와 Baseline

| 항목 | 관찰 |
|---|---|
| SK endpoint | `eth0`, CPSW `/dev/ptp0`, MAC `28:b5:e8:cc:2a:3f`, kernel `6.18.13-gc21449208550` |
| TMDS endpoint | `eth1`, CPSW `/dev/ptp0`, MAC `70:ff:76:20:22:99`, kernel `6.18.13-ti-00778-gc21449208550-dirty` |
| link | 양 endpoint 1 Gbps/full, carrier up |
| peer proof | temporary `198.18.3.1/30` and `198.18.3.2/30` ping 후 SK neighbor `70:ff:76:20:22:99`, TMDS neighbor `28:b5:e8:cc:2a:3f` |
| initial qdisc | 양 endpoint default `mq`/`pfifo_fast`, custom TSN qdisc 없음 |
| initial process | `ptp4l`, `phc2sys`, `iperf3`, `tcpdump` 없음 |

TMDS `eth1`은 reboot 직후 administratively down이었다. P2 baseline에 맞춰 `ip link set
eth1 up` 후 1 Gbps/full carrier를 확인했다. peer proof 직후 temporary IPv4와 neighbor
entry를 양 board에서 제거했다.

## P2-T0: Same-Path gPTP Health

SK `eth0`과 TMDS `eth1`에서 L2/P2P hardware `ptp4l -m -q -2 -P -H`를 실행했다.

```text
SK:   LISTENING -> MASTER
TMDS: LISTENING -> MASTER -> UNCALIBRATED -> SLAVE
```

TMDS steady sample은 offset 약 `-24~+10 ns`, path delay `424~425 ns`였다. 이 값은 P2
path에서 PHC synchronization health가 정상임을 보이지만, P1의 다른 physical path 결과나
packet latency timestamp를 대체하지 않는다.

## P2-G0: Safe Qbv Control Replay

### 적용 전제와 수정

첫 `taprio` apply는 SK `eth0`의 `p0-rx-ptype-rrobin` private flag가 on인 상태여서 아래
오류로 거절됐다.

```text
Error: ti_am65_cpsw_nuss: p0-rx-ptype-rrobin flag conflicts with taprio qdisc.
```

VLAN을 제거하고 SK `eth0`/`eth1`을 모두 down한 상태에서 TX queue를 3으로, private flag를
off로 변경한 뒤 재시도했다. 이 순서는 CPSW driver prerequisite이며 root qdisc가 이미
올라간 뒤 cycle을 바꾸는 절차와는 별개다.

### Qbv와 Traffic 조건

```text
sender: SK eth0.311 (10.33.0.1/24)
receiver: TMDS eth1.311 (10.33.0.2/24)

taprio flags 0x2
cycle: 500000 ns
window 0: 0x5 (TC0 + TC2), 125000 ns
window 1: 0x1 (TC0),       375000 ns

UDP/5001: 128 B, 1 Mbit/s, skb priority 3 -> VLAN PCP 7 -> TC2
UDP/5003: 1472 B, 100 Mbit/s, default priority -> VLAN PCP 0 -> TC0
duration: 15 s
```

TC0은 모든 window에서 열어 PTP control traffic을 gate-out하지 않았다. TMDS `ptp4l`은
traffic 중에도 `SLAVE`를 유지했고, trailing steady sample은 offset `-23~+10 ns`, path
delay `418~419 ns`였다. `FAULTY`, peer-delay TX timestamp timeout, sync loss는 관찰되지
않았다.

### Data-Plane 증적

| 증적 | 결과 |
|---|---|
| `taprio` | `flags 0x2`, 500 us, `0x5 -> 0x1` schedule 수용 |
| critical filter | `14,665` packet, `2,491,969` byte가 SK TC2 child qdisc에 기록 |
| background queue | `127,813` packet, `192,902,365` byte가 SK TC0 child qdisc에 기록 |
| critical receiver | iperf3 `0/14,650` loss, 1.00 Mbit/s receiver |
| background receiver | iperf3 `48/127,393` loss (`0.038%`), 99.9 Mbit/s receiver |
| TMDS parent pcap | UDP/5001은 VLAN 311 PCP 7, UDP/5003은 VLAN 311 PCP 0로 decode |

iperf3 receiver loss는 해당 15 s control replay의 UDP receiver statistic이다. P2의
application loss-free claim 또는 latency distribution 결과가 아니다.

## Raw Artifact

TMDS management SSH로 다음 raw evidence를 local artifact에 보관했고 checksum 대조를
완료했다. artifact directory는 Git 제외 대상이다.

```text
artifacts/p2-g0-2026-07-24/p2-g0-qbv.pcap          184 MiB
artifacts/p2-g0-2026-07-24/p2-g0-tmds-ptp.log      12 KiB
artifacts/p2-g0-2026-07-24/checksums.sha256
```

```text
8b09477bb35f506a86bf67ed967be4045e9bc6d10168f13e80a4e2e563cba141  p2-g0-qbv.pcap
1a063135adb60a0362244c79813c5bff2ac9fbee310e9aa5d60d21f3ea61e15f  p2-g0-tmds-ptp.log
```

## 종료 상태

양 board에서 `ptp4l`, `iperf3`, `tcpdump`를 종료하고 temporary VLAN 311/IP/filter/qdisc를
제거했다. SK `eth0` TX queue를 8로 복원하고 양 board의 data port는 up, IPv4 없음,
default `mq` qdisc, MAC Merge pMAC/TX/verify off 상태를 확인했다. `hwstamp_ctl -r 0 -t 0`으로
SK `eth0`과 TMDS `eth1`의 HWTSTAMP TX/RX filter도 off로 복귀했다. TMDS `/tmp/p2-*` source
logs/pcap도 local artifact checksum 확인 후 제거했다.

## P2-T0: PTPv2 L2 Raw-HW Timestamp Qualification

CPSW receiver의 generic UDP RX raw-HW 제약을 우회하기 위해, domain 127의 PTPv2 L2 Sync
event frame을 AF_PACKET `SO_TIMESTAMPING` probe로 전송했다. domain 127은 same-path
gPTP domain과 분리돼 control-plane state machine에 영향을 주지 않는다.

| 항목 | 결과 |
|---|---|
| TX endpoint | SK `eth0`, `ETH_P_1588`, TX HWTSTAMP on |
| RX endpoint | TMDS `eth1`, PTPv2 event RX HWTSTAMP filter |
| sequence | `40000..40031` |
| TX raw-HW | `32/32` |
| RX raw-HW | `32/32` |
| unique pairing | `32/32`, sender/receiver missing sequence 없음 |
| paired delta | min `424 ns`, p50 `426 ns`, p95 `428 ns`, max `428 ns` |
| gPTP health | TMDS `SLAVE`, custom frame window 전후 offset `-16~+12 ns`, path delay `422~423 ns`, failure signature 없음 |

raw sender/receiver CSV, paired CSV, gPTP log, summary와 checksum은 다음 local artifact에
보관했다.

```text
artifacts/p2-t0-2026-07-24/
```

`p2_ptp_l2_hwts_probe.py`는 packet format qualification용 최소 probe다. Qbv schedule,
VLAN PCP/TC mapping 또는 background contention을 자동으로 설정하지 않는다.

## P2-G1 Pilot: Invalid

VLAN 311 PCP 7/TC2와 background UDP를 결합한 첫 all-open pilot은 결과 데이터로 사용하지
않는다. pilot에서 다음 test-tooling 문제가 확인됐다.

1. sender AF_PACKET socket이 자기 multicast TX frame도 readable event로 받아 error queue의
   TX timestamp event와 혼동했고, timestamp를 기다리는 `recvmsg(MSG_ERRQUEUE)`가 timeout으로
   종료됐다.
2. receiver와 `iperf3` server를 background로 시작한 shell command의 grouping이 명확하지 않아
   receiver CSV가 생성되기 전에 run이 끝났다.
3. candidate PTP frame은 VLAN 포함 62 B였으므로 128 B critical traffic contract에 맞지 않았다.

probe에는 outgoing frame 무시, nonblocking error-queue retry 및 128 B frame-size option을 추가했다.
재시험은 receiver/server를 순차 시작하고 128 B frame을 명시한 뒤에만 수행한다. 이 pilot 중
적용했던 temporary VLAN, HWTSTAMP, Qbv qdisc와 processes는 모두 제거했고, 양 endpoint는
default `mq`, TX queue 8, IPv4 없음 상태로 복귀했다.

`0x7` all-TC gate mask는 CPSW taprio offload setup에서 거절됐다. P2가 사용하는 TC0/TC2만
열어 둔 `0x5` 500 us schedule은 수용됐으므로, A condition은 이를 relevant-traffic all-open
schedule로 사용한다. TC1은 이 case의 traffic class가 아니다.

수정 후 VLAN PCP 7/TC2 128 B probe는 all-open `0x5` schedule에서 TX/RX `raw_hw` 각각
`32/32`와 TC2 queue hit를 다시 확인했다. 그러나 same-path gPTP와 PCP 0 UDP 100 Mbit/s
background를 병행한 5분 A-condition pilot에서는 첫 critical frame부터 SK TX timestamp가
timeout되어 sender CSV를 만들지 못했다. 따라서 `QBV_1G_01`은 여전히 invalid이며, 이
contention 조건에서 CPSW TX hardware timestamp return이 끊기는 driver/queue interaction을
원인 분리한 뒤에만 재시작한다.

원인 분리 matrix에서는 all-open `0x5`, VLAN PCP 7/TC2, 128 B probe를 32 packet으로
고정했다. `gPTP-only`에서는 TMDS가 `SLAVE`인 상태에서 SK sender가 첫 TX timestamp를
받지 못해 timeout했다. 반대로 `background-only` UDP 100 Mbit/s에서는 TX/RX 모두
`raw_hw 32/32`였다. 따라서 현재 증거는 UDP contention이 아니라 same-port `ptp4l`과
custom PTP event probe의 TX timestamp coexistence가 blocker임을 가리킨다. 기존 P2-T0의
gPTP 병행 32-packet 결과와 차이가 나는 조건은 VLAN PCP 7/TC2 및 taprio가 적용된
현재 Qbv traffic path이며, 이 interaction을 별도 재현/driver 분석하기 전에는 P2 A/B
latency percentile을 산출하지 않는다.

## 다음 Gate

`QUALIFY_TIMESTAMP_1G_01`의 idle PTPv2 L2 event packet method는 통과했다. P2 A/B를
재개하려면 이 method가 VLAN PCP 7/TC2와 same-port gPTP를 결합해도 TX/RX raw-HW pairing을
유지하도록 CPSW TX timestamp coexistence blocker를 먼저 해소해야 한다.

각 조건은 최소 10회, 회당 5~10분을 실행하고 packet size, sequence format, offered/achieved
rate, CPU state, gPTP method, qdisc 외 traffic 설정을 고정한다. generic UDP one-way
latency가 별도 요구되면 CPSW path의 이 결과를 재사용하지 않고 ICSSG RX `FILTER_ALL` path
또는 external hardware timestamp measurement를 별도 qualification해야 한다.
