# P3 Qbu/IET Operational Envelope 검증 계획

## 목적

P3의 목적은 Qbu 설정을 한 번 수용하거나 fragment counter를 한 번 증가시키는 것이 아니다.
현재 AM64x CPSW, Linux driver, firmware, MAC Merge 설정에서 Qbu/IET가 어떤 traffic
조건에서 실제로 활성화되는지, 어느 조건에서 inactive 또는 intermittent가 되는지, 그리고
loss/error가 발생하는 영역이 어디인지를 계측한다.

이 결과는 실제 network에서 express/preemptible class, frame size, traffic shaping,
minimum fragment size와 허용 operating range를 정하는 근거다. P3는 one-way latency 또는
jitter A/B 시험이 아니다. 그 목적은 P4에서 raw-HW timestamp/sequence pairing 조건이
성립한 path로 분리한다.

## 기본 원리

Qbu/IET activation은 enable bit만으로 결정되지 않는다. 다음이 동시에 성립해야 한다.

1. MAC Merge, `mqprio fp`, priority filter, queue count가 driver에 수용되어야 한다.
2. preemptible frame이 MAC TX에서 실제 송신 중이어야 한다.
3. 그 송신 구간에 express frame이 도착해야 한다.

따라서 preemptible/express offered rate, packet size, packet rate, burst timing, CPU
scheduling과 queue service는 fragment 발생 여부에 직접 영향을 준다. 설정과 TC counter가
정상이어도 overlap이 부족하면 fragment가 `0`일 수 있으며, 이것은 즉시 driver failure가
아니다.

## 고정 Path와 Golden Baseline

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_OPERATIONAL_01` |
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Link | existing 1 Gbps/full direct cable, autoneg 유지 |
| Queue | `mqprio` 4 TC, `fp P P P E` |
| Preemptible class | UDP dport 5002, priority 2/TC2 |
| Express class | UDP dport 5003, priority 3/TC3 |
| MAC Merge on | `pmac-enabled on`, `tx-enabled on`, `verify-enabled on`, minimum fragment 124 |

이 방향은 기존 `projects/tsn_qbu`에서 TMDS sender fragment와 SK receiver reassembly가
동시에 관찰된 historical golden direction이다. 기준 profile은 preemptible `200M`/1472 B,
express `50M`/1472 B, 30 s다. 이 historical result는 matrix의 출발점이며, P3는 current
runtime에서 raw artifact와 반복성 통계를 새로 만든다.

현재 runtime에서 채택된 P3 activation baseline의 exact ordering, evidence와 campaign gate는
[`p3-qbu-activation-baseline-2026-07-30.md`](p3-qbu-activation-baseline-2026-07-30.md)에
고정한다.

채택 baseline을 통과한 첫 operational matrix 결과는
[`p3-qbu-operational-campaign-result-2026-07-30.md`](p3-qbu-operational-campaign-result-2026-07-30.md)에
정리한다.

50-150 Mbit/s preemptible loss-free boundary 확장 결과는
[`p3-qbu-lossless-boundary-result-2026-07-30.md`](p3-qbu-lossless-boundary-result-2026-07-30.md)에
정리한다.

50 Mbit/s endurance와 55-70 Mbit/s fine sweep의 candidate qualification 결과는
[`p3-qbu-candidate-qualification-result-2026-07-31.md`](p3-qbu-candidate-qualification-result-2026-07-31.md)에
정리한다. P3 실행 harness의 bounded operation과 failure-stop contract는
[`p3-qbu-execution-harness-contract-2026-07-31.md`](p3-qbu-execution-harness-contract-2026-07-31.md)를
따른다.

완료된 artifact inventory, current conclusion, 제외된 incomplete campaign과 남은 질문은
[`p3-qbu-status-2026-07-31.md`](p3-qbu-status-2026-07-31.md)에 정리한다.

### 2026-07-30 Baseline Qualification

historical certificate와 P3 초기 runner의 차이는 MAC Merge enable 직후의 안정화 순서였다.
P3 baseline은 다음 순서를 고정한다.

1. SK receiver를 먼저 `IP flush -> sibling eth0 down -> TX 4 -> rrobin off -> MM on -> link up -> 5 s -> test IP` 순서로 설정한다.
2. TMDS sender도 같은 순서로 설정한 뒤 sender `TX active: on`, `Verification status: SUCCEEDED`를 확인한다.
3. sender `mqprio queues 1@0 1@1 1@2 1@3`와 TC2/TC3 filter를 적용하고 traffic을 시작한다.

초기 runner는 `link up` 직후 sender verification을 확인해 historical procedure의 5-second
settling window를 건너뛰었다. 이 때문에 configuration은 수용됐지만 sender MM gate가 아직
형성되지 않은 run을 발생시켰다.

수정된 ordering의 30-second golden on repeat 세 건은 모두 valid였다.

| Artifact | Sender fragment | Receiver fragment / assembly-ok | Classification |
|---|---:|---:|---|
| `p3-qbu-fragmentation-20260730-162455-kst` | +3020 | +3020 / +3020 | `degraded` |
| `p3-qbu-fragmentation-20260730-162656-kst` | +2416 | +2416 / +2416 | `degraded` |
| `p3-qbu-fragmentation-20260730-162841-kst` | +1610 | +1610 / +1610 | `degraded` |

각 run에서 TMDS sender는 `TX active: on`/`SUCCEEDED`, SK receiver는 historical certificate와
동일하게 local `FAILED`/`off`였다. receiver local verify failure는 이 fixed direction의
pass criterion이 아니다. IET-off control
`p3-qbu-fragmentation-20260730-163013-kst`는 동일 traffic/class hit에서 fragment와
assembly delta가 모두 0이어서 `control-degraded`로 valid했다.

이 baseline은 Qbu on/off counter causality와 activation repeatability를 보장한다. UDP loss가
각 on run에서 남아 있으므로 loss-free production profile 또는 operational-envelope 결론은
아직 아니다.

## P3-A: Configuration Qualification

각 run은 traffic 전에 다음을 archive한다.

- cable peer MAC, carrier, link speed, duplex
- `ethtool -i`, `ethtool --show-mm`, queue count, qdisc, egress filter
- kernel release, boot ID, CPU load
- MAC Merge on run의 TMDS sender `Verification status: SUCCEEDED`, `TX active: on`
- TC2/TC3 filter packet delta
- sender `tx_pri2`/`tx_pri3` hardware priority delta

이 gate가 실패하면 결과는 `invalid`다. fragment가 0인 traffic 결과와 configuration
failure를 혼동하지 않는다.

## P3-B: Traffic Matrix

matrix는 `config/p3-qbu-operational-matrix.json`이 owner다. 기본 matrix는 다음 축을
최소한 분리한다.

| Case | Preemptible | Express | 관찰 목적 |
|---|---|---|---|
| `golden-control-off` | 200 Mbit/s, 1472 B | 50 Mbit/s, 1472 B | IET disabled negative control 1회 |
| `golden-baseline` | 200 Mbit/s, 1472 B | 50 Mbit/s, 1472 B | known-good profile 재현성 |
| `reduced-preemptible-load` | 50 Mbit/s, 1472 B | 50 Mbit/s, 1472 B | preemptible wire occupancy 영향 |
| `reduced-express-rate` | 200 Mbit/s, 1472 B | 10 Mbit/s, 1472 B | express arrival frequency 영향 |
| `high-express-pps` | 200 Mbit/s, 1472 B | 10 Mbit/s, 64 B | express bandwidth과 PPS를 분리 |
| `elevated-preemptible-load` | 400 Mbit/s, 1472 B | 50 Mbit/s, 1472 B | higher occupancy 영역 관찰 |

on case는 기본 3회 반복한다. 요청 rate가 아니라 iperf3 achieved rate, packet count와
loss를 결과의 독립 변수로 사용한다. 이 initial matrix는 line-rate saturation을 주장하지
않는다. generator가 만든 실제 rate/PPS와 결과를 보고 다음 rate/burst matrix를 추가한다.

IET off는 모든 case의 performance A/B가 아니다. golden profile에서 counter causality를
확인하는 negative control 1회다. P3의 주 데이터는 IET on traffic sweep이다.

IET off에서 fragment/reassembly counter가 모두 0이면 causality control은 성립한다. 같은
run의 UDP loss는 `control-degraded`로 기록해 IET on loss와 비교하지만, counter-zero control을
무효화하지는 않는다. 반대로 IET off에서 counter가 증가하면 `control-failed`이며 P3 on case를
해석하지 않는다.

## P3-C: Run별 정량값

각 mode/case/repeat에서 다음을 보존한다.

- TMDS sender `MACMergeFragCountTx`/`iet_tx_frag` delta와 초당 fragment rate
- SK receiver `MACMergeFragCountRx`/`iet_rx_frag`, assembly-ok, assembly/SMD error delta와 초당 rate
- preemptible/express flow의 sent/received bitrate, sent/received packet, UDP loss
- TC2/TC3 filter packet delta
- MAC Merge state, queue/class/qdisc counter, CPU load

`MACMergeFragCountTx`와 `MACMergeFrameAssOkCount`는 1:1 비율로 해석하지 않는다. 하나의
원래 frame이 여러 fragment가 될 수 있기 때문이다. P3는 절대 counter 차이를 fragment
intensity와 receiver assembly health의 독립 지표로 기록한다.

## P3-D: Activation Region 판정

각 on case는 run별로 다음 중 하나로 분류한다.

| 분류 | 조건 | 해석 |
|---|---|---|
| `active` | configuration/traffic gate 통과 및 sender fragment, receiver fragment, assembly-ok 모두 양수 | 해당 achieved rate/PPS 조건에서 actual Qbu activation 관찰 |
| `inactive` | configuration/rate/class gate 통과, actual counter 모두 0, loss/error 없음 | 설정 불능이 아니라 overlap 부족 또는 해당 traffic 조건의 no-activation 후보 |
| `inactive-degraded` | actual counter는 모두 0이나 UDP loss 또는 assembly/SMD error가 발생 | no-activation과 transport degradation이 함께 있는 조건 |
| `intermittent` | 동일 case 반복에서 active와 inactive가 혼재 | packet timing, burst, CPU/queue service에 민감한 transition 영역 |
| `degraded` | activation은 관찰됐으나 UDP loss 또는 assembly/SMD error가 발생 | 해당 traffic 조건은 Qbu가 동작해도 production operating range에서 제외 후보 |
| `invalid` | link, peer, MAC Merge, Linux filter 및 hardware priority class hit, achieved-rate, counter-readability gate 실패 | traffic effect로 해석 금지 |

case aggregate는 activation probability, fragment/reassembly/error rate의 min/median/max,
achieved rate와 loss 분포를 기록한다. 이는 “이 설정이 동작한다”가 아니라 current runtime의
traffic-conditioned operational envelope다.

## Driver/Firmware 조사 분기

다음 순서로 원인을 좁힌다.

1. `invalid`: qdisc/MM/filter/link/achieved-rate/counter-readability 문제를 먼저 수정한다.
2. `inactive`: class hit와 achieved rate가 정상인 상태에서 frame overlap이 충분한지를
   packet size, express PPS, burst, CPU affinity 축으로 추가 측정한다.
3. `intermittent`: traffic timing/CPU scheduling/queue service의 영향을 반복 sweep으로 좁힌다.
4. `degraded`는 loss/error boundary로 보존하고 production traffic profile에서 제외한다.
   known-good golden profile 또는 충분히 자극한 profile에서 반복 inactive이거나 `degraded`가
   지속되면 CPSW driver, firmware, PHY/RGMII, MAC Merge runtime register를 조사한다.

즉 driver/firmware 변경은 설정 수용 실패나 counter 0만으로 시작하지 않는다. configuration
gate와 traffic stimulus가 충분하다는 증거를 확보한 뒤 조사 대상으로 승격한다.

## 실행과 Cleanup

단일 case runner:

```bash
python3 projects/am64x-tsn-quant-validation/tools/p3_qbu_fragmentation.py \
  --mode on --case-id golden-baseline
```

matrix campaign:

```bash
python3 projects/am64x-tsn-quant-validation/tools/p3_qbu_operational_campaign.py
```

각 case artifact에는 manifest, preflight, MM/qdisc/filter/counter before/after, driver,
kernel/boot identity, load, iperf JSON, run summary를 보관한다. campaign summary는 case별
activation probability와 operational region을 보관한다.

P3 종료 시 양 endpoint의 root/clsact qdisc와 MAC Merge enable을 제거한다. artifact는 direct
test IP가 존재하는 상태에서 먼저 회수하고, 이후 `TMDS eth1=10.33.0.2/24`와
`SK eth1=10.33.0.1/24`를 제거한다. P2 Qbv schedule, gPTP state, 이전 TSN profile은 복원하지
않는다.

P3는 existing actual-Qbu certificate와 동일하게 target CPSW port의 sibling port를 down한 뒤
`ethtool -L <target> tx 4` 및 `mqprio queues 1@0 1@1 1@2 1@3`를 적용한다. Linux filter hit만
으로는 충분하지 않으므로, sender `tx_pri2`와 `tx_pri3` hardware priority delta도 validity gate로
기록한다.
