# 정량 측정 계획

## 공통 Gate

모든 performance case는 아래 조건을 통과해야 한다. 하나라도 실패하면 해당 run은
`invalid`이며 Qbv/Qbu 성능 비교에 포함하지 않는다.

| Gate | 통과 조건 | 실패 시 조치 |
|---|---|---|
| topology | cable pair, MAC address pair, carrier, speed, duplex, driver가 `config/topology.yaml` 및 case와 일치 | case 중단 |
| clean baseline | `shared-clean-v1` 확인, 기존 bridge/VLAN/qdisc/MAC Merge/test process 제거 | baseline 재적용 후 재확인 |
| artifact identity | image, DTB, rootfs hash, boot ID, kernel release 기록 | run 무효 |
| timestamp | chosen MAC path가 허용하는 packet type의 TX/RX raw-HW timestamp, sequence pairing, clock offset bound 확보 | latency case 중단 |
| generator | fixed size/rate/period, CPU affinity, scheduler policy, sender achieved rate 기록 | run 무효 |
| contention | background load와 queue/class hit가 관찰됨 | Qbv/Qbu 효과 비교 중단 |
| repeatability | 동일 조건 반복 run의 sample count와 invalid reason 보존 | 결론 보류 |

`shared-clean-v1`의 runtime 정리는
`projects/am64x-tsn-validation-automation/docs/runtime-baselines.md`를 사용한다. 이
프로젝트는 persistent rootfs profile을 수정하거나 복원하는 범위가 아니다.

## 단계별 최소 검증 세트

### Stage 0: 측정 성립성

| Test ID | Path | 목적 | PASS 조건 |
|---|---|---|---|
| `QUALIFY_TOPOLOGY_1G_01` | CPSW direct | port/MAC/PHC/link mapping 확정 | 양쪽 carrier, 1 Gbps/full, MAC pair proof, `ethtool -T` archive |
| `QUALIFY_TIMESTAMP_1G_01` | candidate path | packet별 timestamp method 검증 | selected packet type의 TX/RX raw-HW, unique sequence pairing, PHC offset bound, raw CSV 보존 |
| `QUALIFY_GENERATOR_1G_01` | CPSW direct | critical/background generator 정확도 검증 | achieved rate, period error, CPU affinity/load가 목표 범위 내 |

`QUALIFY_TIMESTAMP_1G_01` 또는 `QUALIFY_GENERATOR_1G_01`이 실패하면 해당 실패를
보드 불능으로 결론 내리지 않는다. hwtstamp 설정, receiver MAC block의 RX filter 지원 범위,
packet format, PHC 동기, generator achieved rate를 점검한 뒤 같은 Stage 0 case를 다시 수행한다.
현재 CPSW Linux RX filter는 PTP event에 제한되므로 일반 UDP one-way latency는 CPSW receiver
path에서 전제하지 않는다. 상세한 path 선택은 `workspace-sdk-cross-check.md`를 따른다.

### Stage 1: 조건 고정 Case 검증

| Test ID | 조건 | Traffic | 필수 증적 |
|---|---|---|---|
| `QBV_MULTICLASS_01` | HW taprio ON, TC2 500 us / TC1 250 us / TC0 250 us | PCP 2/TC2 periodic 128 B critical + PCP 0/TC0 background | schedule, TX/RX raw-HW count, TX phase, TC0 offered/received rate and drop, gPTP state |
| `QBU_1G_OPERATIONAL_01` | IET on traffic sweep, existing CPSW-to-CPSW line | TMDS sender: preemptible/express rate, frame-size, PPS condition matrix | activation probability, fragment/reassembly/error rate, per-flow rate/loss, active/inactive/intermittent region |
| `COMBO_1G_01` | Qbv vs Qbv+Qbu | critical periodic + saturating preemptible background | Qbv/Qbu state, gate violation, counter, raw paired timestamp, percentile |

각 case는 packet size, rate, period, duration, queue mapping, PHC source, CPU load,
CPU affinity, qdisc와 background profile를 manifest에 고정한다. `QBV_MULTICLASS_01`은
all-open control과 latency percentile을 비교하지 않는다. TC0 offered rate가 250 Mbit/s
allocation을 초과하고 queue drop이 발생한 상태에서 TC2 TX phase가 500 us window에 남는지를
판정한다. formal contract는 5 runs x 300 s이며 상세 criterion은
`p2-q3-multiclass-window-validation-plan-2026-07-28.md`를 따른다.
`QBU_1G_OPERATIONAL_01`은 P3 Qbu/IET operational envelope case이며 raw
timestamp/latency percentile case가 아니다. IET off는 golden profile의 negative control
1회이고, 주 결과는 IET on traffic sweep의 activation region이다. 상세 contract는
`p3-qbu-fragmentation-quantification-plan-2026-07-28.md`를 따른다.

### Stage 2: link speed 분리

100 Mbps와 1 Gbps는 합산하지 않는다. P3 `QBU_1G_OPERATIONAL_01`은 current CPSW-CPSW
cable pair에서 historical golden TMDS-sender direction을 기준으로 traffic-conditioned
activation region을 만든다. 100 Mbps SK-sender certificate와 Qbu latency case는 해당
speed/path의 traffic/timestamp gate를 별도로 통과한 뒤 독립 결과로 관리한다. 모든 run은
preflight로 cable pair와 CPSW endpoint를 다시 확정하며, 과거 결과만으로 고정하지 않는다.

## Run 데이터 계약

각 run directory는 다음 메타데이터와 raw data를 포함해야 한다. binary pcap, 긴 UART
capture, 대용량 raw sample은 Git에 넣지 않고 `artifacts/` 또는 별도 archive URI에 보관하며,
Git에는 manifest, checksum, summary, 해석만 남긴다.

```text
<run-id>/
  manifest.json             # Test ID, topology, artifact identity, tool versions
  preflight.json            # MAC pair, link, driver, PHC, ethtool -T
  ptp-health.json           # state, offset, path delay, clock uncertainty
  sender.csv                # sequence, TX raw-HW timestamp, traffic class
  receiver.csv              # sequence, RX raw-HW timestamp, traffic class
  paired.csv                # latency case에만: sequence, latency, validity reason
  qos-before.txt
  qos-after.txt
  counters-before.txt
  counters-after.txt
  generator.json            # requested/achieved rate, period error, CPU state
  summary.json              # case별 phase/rate/drop 또는 latency 통계
  checksums.sha256
```

`summary.json`에는 최소 `valid`, `invalid_reason`, `sample_count`, timestamp source와 case별
pass/fail metric을 넣는다. latency case의 percentile은 `valid=true`이며 paired sample count와
clock uncertainty가 사전 정의한 latency budget보다 충분히 작은 경우에만 성능 결론으로 해석한다.

## 중단 기준

- TX/RX raw-HW timestamp 중 하나라도 software timestamp로 대체됨
- PHC 관계 또는 offset bound가 기록되지 않음
- sequence pairing loss의 원인을 sender, wire, receiver 중 구분할 수 없음
- background contention, Qbv queue hit, Qbu fragment가 실제로 발생하지 않음
- case contract의 packet size, rate, period, duration, CPU state, qdisc가 달라짐
- receiver application 또는 host capture가 병목으로 판단됨
- 반복 run의 분산 또는 timestamp uncertainty가 기대 개선량보다 큼

중단한 run도 삭제하지 않는다. manifest와 invalid reason을 보존하고, 가능한 관찰 범위를
Qbv control/phase 또는 Qbu counter 수준으로 명확히 낮춰 기록한다.
