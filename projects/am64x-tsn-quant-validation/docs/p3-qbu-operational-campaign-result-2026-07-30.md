# P3 Qbu/IET Operational Campaign 결과

## 실행 정보

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_OPERATIONAL_01` |
| Raw artifact | `artifacts/p3-qbu-operational-20260730-174108-kst` |
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Link | existing direct cable, 1 Gbps/full |
| Run | 2026-07-30, control 1회 + on case 5개 x 3회 |
| Overall result | `valid: true` |

campaign은 `P3_QBU_ACTIVATION_BASELINE_20260730` gate를 통과한 뒤 나머지 matrix를
실행했다. 모든 run은 artifact 회수 뒤 data-port test IP를 제거하고 MAC Merge를 off 상태로
복원했다.

## Aggregate 결과

아래 rate는 30-second window의 sender fragment delta/second median이다. loss는 iperf3
lost-packet median이며, `active`는 loss/error 없는 activation, `degraded`는 activation과
loss 또는 receiver assembly/SMD error가 함께 있었음을 뜻한다.

| Case | Activation probability | Fragment/s median | Preemptible loss median | Express loss median | Region |
|---|---:|---:|---:|---:|---|
| `golden-control-off` | n/a | 0 | 254761 | 63734 | `control-degraded` |
| `golden-baseline` | 1.0 | 181.53 | 2961 | 15 | `degraded` |
| `reduced-preemptible-load` | 1.0 | 1.03 | 0 | 0 | `active` |
| `reduced-express-rate` | 1.0 | 41.90 | 1274 | 0 | `degraded` |
| `high-express-pps` | 1.0 | 3107.23 | 76093 | 47919 | `degraded` |
| `elevated-preemptible-load` | 1.0 | 1991.67 | 299682 | 339 | `degraded` |

`high-express-pps`의 receiver assembly-error median은 2.9/s, SMD-error median은 17.0/s다.
나머지 on case의 receiver assembly-error와 SMD-error median은 0/s다.

## 판정

1. 채택된 baseline은 campaign에서도 통과했다. golden on 3회는 모두 measurement-valid,
   activation probability 1.0이며 sender fragment, receiver fragment, receiver assembly-ok
   counter가 동시에 증가했다.
2. IET-off control은 fragment/reassembly delta 0으로 counter causality를 유지했다. 다만
   traffic loss가 있어 `control-degraded`이며 IET-off throughput/quality benchmark가 아니다.
3. 모든 on case에서 actual Qbu activation은 재현됐다. 따라서 이번 matrix 범위에서는
   `inactive` 또는 `intermittent` region을 발견하지 못했다.
4. `reduced-preemptible-load`는 세 run 모두 loss/error 없이 `active`였다. 이는 current
   tested range에서 유일한 loss-free activation candidate지만, 3 x 30 s evidence만으로
   production profile로 확정하지 않는다.
5. golden, reduced express, high express PPS, elevated preemptible load는 모두 activation은
   재현됐지만 `degraded`다. 특히 high express PPS와 elevated preemptible load는 큰 packet
   loss가 있으므로 production operating range 후보에서 제외한다.

## 다음 측정

`reduced-preemptible-load`를 production candidate로 평가하려면 duration을 늘리고,
preemptible rate를 50 Mbit/s 주변에서 세분화해 loss-free boundary와 fragment intensity를
추가로 측정한다. golden profile보다 더 높은 fragment rate를 목표로 하더라도 high express
PPS 또는 elevated preemptible load의 현재 loss/error 영역을 그대로 채택하지 않는다.

이 후속 loss-free boundary campaign의 결과는
[`p3-qbu-lossless-boundary-result-2026-07-30.md`](p3-qbu-lossless-boundary-result-2026-07-30.md)에
기록한다.

## 관련 자료

- `docs/p3-qbu-activation-baseline-2026-07-30.md`
- `docs/p3-qbu-fragmentation-quantification-plan-2026-07-28.md`
- `config/p3-qbu-operational-matrix.json`
- `artifacts/p3-qbu-operational-20260730-174108-kst/campaign-summary.json`
