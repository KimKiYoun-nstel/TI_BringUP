# AM64x TSN Quantitative Validation

## 목적

이 프로젝트는 SK-AM64B와 TMDS64EVM에서 이미 확인한 gPTP, DSCP/PCP, Qbv,
Qbu/IET 기능을 정량적으로 검증하기 위한 독립 작업 단위다. 목표는 설정 성공이나
counter 증가를 재확인하는 것이 아니라, 고정된 조건의 A/B 비교로 critical traffic의
latency, jitter, loss 및 tail latency 변화를 신뢰성 있게 판단하는 것이다.

기준 가이드는 `.agents/AM64x_TSN_정량_검증_가이드.md`와
`.agents/AM64x_TSN_정량_검증_TI_SDK_활용_추가_가이드.md`다. 현재 증적의 상태는
[`docs/guide-review.md`](docs/guide-review.md), workspace TI SDK source와의 교차 분석 및
수동 시험 순서는 [`docs/workspace-sdk-cross-check.md`](docs/workspace-sdk-cross-check.md)에 기록한다.
P1 high-rate 결과, pktgen 전환 실패 및 다음 세션 재개 절차는
[`docs/session-handoff-2026-07-23.md`](docs/session-handoff-2026-07-23.md)에 기록한다.
P1의 목적, 시험 구성, 최종 판정, 제약 및 후속 선택지는
[`docs/p1-gptp-load-validation-2026-07-23.md`](docs/p1-gptp-load-validation-2026-07-23.md)에
정리한다.
P2 Qbv 정량 검증의 현재 readiness, timestamp blocker와 qualification 순서는
[`docs/p2-qbv-readiness-2026-07-23.md`](docs/p2-qbv-readiness-2026-07-23.md)에 정리한다.
P2 CPSW direct control-plane replay의 실제 결과와 raw artifact는
[`docs/p2-qbv-control-replay-2026-07-24.md`](docs/p2-qbv-control-replay-2026-07-24.md)에
정리한다.

## 현재 판정

| 항목 | 상태 | 현재 말할 수 있는 범위 |
|---|---|---|
| gPTP link synchronization | 부분 확인 | SK `eth1`과 TMDS `eth2`의 gPTP lock 및 path delay 관찰 |
| DSCP/PCP | 확인 | CPSW direct sender와 switchdev forwarding의 PCP 전달 |
| Qbv | 제한적 확인 | CPSW hardware `taprio` offload와 PCP delivery |
| Qbu/IET | 확인 | TMDS CPSW sender의 fragment 및 SK receiver reassembly counter 증가 |
| one-way latency | 직접 측정 미수행 | 현 보드 불가로 판정한 근거 없음; CPSW direct path의 수동 측정 경로 확인 필요 |
| Qbv/Qbu tail-latency improvement | 직접 A/B 측정 미수행 | 현 보드 불가로 판정한 근거 없음; one-way sample 수집 후 비교 필요 |

기존 `iperf3` 및 `tcpdump` 중심 기능 검증 절차에는 packet별 TX/RX raw hardware timestamp,
공통 PHC 시간축 검증, sequence matching, raw sample archive가 기록돼 있지 않다. 이는
보드 불능 판정이 아니라 아직 직접 수행하지 않은 측정 경로다. 수동 시험에서 이 경로를
확인한 뒤 latency percentile과 Qbv/Qbu 성능 개선을 비교한다.

## 범위와 비범위

## 운영 원칙

이 프로젝트의 정량 검증은 수동으로 수행한다. 보드 설정, traffic 생성, packet capture,
counter 채취, 결과 판정은 각 test case의 기록지와 raw data를 보면서 수행하며, 이
프로젝트에 runner나 board command 자동 실행 도구를 추가하지 않는다. 여기의 문서는
수동 시험에서 비교 조건과 증적 형식을 빠뜨리지 않기 위한 기준이다.

포함:

- 측정 topology, MAC block, PHC, link speed의 고정 및 증적화
- TX/RX hardware timestamp와 packet sequence pairing 성립성 검증
- Qbv/Qbu off/on 조건의 traffic profile, CPU 조건, qdisc 및 counter 고정
- raw sample, 환경 manifest, percentile summary의 재현 가능한 보존
- 측정 성립 조건 및 중단 기준의 명시적 판정

제외:

- 기존 `am64x-tsn-validation-automation`의 기능 enable regression 대체
- timestamp validity가 없는 `tcpdump` timestamp를 one-way latency로 해석
- 단일 run 또는 counter 증가만으로 성능 개선 결론 도출
- workspace 또는 SDK 원본의 무단 수정

## 프로젝트 구조

```text
am64x-tsn-quant-validation/
  config/topology.yaml       # 측정 기준 topology와 알려진 제약
  docs/guide-review.md       # 가이드 요구사항 대비 현재 가능성 판정
  docs/workspace-sdk-cross-check.md # workspace TI SDK와 증적의 교차 분석 및 수동 단계
  docs/measurement-plan.md   # gate, 최소 matrix, data contract, 중단 기준
  artifacts/                 # git 제외 raw capture 및 local run data
```

## 실행 순서

1. `config/topology.yaml`의 cable pair, netdev, MAC block, PHC를 실제 board에서 다시 확인한다.
2. `shared-clean-v1`을 적용하고 image/DTB/rootfs identity, boot ID, CPU governor, link speed를 run manifest에 기록한다.
3. `QUALIFY_TIMESTAMP_1G_01`에서 packet별 TX/RX raw-HW timestamp와 sequence pairing, PHC offset bound를 검증한다.
4. qualification이 통과한 경우에만 Qbv/Qbu A/B traffic case를 반복 실행한다.
5. timestamp qualification이 실패하면 hwtstamp 설정, socket timestamp 경로, RX 수집, PHC 동기 상태를 원인별로 확인하고 같은 case를 다시 측정한다. 실패한 run은 원인 분석 자료로 보존하되 latency 결과로 사용하지 않는다.

구체적인 gate와 matrix는 [`docs/measurement-plan.md`](docs/measurement-plan.md)를 따른다.

## 기존 자산과의 관계

- `projects/am64x-tsn-validation-automation/`: runtime baseline, UART-only preflight, 기능 동작 regression의 기준이다.
- `projects/tsn_qbv/`, `projects/tsn_qbu/`, `projects/tsn_dscp_pcp/`: topology, QoS prerequisite, Qbv/Qbu historical evidence의 근거다.
- 이 프로젝트: 위 자산을 변경하지 않고, 정량 측정의 성립성 및 결과 보존 계약을 별도로 관리한다.
