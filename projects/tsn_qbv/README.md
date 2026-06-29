# AM64x TSN Qbv Lab

## 목적

이 프로젝트는 `projects/tsn_dscp_pcp`에서 확보한 VLAN PCP marking / preservation 결과를 baseline으로 삼아,
`SK-AM64B` CPSW switchdev 경로에서 `mqprio -> CBS -> taprio/Qbv -> gPTP 연동` 순서로 단계 검증을 진행하기 위한 작업 구역이다.

핵심 목표는 단순 PCP 유지 확인이 아니라,
**PCP 기반 traffic class가 queue 및 gate schedule에 실제로 연결되는지**를 증거 기반으로 확인하는 것이다.

## 기준

- baseline prerequisite project: `projects/tsn_dscp_pcp`
- 상세 로드맵 원문: `am64x_qbv_project_roadmap.md`
- 현재 작업용 요약 로드맵: `docs/roadmap.md`
- 활성 트랙 구분: `docs/tracks.md`
- Phase A canonical closeout: `docs/phaseA-endpoint-egress-qbv.md`
- Phase A replay guide: `docs/phaseA-replay-guide.md`

## 현재 기준

- 현재 canonical 결과 문서는 `docs/phaseA-endpoint-egress-qbv.md`다.
- 날짜가 붙은 여러 문서는 진행 중 증거 로그로만 유지한다.
- 재시험 기준 helper는 다음 3개다.
  - `board/prepare_endpoint_target.sh`
  - `board/apply_taprio.sh`
  - `board/write_gptp_cfg.sh`

## 단계 요약

1. Phase 0: PCP preservation baseline 재현
2. Phase 1: `mqprio` 기반 PCP -> TC / queue mapping 확인
3. Phase 2: `CBS` shaping 확인
4. Phase 3: `taprio` 적용성 및 offload accept/reject 확인
5. Phase 4: Qbv gate schedule 효과 확인
6. Phase 5: gPTP 통합 Qbv 검증

## 핵심 문서

- `docs/phaseA-endpoint-egress-qbv.md`: Phase A closeout single source of truth
- `docs/phaseA-replay-guide.md`: 현재 포트 조합 기준 재시험 절차
- `docs/results.md`: 프로젝트 레벨 요약
- `docs/board-matrix.md`: 포트 역할과 direct pair 정리
- `docs/issues.md`: 재시험 시 주의할 known issue

## 기본 토폴로지

```text
TMDS ep2 / eth2 / ICSSG sender
  -> SK eth1 / CPSW ingress
  -> SK br-tsn / CPSW switchdev
  -> SK eth0 / CPSW egress
  -> TMDS ep1 / eth1 / receiver
```

## 작업 원칙

- SK 위험 runtime 변경은 UART 기준으로 수행한다.
- TMDS는 `ssh root@192.168.0.220` 기준으로 제어한다.
- SK-AM64B에는 별도 control Ethernet 포트가 없고, 보드 제어 기준은 항상 UART다.
- TMDS64EVM의 control 포트는 `eth0`이며, 현재 Qbv 검증 대상 포트는 `eth1`, `eth2`다.
- pass/fail은 가능하면 TMDS sender/final receiver wire capture를 우선 기준으로 판단한다.

## 포트 역할 정리

- SK-AM64B
  - `eth0`: CPSW data/test port
  - `eth1`: CPSW data/test port
  - control plane: UART only
- TMDS64EVM
  - `eth0`: control port (`192.168.0.220`)
  - `eth1`: CPSW data/test port
  - `eth2`: ICSSG data/test port

현재 direct endpoint 검증에 사용하는 물리 직결 페어는 둘이다.

```text
Pair 1: SK eth1 (CPSW) <-> TMDS eth2 (ICSSG)
Pair 2: SK eth0 (CPSW) <-> TMDS eth1 (CPSW)
```

## 현재 판단

- `switch_mode=true` TSN switch 경로는 gPTP blocker 때문에 별도 트랙으로 유지한다.
- `switch_mode=false` endpoint egress Qbv 트랙은 현재 closeout 가능 상태다.
- 재시험과 후속 비교는 `docs/phaseA-endpoint-egress-qbv.md`와 `docs/phaseA-replay-guide.md` 기준으로만 진행한다.
