# P3 Qbu/IET Candidate Qualification 결과

## 실행 정보

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_LOSSLESS_CANDIDATE_03` |
| Raw artifact | `artifacts/p3-qbu-operational-20260731-100846-kst` |
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Candidate endurance | preemptible 50 Mbit/s, express 50 Mbit/s, 1472 B, 300 s x 3 |
| Fine sweep | preemptible 55/60/65/70 Mbit/s, express 50 Mbit/s, 1472 B, 60 s x 3 |
| Overall result | `valid: true` |

이 campaign은 이전 boundary result의 50 Mbit/s point를 production candidate로 승격하기 전에
duration을 늘리고 50-75 Mbit/s interval을 세분화한 것이다.

## 결과

| Case | Classification count | Preemptible loss min / median / max | Express loss min / median / max | 판정 |
|---|---|---:|---:|---|
| 50 Mbit/s, 300 s | `active` 2, `degraded` 1 | 0 / 0 / 0 | 0 / 0 / 2 | near-loss-free, not loss-free |
| 55 Mbit/s, 60 s | `active` 1, `degraded` 2 | 0 / 3 / 9675 | 0 / 153 / 10754 | unstable/degraded |
| 60 Mbit/s, 60 s | `degraded` 3 | 6 / 10 / 21 | 0 / 0 / 2 | degraded |
| 65 Mbit/s, 60 s | `active` 1, `degraded` 2 | 0 / 2 / 3 | 0 / 0 / 120 | unstable/degraded |
| 70 Mbit/s, 60 s | `active` 1, `degraded` 2 | 0 / 7 / 40 | 0 / 0 / 305 | unstable/degraded |

50 Mbit/s endurance run은 sender fragment/receiver reassembly이 모두 발생했고 receiver
assembly/SMD error는 0이었다. 그러나 한 300-second run에서 express packet 2개가 유실되어
세 run 전부 `active`라는 acceptance를 만족하지 못했다.

55-70 Mbit/s fine sweep은 rate에 따른 단조 transition을 만들지 못했다. 55 Mbit/s는 한 run에서
큰 loss/error burst가 있었고, 60 Mbit/s는 작은 preemptible loss가 세 run 모두 발생했다.
65/70 Mbit/s는 zero-loss run과 degraded run이 혼재했다. 이 결과는 current userspace
generator/CPU scheduling/queue-service timing이 loss와 fragment intensity에 영향을 준다는
기존 관찰과 일치한다.

## Current Decision

현재 project에는 loss-free production Qbu profile이 없다. 50 Mbit/s는 가장 낮은-loss
activation point이지만, 900 aggregate seconds에서 express loss가 0이 아니므로
`near-loss-free diagnostic candidate`로만 유지한다. 55 Mbit/s 이상은 production candidate에서
제외한다.

다음 profile 측정은 `p3-qbu-execution-harness-contract-2026-07-31.md`의 bounded staging,
checkpoint, failure-stop contract가 안정적으로 적용된 뒤에만 수행한다. 먼저 duration/rate를
늘리는 대신 CPU affinity와 generator burst를 고정해 timing variance를 분리한다.

## 관련 자료

- `config/p3-qbu-lossless-candidate-qualification-matrix.json`
- `docs/p3-qbu-lossless-boundary-result-2026-07-30.md`
- `docs/p3-qbu-execution-harness-contract-2026-07-31.md`
- `artifacts/p3-qbu-operational-20260731-100846-kst/campaign-summary.json`
