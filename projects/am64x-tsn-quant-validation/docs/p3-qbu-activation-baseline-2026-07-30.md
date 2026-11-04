# P3 Qbu/IET Activation Baseline 채택 기록

## 상태

`P3_QBU_ACTIVATION_BASELINE_20260730`을 현재 정량검증 프로젝트의 P3
Qbu/IET activation baseline으로 채택한다. 이 baseline은 production traffic profile 또는
loss-free operating range가 아니라, 동일한 1 Gbps CPSW path에서 IET on/off hardware counter
causality와 TMDS sender actual fragmentation을 반복 재현하는 실행 전제다.

## 고정 조건

| 항목 | 채택 값 |
|---|---|
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Link | existing direct cable, 1 Gbps/full, autoneg 유지 |
| Preemptible | UDP 5002, priority 2/TC2, 200 Mbit/s, 1472 B |
| Express | UDP 5003, priority 3/TC3, 50 Mbit/s, 1472 B |
| Duration | 30 s |
| Queue | `tx 4`, `mqprio queues 1@0 1@1 1@2 1@3`, `fp P P P E` |
| MAC Merge | `pmac-enabled on`, `tx-enabled on`, `verify-enabled on`, `verify-time 10`, minimum fragment 124 |

각 endpoint는 `IP flush -> sibling eth0 down -> target eth1 down -> tx 4 ->
p0-rx-ptype-rrobin off -> MAC Merge configure -> eth1 up -> sleep 5 -> test IP` 순서로
설정한다. SK receiver를 먼저 완료한 다음 TMDS sender를 설정한다. traffic 전 TMDS sender는
반드시 `TX active: on` 및 `Verification status: SUCCEEDED`여야 한다. SK receiver의 local
verify `FAILED`/`TX active: off`는 historical certificate와 동일하며 baseline failure가 아니다.

## 채택 증거

| Artifact | Mode | Sender fragment | Receiver fragment / assembly-ok | 판정 |
|---|---|---:|---:|---|
| `artifacts/p3-qbu-fragmentation-20260730-162455-kst` | on | +3020 | +3020 / +3020 | valid, `degraded` |
| `artifacts/p3-qbu-fragmentation-20260730-162656-kst` | on | +2416 | +2416 / +2416 | valid, `degraded` |
| `artifacts/p3-qbu-fragmentation-20260730-162841-kst` | on | +1610 | +1610 / +1610 | valid, `degraded` |
| `artifacts/p3-qbu-fragmentation-20260730-163013-kst` | off | 0 | 0 / 0 | valid, `control-degraded` |

세 on run은 모두 TMDS sender MM readiness, Linux filter packet delta, sender hardware
`tx_pri2`/`tx_pri3` delta, receiver assembly error zero를 만족했다. 따라서 counter 증가가
설정 수용 또는 Linux filter hit만으로 생긴 오판이 아님을 확인했다.

## Campaign Gate

새 P3 campaign은 다음을 먼저 만족해야 한다.

1. `golden-control-off`는 valid이고 `control-failed`가 아니어야 한다.
2. `golden-baseline` 3회는 모두 measurement-valid여야 한다.
3. `golden-baseline`의 activation probability는 1.0이어야 한다.

이 gate가 실패하면 remaining traffic matrix를 실행하지 않는다. baseline과 다른 offered
load/frame-size case의 `inactive`, `intermittent`, `degraded` 결과는 baseline failure가 아니라
operational-envelope data로만 해석한다.

## 한계

baseline on run에는 UDP loss가 남아 있어 모두 `degraded`다. IET-off control도 counter-zero는
성립했지만 traffic loss가 있어 `control-degraded`다. 따라서 이 기록은 Qbu activation
causality의 baseline이며, production deployment의 허용 loss boundary나 최적 traffic profile을
확정하지 않는다.

## 관련 자료

- `docs/p3-qbu-fragmentation-quantification-plan-2026-07-28.md`
- `config/p3-qbu-operational-matrix.json`
- `projects/tsn_qbu/docs/REPRODUCTION.md`
- `projects/tsn_qbu/docs/history/2026-07-09_rewired_pair_c_result.md`
