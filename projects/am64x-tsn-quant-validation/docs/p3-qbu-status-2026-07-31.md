# P3 Qbu/IET 현재 상태

## Artifact Inventory

P3 board `/tmp`에는 historical run directory가 누적되어 있지만, completed campaign의 raw
evidence는 이미 PC project artifact에 회수되어 있다. 추가 bulk-transfer는 필요하지 않다.

| Campaign artifact | Expected run | Local `summary.json` | 상태 |
|---|---:|---:|---|
| `p3-qbu-operational-20260730-174108-kst` | 16 | 16 | complete, valid |
| `p3-qbu-operational-20260730-183725-kst` | 19 | 19 | complete, valid |
| `p3-qbu-operational-20260731-100846-kst` | 19 | 19 | complete, valid |
| `p3-qbu-operational-20260730-174028-kst` | 0 | 0 | host artifact-directory collision, board traffic 전 실패 |
| `p3-qbu-operational-20260731-090636-kst` | 2 | 2 | nested SSH hang 이전 partial evidence, aggregate 제외 |

각 complete run은 `runs/<case>/run-*/sk`와 `runs/<case>/run-*/tmds`에 board-side
before/after MM state, counters, qdisc/filter, iperf3 JSON, link/driver/boot identity를 보존한다.

## 완료된 검증

1. **Activation baseline**
   - TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver, 1 Gbps/full path를 채택했다.
   - IET-off counter-zero control과 golden on 3-repeat activation을 확인했다.
   - sender fragment와 receiver fragment/assembly counter가 동시에 증가한다.

2. **Initial operational matrix**
   - 모든 on case가 activation probability 1.0이었다.
   - 50M preemptible/50M express, 30 s x 3만 initial matrix에서 loss/error 없이 `active`였다.

3. **Loss boundary extension**
   - 50M preemptible/50M express, 60 s x 3은 `active`였다.
   - 75M은 active/degraded 혼재, 100M 이상은 degraded였다.

4. **Candidate qualification**
   - 50M/50M, 300 s x 3에서 preemptible loss는 0이었지만 한 run에서 express loss 2가 발생했다.
   - 따라서 loss-free production profile은 아직 확정하지 않았다.
    - 55-70M fine sweep은 active/degraded가 혼재하거나 degraded여 timing-sensitive transition을 보였다.

5. **Timing variance isolation**
    - 50M/50M, 300 s x 3에서 default, CPU split 단독, 100 us pacing 단독은 모두 express loss 또는
      SMD error를 보였다.
    - TMDS preemptible CPU0 + express CPU1와 100 us pacing의 결합은 3 run 모두 `active`이고
      preemptible/express loss와 assembly/SMD error가 0이었다.

## Current Decision

- actual Qbu activation은 current CPSW path와 traffic generator에서 반복 재현됐다.
- P3 initial envelope과 50-150M boundary evidence는 충분히 확보됐다.
- `50M preemptible + 50M express`는 가장 낮은-loss diagnostic point지만 production profile은 아니다.
- P3 결과를 UART transport 전환만을 이유로 재실행하지 않는다. 최근 변경은 board control/stage
  transport와 artifact collection failure handling이며 Qbu setup, traffic, counter criterion을
  바꾸지 않았다.
- current evidence는 sender CPU placement와 generator burst timing의 상호작용이 express loss를
  지배함을 지지한다. 결합 조건의 900 aggregate loss-free seconds는 diagnostic evidence이며
  production profile acceptance는 아니다.
- independent reboot 후 combined condition의 첫 300 s run에서 preemptible loss 10이 발생했다.
  CPU/IRQ placement와 MM/hardware error counters는 정상이어도 deterministic loss-free profile은
  성립하지 않는다.
- SK receiver UDP `RcvbufErrors`는 229376 B buffer에서 preemptible loss와 함께 증가했고 1 MiB
  runtime buffer에서 사라졌다. express/SMD loss는 남았으며 fragment 188 B가 현재 가장 낮은-loss
  boundary지만 deterministic candidate는 아니다.

## Harness State

- Board control과 endpoint script stage: UART-only
- Artifact bulk transfer: traffic/cleanup 뒤 bounded SSH only
- stage: campaign 최초 1회, target SHA-256 verification
- artifact transfer: TMDS->SK board-side 60 s, host-side 90 s timeout
- TMDS management `eth0` recovery: cleanup 뒤 UART address discovery와 host-side bounded artifact transfer
- run failure: `campaign-record.json` 저장 후 즉시 stop
- progress: `campaign-status.json`

## Driver Telemetry 완료 및 Follow-up 계획: 2026-08-11

`artifacts/p3-qbu-driver-telemetry-managed-20260805-kst`는 `QBU_1G_DRIVER_TELEMETRY_01`
control 1회와 on-run 300 s x 3회를 모두 완료했고 `valid: true`다. on-run은 activation
probability 1.0, preemptible/express loss 0, assembly/SMD error 0의 `active` 3회였다.
SK의 UDP `InErrors`/`RcvbufErrors` 및 softnet dropped/time-squeeze도 run 동안 증가하지 않았다.
이는 fragment 188 B + CPU split + 100 us pacing의 유효 diagnostic 표본이지만 production
acceptance는 아니다.

8월 10일 재실행 실패는 Qbu result failure가 아니라 TMDS management `eth0` recovery와
artifact collection transport failure다. `transport-status.json`에 cleanup/reset 오류와
transport 오류를 분리 기록하며, raw artifact가 회수되지 않은 run은 aggregate에 포함하지 않는다.

다음 case `QBU_1G_DRIVER_TELEMETRY_FOLLOWUP_01`은 동일 조건에서 300 s x 5를 수행한다.
SK RX0 및 TMDS TX2/TX3 IRQ, softnet, UDP MIB, MAC Merge counter를 5 s interval로 함께
수집한다. loss/SMD error는 diagnostic event로 보존하고 campaign 중단 조건으로 사용하지 않는다.

### Follow-up 결과와 instrumentation 보정: 2026-08-11

`artifacts/p3-qbu-operational-20260811-093501-kst`는 control 1회와 on-run 300 s x 5를
모두 artifact까지 회수했다. on-run은 active 2회, degraded 3회였으며 degraded run에서는
express loss 25/9/18과 receiver SMD error 22/9/16이 동반됐다. SK UDP/softnet error는
증가하지 않아 이번 표본의 loss를 receiver socket overflow로 해석하지 않는다.

다만 첫 telemetry format은 TMDS TX3 IRQ의 CPU1 count를 읽지 않고 첫 CPU column만 읽었다.
또한 SK/TMDS wall-clock epoch가 서로 달라 absolute timestamp를 cross-board correlation에
사용할 수 없다. 다음 diagnostic run은 모든 CPU IRQ column의 합계와 endpoint별
`sample_index`/`elapsed_s`를 기록해, sender TX2/TX3 service와 receiver SMD event를
run-relative window로 비교한다.

### 보정된 correlation 결과: 2026-08-11 10:50

`artifacts/p3-qbu-operational-20260811-105003-kst`의 campaign은 control 1회와 on-run
300 s x 5회를 완료했으며 `valid: true`다. CPU 합계와 endpoint별 run-relative 시간축을
사용한 collector 보정 후, on-run은 모두 `active`였고 양 flow loss 및 assembly/SMD error가
0이었다. 조건은 50M/50M, 1472 B, fragment 188 B, CPU0/CPU1 split, 100 us pacing,
receiver rmem 1 MiB였다. sender fragment rate는 7.5~384.057/s로 가변적이었다.

이는 1,500초의 무손실 diagnostic 표본이며 production acceptance가 아니다. 앞선
독립 reboot 실패 및 같은 계열의 loss/SMD error 결과를 유지한다. IET-off control은
`control-degraded`여서 on/off throughput 개선의 비교 기준으로 사용하지 않는다.
error가 없는 이 표본만으로 IRQ service와 SMD error의 인과관계도 확정할 수 없다.

2026-11-04 장비 이전에서는 사용자 결정에 따라 raw artifacts/log를 전송하지 않는다.
새 장비에서는 본 문서의 결과와 matrix/tool을 기준으로 재개하며, 원시 자료 재집계가
필요한 경우에는 원본 장비의 해당 artifact를 별도로 요청한다.

## 남은 P3 질문

1. 50M에서 드물게 발생한 express loss가 traffic generator scheduling, CPU affinity, queue service,
   PHY/MAC error 중 어느 요인인지 분리해야 한다.
2. rate와 fragment intensity가 단조롭지 않은 이유를 CPU affinity와 generator burst 고정 A/B로
   확인해야 한다.
3. production profile을 주장하려면 duration, permitted loss, assembly/SMD error bound를 먼저
   acceptance rule로 정하고 해당 rule을 만족하는 traffic profile을 별도 검증해야 한다.
4. CPU0/CPU1 online topology, CPSW IRQ/NAPI placement을 고정한 상태에서 combined condition의
   endurance와 교란 부하 영향을 확인해야 한다.
5. SK receiver single-CPU NAPI/socket receive queue pressure와 sender queue-service timing을
   구분할 telemetry-first 원인분리 design을 정의해야 한다.
6. CPSW queue service/NAPI/IRQ dispatch와 MAC Merge SMD error timing correlation을 driver-level
   telemetry로 수집해야 한다.

## 관련 기록

- `docs/p3-qbu-activation-baseline-2026-07-30.md`
- `docs/p3-qbu-operational-campaign-result-2026-07-30.md`
- `docs/p3-qbu-lossless-boundary-result-2026-07-30.md`
- `docs/p3-qbu-candidate-qualification-result-2026-07-31.md`
- `docs/p3-qbu-execution-harness-contract-2026-07-31.md`
- `docs/p3-qbu-reboot-readiness-2026-08-03.md`
- `docs/p3-qbu-timing-variance-result-2026-08-03.md`
- `docs/p3-qbu-combined-endurance-plan-2026-08-04.md`
- `docs/p3-qbu-combined-endurance-result-2026-08-04.md`
- `docs/p3-qbu-loss-location-isolation-result-2026-08-04.md`
