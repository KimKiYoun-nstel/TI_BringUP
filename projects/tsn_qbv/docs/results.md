# Qbv Results

## 상태 요약

| Phase | 상태 | 판단 |
|---|---|---|
| Phase 0 | 완료 | sender/receiver wire capture로 `vlan 301, p7/p6` 재현 확인 |
| Phase 1 | 완료 | candidate map + class separation + TX_PRI_MAP register 확인 |
| Phase 2 | 완료 | software CBS 적용 및 `p7` rate shaping 확인 |
| Phase 3 | 완료 | `taprio` apply 성공, all-open schedule로 continuity 확인 |
| Phase 4 | 완료 | selective gate schedule로 receiver burst pattern 변화 확인 |
| Phase 5 | 진행 중 | BMCA/UNCALIBRATED 및 PHC-based base-time까지 확인, stable SLAVE 미확보 |
| Phase A | 완료 | endpoint egress Qbv closeout 완료, direct 3경로의 SW/HW taprio 및 coexistence matrix 정리 |

## 현재 판정

- 새 `tsn_qbv` 프로젝트 골격은 준비되었다.
- Phase 0 baseline 재현이 실제 보드에서 다시 확인되었다.
- Phase 1 `mqprio` 기반 PCP -> TC / queue mapping 확인이 완료되었다.
- baseline `mqprio map 2 2 1 0 ...`은 separation map이 아니므로, Phase 1에서는 candidate map을 별도 적용했다.
- candidate `mqprio map 0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0`은 `replace`가 아니라 `del -> add`로 `eth0`에 적용했다.
- receiver wire capture 기준 `p7`/`p6`/`p0`를 모두 다시 구분해서 관찰했다.
- switchdev forwarding 경로에서 `tc -s qdisc`/`class`는 여전히 직접 판정 지표가 아니었지만,
  같은 `eth0` egress를 쓰는 `br-tsn.301` control path에서
  `p7 -> class100:3`, `p6 -> class100:2`, `p0 -> class100:1`이 재현되었다.
- `ethtool -d eth0`의 `TX_PRI_MAP` register도
  `00022018:reg(00002210) -> 00022018:reg(00000210)`으로 변했다.

Phase 2 `CBS shaping` 검증이 완료되었다.

- hardware offload `cbs`는 reject 되었지만, software `cbs`는 apply 성공했다.
- 동시 부하에서 `p7` flow는 `10 Mbits/sec -> 약 1 Mbits/sec`로 줄었고,
  background `p0` flow는 `20 Mbits/sec`를 유지했다.

Phase 3 `taprio 적용성` 확인이 완료되었다.

- `sch_taprio` module load 가능
- `taprio` qdisc apply 성공
- selective schedule은 traffic continuity를 깨뜨릴 수 있음을 확인
- `tc qdisc del ...` 후 all-open schedule로 recreate 하면 continuity 유지 가능

Phase 4 `Qbv gate schedule effect` 검증이 완료되었다.

- all-open schedule에서는 `p7/p0`가 receiver에서 interleaved pattern으로 들어왔다.
- selective `50ms p7 window / 50ms p0 window` schedule에서는 receiver에서 burst/grouped pattern으로 바뀌었다.
- control-path와 test traffic은 selective schedule 상태에서도 유지되었다.

Phase 5 `gPTP integrated Qbv`는 진행 중이다.

- selective schedule과 같은 `eth0` port에서 직접 gPTP를 돌리면 `tx timestamp timeout`으로 불안정했다.
- 대신 `SK eth1 <-> TMDS eth2` direct path로 SK 공통 PHC `/dev/ptp0`를 동기화하는 경로를 시도했다.
- 이 direct path에서는 BMCA와 best master selection, `UNCALIBRATED on RS_SLAVE`까지는 확인했다.
- 또한 PHC 기준 미래 `base-time`으로 selective taprio schedule을 다시 생성하는 경로도 확인했다.
- `taprio` 제거, `switch_mode=false`, PHC epoch 정렬, `tx_timestamp_timeout` 증가를 각각 시도해도 stable `SLAVE`는 재현하지 못했다.
- raw `0x88f7` capture 기준으로는 `Sync/Announce/Pdelay_Req/Resp/Resp_Fup`가 direct path에서 실제 왕복하는 것을 확인했다.
- 재부팅 후 분리 실험으로 `bridge only`는 통과하지만 `bridge + switch_mode`부터 `TMDS stable SLAVE`가 깨지는 것을 확인했다.
- `eth1 mqprio only`를 추가해도 failure signature는 동일해서, 현재 최초 blocker는 `mqprio`보다 `switch_mode` 쪽에 더 가깝다.

Phase A `endpoint egress 우회 경로`는 closeout 되었다.

- closeout matrix:
  - `SK eth0 -> TMDS eth1`: SW/HW taprio 모두 성공, SW/HW + gPTP coexistence 모두 성공
  - `SK eth1 -> TMDS eth2`: SW/HW taprio 모두 성공, SW + gPTP 성공, HW + gPTP partial / unstable
  - `TMDS eth2 -> SK eth1`: SW/HW taprio 모두 성공, SW + gPTP 성공, HW + gPTP fail (`tx timestamp timeout`)
- `TMDS eth1 -> SK eth0`는 현재 TMDS `eth0` control-port 유지 조건 때문에 Phase A closeout 범위에서 제외했다.
- canonical closeout 문서: `docs/phaseA-endpoint-egress-qbv.md`
- canonical replay guide: `docs/phaseA-replay-guide.md`

## Phase 0 결과 요약

- SK baseline 확인:
  - `switch_mode=true`
  - `br-tsn=10.50.0.2/24`
  - `eth0`, `eth1` 모두 `br-tsn` slave + `forwarding`
  - `p0-rx-ptype-rrobin=off`
  - `mqprio ... hw 1 mode channel` on both ports
- TMDS endpoint 재구성:
  - `ep1 eth1.301 = 10.31.0.2/24`
  - `ep2 eth2.301 = 10.31.0.1/24`
  - `eth2.301`에 `egress-qos-map` + `tc skbedit priority` 유지
- wire evidence:
  - sender `eth2`: `vlan 301, p 7` on UDP `5001`
  - receiver `eth1`: `vlan 301, p 7` on UDP `5001`
  - sender `eth2`: `vlan 301, p 6` on UDP `5002`
  - receiver `eth1`: `vlan 301, p 6` on UDP `5002`
- `iperf3`:
  - UDP `5001`: receiver loss `0/1296 (0%)`
  - UDP `5002`: receiver loss `0/864 (0%)`

상세 기록: `docs/2026-06-26_phase0-baseline-revalidation.md`

Phase 1 초기 기록: `docs/2026-06-26_phase1-mqprio-early-findings.md`

Phase 2 기록: `docs/2026-06-26_phase2-cbs-validation.md`

Phase 3 기록: `docs/2026-06-26_phase3-taprio-apply-validation.md`

Phase 4 기록: `docs/2026-06-26_phase4-qbv-effect-validation.md`

Phase 5 기록: `docs/2026-06-26_phase5-gptp-qbv-integration-progress.md`

Phase 5 재부팅 후 분리 기록: `docs/2026-06-29_phase5-gptp-split-state-check.md`

Phase A endpoint 우회 closeout: `docs/phaseA-endpoint-egress-qbv.md`
