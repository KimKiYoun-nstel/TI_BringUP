# P3 Qbu/IET Loss-Free Boundary 결과

## 실행 정보

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_LOSSLESS_BOUNDARY_02` |
| Raw artifact | `artifacts/p3-qbu-operational-20260730-183725-kst` |
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Boundary variable | preemptible UDP 5002 rate |
| Fixed express traffic | UDP 5003, 50 Mbit/s, 1472 B |
| Boundary case duration / repeat | 60 s / 3회 |
| Overall result | `valid: true` |

campaign은 IET-off control과 accepted golden `200M/50M` baseline 3회를 먼저 통과한 뒤
`50/75/100/125/150 Mbit/s` preemptible rate를 실행했다.

## Aggregate 결과

| Preemptible rate | Classification count | Fragment/s median | Preemptible loss min / median / max | Express loss min / median / max |
|---:|---|---:|---:|---:|
| 50 Mbit/s | `active` 3 | 0.68 | 0 / 0 / 0 | 0 / 0 / 0 |
| 75 Mbit/s | `active` 1, `degraded` 2 | 14.60 | 0 / 22 / 52 | 0 / 0 / 14 |
| 100 Mbit/s | `degraded` 3 | 20.13 | 59 / 173 / 196 | 7 / 7 / 1765 |
| 125 Mbit/s | `degraded` 3 | 400.72 | 307 / 523 / 996 | 0 / 4 / 267 |
| 150 Mbit/s | `degraded` 3 | 589.95 | 982 / 1110 / 1162 | 0 / 0 / 1 |

100 Mbit/s에서는 receiver assembly-error median이 0.017/s, SMD-error median이 0.117/s였다.
나머지 boundary case의 receiver assembly/SMD error median은 0/s였다.

## 판정

1. current 1 Gbps CPSW path에서 60 s x 3회 loss-free actual-Qbu activation이 확인된
   preemptible offered-rate upper point는 **50 Mbit/s**다.
2. **75 Mbit/s는 loss-quality transition point**다. 세 run 모두 activation은 있었지만 한 run만
   loss-free였으므로 production candidate로 채택하지 않는다.
3. **100 Mbit/s 이상은 current generator/queue/CPU 조건에서 consistently degraded**다.
   100 Mbit/s의 loss는 작더라도 모든 repeat에 존재했으며 receiver assembly/SMD error도
   관찰됐다.
4. fragment rate는 rate에 단조 증가하지 않았다. 예를 들어 75 Mbit/s와 100 Mbit/s의 run 간
   max/min fragment rate 차이가 크다. 이는 P3 기본 원리대로 userspace packet timing, CPU
   scheduling, queue service에 따른 overlap sensitivity가 남아 있음을 보여준다.

## Current Operating Recommendation

current tested conditions에서 loss-free Qbu activation candidate는 다음으로 제한한다.

```text
TMDS eth1 -> SK eth1, 1 Gbps/full
preemptible: 50 Mbit/s, UDP 5002, 1472 B
express:     50 Mbit/s, UDP 5003, 1472 B
```

이는 180 seconds aggregate evidence를 가진 candidate이지 production deployment approval이
아니다. 75 Mbit/s 이상을 사용하려면 loss budget, duration, CPU affinity, offered burst와
receiver error 기준을 별도로 검증해야 한다.

## 다음 측정

1. 50 Mbit/s candidate를 300 s 이상으로 확장해 long-duration loss/error를 확인한다.
2. 50-75 Mbit/s 사이를 5 Mbit/s 또는 10 Mbit/s step으로 측정해 transition interval을
   좁힌다.
3. CPU affinity와 packet generator burst 조건을 고정한 A/B run으로 fragment-rate variation의
   원인을 분리한다.

## 관련 자료

- `config/p3-qbu-lossless-boundary-matrix.json`
- `docs/p3-qbu-activation-baseline-2026-07-30.md`
- `docs/p3-qbu-operational-campaign-result-2026-07-30.md`
- `artifacts/p3-qbu-operational-20260730-183725-kst/campaign-summary.json`
