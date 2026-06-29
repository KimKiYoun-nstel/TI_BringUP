# AM64x Qbv Project Roadmap Summary

## 목적

`projects/tsn_dscp_pcp`에서 확보한 PCP emission / preservation 결과를 baseline으로 삼아,
`SK-AM64B` CPSW를 TSN switch candidate로 사용해 `mqprio -> CBS -> taprio/Qbv -> gPTP` 순서로 검증을 진행한다.

현재는 이 원래 로드맵을 유지하되, 실험 트랙을 둘로 분리한다.

- 원래 트랙: `switch_mode=true` TSN switch / gPTP 통합
- 우회 트랙: `switch_mode=false` endpoint egress Qbv

상세 초안과 배경 설명은 `../am64x_qbv_project_roadmap.md`를 원문으로 유지한다.
이 문서는 실제 프로젝트 작업 시작을 위한 요약본이다.

## Baseline

이미 확보한 사실:

- SK CPSW direct sender는 VLAN PCP `p7/p6`를 wire에 emit 가능
- TMDS `eth2` ICSSG sender는 VLAN PCP `p7/p6` 생성 가능
- `TMDS eth2 -> SK switchdev -> TMDS eth1` 경로에서 PCP preservation 확인 완료
- 중요 prerequisite:
  - `p0-rx-ptype-rrobin off`
  - `switch_mode=true`
  - `br-tsn vlan_filtering=1`
  - VLAN tagged forwarding
  - `mqprio hw 1 mode channel`
  - VLAN `egress-qos-map`
  - `tc skbedit priority`

## Phase 순서

1. Phase 0: PCP preservation baseline 재현
2. Phase 1: `mqprio` 기반 PCP -> TC / queue mapping 확인
3. Phase 2: `CBS` shaping 확인
4. Phase 3: `taprio` 적용성 및 offload 상태 확인
5. Phase 4: Qbv gate schedule 효과 확인
6. Phase 5: gPTP 통합 Qbv 검증

## Phase 0 성공 조건

```text
TMDS eth2 sender: vlan 301, p7/p6
TMDS eth1 receiver: vlan 301, p7/p6
```

Phase 0가 흔들리면 이후 `mqprio`/`CBS`/`taprio` 해석이 불가능하므로, Qbv 프로젝트는 이 baseline을 먼저 다시 고정한다.

## 현재 준비 자산

- baseline apply wrapper: `../board/setup_sk_switchdev_base.sh`
- TMDS endpoint namespace wrapper: `../board/setup_tmds_netns_endpoints.sh`
- mqprio helper: `../board/setup_mqprio.sh`
- CBS helper: `../board/setup_cbs.sh`
- taprio helper: `../board/setup_taprio.sh`
- cleanup helper: `../board/cleanup.sh`

## 현재 열린 질문

- SK switchdev path에서 `mqprio` counter와 실제 wire behavior를 어떻게 연결할 것인가?
- `taprio`가 현재 kernel/rootfs에서 hardware offload로 accepted 되는가?
- CPSW EST 제한, cycle-time, interval granularity를 어떤 기준으로 잡을 것인가?
- gPTP PHC와 taprio `base-time` 연결을 어떻게 안정화할 것인가?

## 현재 트랙 운영

- `endpoint egress Qbv` 트랙은 `docs/phaseA-endpoint-egress-qbv.md` 기준으로 계속 진행한다.
- `switch_mode gPTP blocker` 트랙은 `docs/phase5-gptp-integrated-qbv.md`와 `docs/2026-06-29_phase5-gptp-split-state-check.md` 기준으로 분리 유지한다.
