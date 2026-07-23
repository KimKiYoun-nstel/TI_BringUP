# P2 Qbv 정량 검증 준비 상태

## 목적과 범위

P2 `QBV_1G_01`은 `SK eth0 -> TMDS eth1` CPSW direct path에서 Qbv all-open/off와
hardware `taprio` on을 같은 traffic 조건으로 비교하는 시험이다. P1의 gPTP load 시험은
`SK eth1 -> TMDS eth2` CPSW-to-ICSSG path에서 수행했으므로, P1 결과만으로 P2의
timestamp 또는 latency gate가 충족됐다고 간주하지 않는다.

```text
P2 path: SK eth0 (CPSW, /dev/ptp0) -> TMDS eth1 (CPSW, /dev/ptp0)
P2 traffic: PCP 7 periodic 128 B critical + PCP 0 1500 B background
comparison: all-open/off vs hardware taprio on
```

P2는 다음 두 질문을 분리한다.

1. Qbv schedule이 CPSW egress에서 실제 traffic의 gate/burst behavior를 바꾸는가?
2. 그 변화의 packet별 TX/RX raw-HW timestamp와 sequence pairing을 확보해 latency
   percentile로 비교할 수 있는가?

첫 번째 질문의 기존 증적은 있으나, 두 번째 질문은 아직 통과하지 않았다. 따라서 현재
P2는 **latency A/B 실행 전 timestamp qualification 준비 단계**다.

## 확정된 시작점

| 항목 | 증적 | 해석 |
|---|---|---|
| physical path | SK `eth0` MAC `28:b5:e8:cc:2a:3f` <-> TMDS `eth1` MAC `70:ff:76:20:22:99` | P2 reference cable pair |
| MAC/PHC | 양 endpoint CPSW, `/dev/ptp0` | 서로 다른 board의 PHC이므로 gPTP residual bound가 여전히 필요 |
| hardware Qbv | SK `eth0`에서 `taprio flags 0x2`, 500 us schedule 수용 | hardware offload functional evidence |
| class delivery | TMDS capture에서 VLAN 311 PCP 7/6 관찰 | PCP mapping/wire delivery functional evidence |
| timing control | 500 us/8 ms cycle-correlated single-flow burst, gate-close stress, safe schedule gPTP coexistence | P2 control-plane reference로 재현 가능 |
| P1 load result | 800 Mbit/s gPTP PASS는 `SK eth1 -> TMDS eth2` path | P2 link의 load/PHC bound로 재사용 금지 |

기존 Qbv functional run의 500 us schedule은 다음과 같다. 이는 hardware offload와 PCP
delivery를 확인한 reference이며, same-port gPTP timebase를 유지하는 P2 latency run의
schedule로 그대로 사용하지 않는다.

```text
TC2: 0x4, 125000 ns
TC1: 0x2, 125000 ns
TC0: 0x1, 250000 ns
cycle: 500000 ns
```

P2에서 internal priority와 wire PCP를 혼동하지 않는다. 과거 direct timing run에서는
`5001 -> skbedit priority 3`, `5002 -> skbedit priority 2` 및 VLAN egress map
`3:7`, `2:6` 조합이 `taprio map`의 TC2/TC1과 일관됐다. 기존 automation의 priority
`7/6` functional setting을 그대로 timing case에 복사하지 않는다.

P2에서 `ptp4l`로 same-path PHC bound를 수집하는 경우에는 PTP control class를 닫지 않는다.
TC0이 항상 열린 safe schedule(예: p7/TC2가 필요한 구간에는 `0x5`, 나머지 구간에는
`0x1`)로 별도 control run을 먼저 통과시킨다. PTP frame의 실제 traffic-class mapping과
`ptp4l` state를 증적 없이 추정하지 않는다.

## 현재 Blocker

| Gate | 상태 | 근거와 조치 |
|---|---|---|
| current topology/runtime | 재확인 필요 | TMDS console은 현재 login prompt였고, 새 P2 run 전에 carrier, speed, duplex, peer MAC, baseline을 읽기 전용으로 다시 기록해야 한다. |
| same-path gPTP bound | 재수집 필요 | P1의 ICSSG path bound는 CPSW direct P2 path의 PHC relation을 보장하지 않는다. P2 path에서 L2/P2P hardware `ptp4l`을 실행해 state, offset, path delay, uncertainty bound를 같은 run에 남긴다. |
| generic UDP RX raw-HW | 불가 | CPSW Linux RX HWTSTAMP filter는 PTP V1/V2 event만 수용한다. TMDS `eth1`에서 generic UDP RX raw-HW latency를 전제하지 않는다. |
| sender raw-HW | 미확보 | 기존 `tx_hwts_probe.py`는 socket timestamp path를 열었지만 `raw_hw`/`hw`가 아닌 `sw`만 받았다. software timestamp를 PHC domain으로 환산해 latency/gate phase 증거로 사용하지 않는다. |
| measurement tool provenance | 미확정 | `plget`은 workspace에 source/binary가 없다. source revision, build method, binary hash와 requested/returned HWTSTAMP configuration을 확보하기 전에는 P2 도구로 사용하지 않는다. |
| sequence pairing | 미구현 | sender/receiver의 unique sequence, packet type, TX/RX raw-HW timestamp, pairing loss reason을 raw CSV로 남기는 경로가 없다. |

이 blocker는 Qbv hardware 불능 판정이 아니다. 현재 Linux CPSW driver의 RX filter와
user-space measurement path가 P2 latency contract를 아직 만족하지 않는다는 뜻이다.

## P2 실행 전 Qualification 순서

### P2-0: 읽기 전용 preflight

`shared-clean-v1`를 확인한 뒤 아래 증적을 P2 run directory의 `preflight.json`과 text
capture에 보존한다. preflight가 다르면 run을 시작하지 않는다.

```text
SK:   ip -br link; ip -br addr; ethtool eth0; ethtool -i eth0; ethtool -T eth0
TMDS: ip -br link; ip -br addr; ethtool eth1; ethtool -i eth1; ethtool -T eth1
both: /sys/class/net/<if>/device/ptp mapping, ethtool -l, tc qdisc show,
      ethtool --show-mm, CPU governor, relevant ethtool -S counters
```

ARP source-MAC proof, carrier, 1 Gbps/full, current kernel/image identity, boot ID, driver와
PHC mapping이 `config/topology.yaml`의 P2 path와 일치해야 한다. HWTSTAMP filter는
`hwstamp_ctl` read-only query가 없으므로, P2-T0에서 requested/returned setting과
cleanup command를 같은 record에 남긴다.

### P2-T0: timestamp method 결정

이 단계의 목적은 latency case를 시작하는 것이 아니라, 어떤 packet type과 collection
method가 raw-HW pairing contract를 만족하는지 결정하는 것이다.

1. CPSW receiver의 generic UDP RX raw-HW를 다시 요구하지 않는다.
2. CPSW direct path를 유지하려면 PTP event frame 기반의 sender/receiver collection method를
   선정하고, TX/RX 모두 `raw_hw`임을 packet별로 확인한다.
3. PTP event frame으로 Qbv critical traffic을 표현할 수 없거나 raw-HW pairing이 성립하지
   않으면, P2 latency A/B는 `invalid`로 기록하고 종료한다.
4. 일반 UDP critical traffic의 one-way latency가 목표이면 ICSSG RX `FILTER_ALL` path 또는
   external hardware timestamp measurement를 별도 topology/qualification case로 선택한다.

P2-T0 PASS 조건은 아래 모두다.

```text
selected packet type declared
TX raw-HW timestamp per packet
RX raw-HW timestamp per packet
unique sequence pairing
paired CSV and unpaired reason preserved
same-run gPTP offset/uncertainty bound preserved
```

한 항목이라도 software timestamp이면 `QBV_1G_01` latency/percentile claim을 하지 않는다.
기능 gate conformance evidence는 보존할 수 있으나, `valid=true` latency result로 기록하지
않는다.

### P2-G0: Qbv control-plane replay

P2-T0과 독립적으로, known-good CPSW direct Qbv control behavior를 먼저 재현한다. 이 run은
latency 측정 대체물이 아니다.

1. 500 us schedule을 `taprio flags 0x2`로 적용하고 configured/operational qdisc를 보존한다.
   same-path `ptp4l`을 병행하면 TC0 always-open safe schedule을 사용하고 PTP state/error log를
   함께 보존한다.
2. PCP/TC mapping과 VLAN egress map을 보존하고, parent device capture로 wire PCP를 확인한다.
3. critical periodic flow와 PCP 0 background flow의 requested/achieved rate, packet size,
   period, CPU affinity, scheduler policy를 기록한다.
4. queue/filter/qdisc/counter before/after 및 taprio/EST-related dmesg delta를 보존한다.
5. schedule cycle을 변경할 때는 CPSW EST 제한에 따라 `tc qdisc del dev eth0 root` 후
   `tc qdisc add ... taprio`를 사용한다. live `replace`로 cycle을 바꾸지 않는다.

P2-G0은 `flags 0x2`, expected schedule, wire PCP, class hit, background contention이
확인되면 control-plane PASS다. raw-HW pairing이 없으면 latency/percentile PASS가 아니다.

### P2-G1: valid A/B matrix

P2-T0과 P2-G0 모두 통과한 뒤에만 아래 matrix를 수행한다.

| Condition | Qbv | Traffic | 반복 |
|---|---|---|---|
| A | all-open/off | PCP 7 periodic 128 B critical + PCP 0 1500 B background | 최소 10회, 회당 5~10분 |
| B | hardware taprio on | A와 동일 | 최소 10회, 회당 5~10분 |

두 조건은 packet type, sequence format, size, period, duration, offered/achieved rate, CPU
state, gPTP method, qdisc 외 traffic setting을 동일하게 유지한다. 각 run은
`manifest.json`, `preflight.json`, `ptp-health.json`, `sender.csv`, `receiver.csv`,
`paired.csv`, qdisc/counter before/after, `generator.json`, `summary.json`, checksum manifest를
가져야 한다.

## 안전한 종료와 판정

- run 종료 시 `ptp4l`, traffic process, capture process, temporary VLAN/IP/qdisc를 제거하고
  `shared-clean-v1`을 재확인한다.
- HWTSTAMP를 설정했다면 requested/returned setting과 `hwstamp_ctl -r 0 -t 0` cleanup 결과를
  남긴다.
- failed/invalid run도 삭제하지 않는다. timestamp source, pairing loss, PHC bound 또는
  contention 부족 중 어느 gate가 실패했는지 `invalid_reason`에 기록한다.
- P2 control-plane replay의 성공은 Qbv offload/gate behavior evidence다. raw-HW pairing 없는
  결과를 one-way latency, jitter, p99/p99.9, Qbv latency improvement로 해석하지 않는다.

## 준비 완료 판정

현재 준비 작업은 P2의 path, baseline, known-good taprio setting, mapping correction, data
contract와 stop rule을 고정했다. 다음 live 작업은 **P2-0 읽기 전용 preflight**다. P2-T0에서
valid raw-HW pairing method가 확정되기 전에는 P2-G0을 넘는 latency A/B traffic run을 시작하지
않는다.

## 관련 문서

- `docs/measurement-plan.md`: 공통 gate, run data contract, invalid 기준
- `docs/workspace-sdk-cross-check.md`: CPSW HWTSTAMP driver 제약과 P2 위치
- `docs/p1-gptp-load-validation-2026-07-23.md`: 별도 CPSW-to-ICSSG P1 load 결과
- `projects/am64x-tsn-validation-automation/docs/2026-07-14_first-automated-validation.md`: Qbv functional baseline
- `projects/tsn_qbv/docs/2026-06-30_phaseB-endpoint-egress-qbv-timing-validation-progress.md`: mapping correction과 과거 timing-observability 한계
