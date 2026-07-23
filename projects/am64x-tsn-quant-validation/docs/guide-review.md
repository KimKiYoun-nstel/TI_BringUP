# 정량 검증 가이드 검토

## 결론

`AM64x_TSN_정량_검증_가이드.md`의 핵심 요구인 packet별 TX/RX hardware timestamp,
동기화된 시간축, sequence matching은 현재 repo 자산에서 end-to-end로 직접 검증되지
않았다. 이것은 보드 불능 판정이 아니다. 현재 환경은 TSN 기능 동작과 일부 dataplane
counter를 확인했으며, one-way latency, jitter, p95/p99/p99.9/max 또는 Qbv/Qbu
tail-latency 개선을 위한 수동 측정 경로는 아직 완결 시험하지 않은 상태다.

첫 수동 시험은 `QUALIFY_TIMESTAMP_1G_01`로 측정 경로를 확인한다. 이 시험이
실패하면 보드 불능으로 결론 내리지 않고 hwtstamp 설정, socket timestamp 경로,
RX 수집, PHC 동기 상태를 확인한 뒤 같은 시험을 다시 수행한다.

## 가이드 요구사항 대비 판정

| 가이드 항목 | 현재 상태 | 근거 | 판정 |
|---|---|---|---|
| 물리 topology와 netdev 식별 | 확인 | SK `eth0`-TMDS `eth1`은 CPSW direct, SK `eth1`-TMDS `eth2`는 CPSW-ICSSG direct | 가능 |
| link speed 및 MAC/PHC mapping | 부분 확인 | 모두 1 Gbps/full 관찰, CPSW는 `/dev/ptp0`, TMDS ICSSG는 `/dev/ptp2` | run마다 재확인 필요 |
| gPTP lock | 부분 확인 | SK `eth1`-TMDS `eth2`에서 TMDS SLAVE 및 약 439~440 ns path delay 관찰 | link별 lock/offset bound 필요 |
| TX HW timestamp request | 부분 시험 | SK `eth0` probe가 raw-HW를 요청했으나 software timestamp만 수신. probe에는 interface hwtstamp 설정 ioctl이 없음 | 동일 path에서 hwtstamp 설정을 포함한 수동 재시험 필요 |
| RX HW timestamp capture | 직접 시험 미수행 | 기존 기능 검증 절차는 `tcpdump` capture만 사용 | 수동 RX timestamp 수집 시험 필요 |
| TX/RX sequence pairing | 직접 시험 미수행 | iperf3/tcpdump 증적에는 packet-level pairing format 없음 | sequence payload와 대응 기록 시험 필요 |
| deterministic critical traffic | 직접 시험 미수행 | iperf3는 throughput/loss generator이며 period, scheduler jitter, CPU affinity가 고정되지 않음 | 수동 traffic profile 및 achieved rate 확인 필요 |
| Qbv offload | 확인 | CPSW direct reference에서 `taprio` hardware `flags 0x2`, 500 us schedule 확인 | 제한적 측정 가능 |
| Qbu actual overlap | 확인 | TMDS `eth1 ->` SK `eth0`에서 TX fragment와 RX reassembly가 같은 window에 증가 | counter 관찰 가능 |
| 동일 조건 A/B 반복 | 미구현 | traffic, CPU, timestamp method, raw data contract가 case별로 고정되지 않음 | 추가 구현 필요 |

## 현재 근거

- 기존 기능 검증과 actual run 결과: `projects/am64x-tsn-validation-automation/README.md`, `docs/2026-07-14_first-automated-validation.md`
- runtime clean baseline: `projects/am64x-tsn-validation-automation/docs/runtime-baselines.md`
- port driver, PHC, hardware timestamp capability advertisement: `projects/tsn_dscp_pcp/docs/results.md`
- Qbv packet timestamp 및 phase proof의 미해결 사항: `projects/tsn_qbv/docs/2026-06-30_phaseB-endpoint-egress-qbv-timing-validation-progress.md`
- Qbu fragment/reassembly과 generator overlap 제약: `projects/tsn_qbu/docs/VALIDATION_STATUS.md`

`ethtool -T`의 capability 표시, `ptp4l` 동기화, `tc` 성공, `taprio` offload flag,
MAC Merge verify, fragment counter 증가는 필요한 증거지만, packet별 one-way latency
측정 성립을 보장하지 않는다.

## 측정 가능성 분류

| 항목 | 현재 판정 | 허용되는 결과 |
|---|---|---|
| gPTP path delay와 lock health | 제한적으로 가능 | ptp4l state, offset, path delay 추세 |
| Qbv control/offload | 가능 | qdisc, queue mapping, PCP delivery, offload state |
| Qbv gate phase | 부분 시험 | sender probe는 software timestamp만 관찰; PHC 기준 packet timestamp 수집 경로 재시험 필요 |
| Qbu fragmentation/reassembly | 가능 | sender/receiver counter delta, verify, error count |
| Qbu express tail-latency delta | 직접 A/B 측정 미수행 | IET off/on에서 express packet sample을 수집해 비교 필요 |
| end-to-end one-way latency | 직접 측정 미수행 | TX/RX raw-HW timestamp와 sequence pairing을 수동 시험으로 확인 필요 |

## 설계 결정

1. 첫 기준 path는 `cpsw-direct`인 SK `eth0`과 TMDS `eth1`이다. Qbv와 Qbu의 기존 기능 증적이 있고 CPSW-PHC 구조를 단순화한다.
2. `gptp-direct`인 SK `eth1`과 TMDS `eth2`는 gPTP reference로 유지하되, CPSW/ICSSG의 서로 다른 PHC를 동일 시간축으로 가정하지 않는다.
3. 각 수동 시험 기록에는 baseline check 외에 image/DTB/rootfs identity, boot ID, kernel release, link state, `ethtool -T`, PHC health, CPU governor/affinity를 고정해 기록해야 한다.
4. raw sample validity, clock uncertainty, loss, outlier 정의를 만족하지 못하면 summary는 `invalid`로 표시하고 percentile을 성능 결론에 사용하지 않는다.
