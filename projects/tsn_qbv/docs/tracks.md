# Qbv Active Tracks

## 목적

`tsn_qbv` 프로젝트의 현재 작업을 두 개의 분리된 트랙으로 유지한다.

1. `endpoint egress Qbv` 트랙
2. `switch_mode gPTP blocker` 트랙

둘을 섞어서 해석하면 원인 분리가 무너지므로,
이 문서는 어떤 질문이 어느 트랙에 속하는지 빠르게 판단하기 위한 index다.

## Track 1. Endpoint Egress Qbv

목적:

- `switch_mode=false` direct endpoint path에서
- PCP -> TC/queue -> taprio/Qbv gate effect를 먼저 검증

대표 경로:

- `SK eth1(CPSW sender) -> TMDS eth2(ICSSG receiver)`
- `TMDS eth2(ICSSG sender) -> SK eth1(CPSW receiver)`
- `SK eth0(CPSW sender) -> TMDS eth1(CPSW receiver)`
- `TMDS eth1(CPSW sender) -> SK eth0(CPSW receiver)`

현재 상태:

- 활성 트랙
- 현재 가장 실무적으로 진도가 나는 경로

현재 결론:

- direct 3경로 모두에서 SW/HW taprio egress effect는 확인되었다.
- `SK eth0 -> TMDS eth1`는 SW/HW + gPTP coexistence까지 성공한 reference path다.
- `SK eth1 -> TMDS eth2`는 HW + gPTP가 partial / unstable이다.
- `TMDS eth2 -> SK eth1`는 SW + gPTP는 성공하지만 HW + gPTP는 실패한다.

핵심 기록:

- `docs/phaseA-endpoint-egress-qbv.md`
- `docs/phaseA-replay-guide.md`

관련 helper:

- `board/prepare_endpoint_target.sh`
- `board/apply_taprio.sh`
- `board/write_gptp_cfg.sh`

## Track 2. switch_mode gPTP Blocker

목적:

- `switch_mode=true`에 들어가는 순간 direct gPTP가 왜 stable `SLAVE`로 수렴하지 못하는지 분리

현재 상태:

- blocker 추적 전용 트랙
- endpoint Qbv 진도와 분리 유지 중

현재 결론:

- `bridge only`는 통과
- `switch_mode=true`가 들어가는 시점부터 최초 failure 발생
- `mqprio`, `taprio`, `p0-rx-ptype-rrobin`는 그 이후 secondary condition일 뿐 최초 원인은 아님

핵심 기록:

- `docs/phase5-gptp-integrated-qbv.md`
- `docs/2026-06-29_phase5-gptp-split-state-check.md`

## 사용 기준

다음 질문은 endpoint 트랙으로 본다.

- `taprio가 sender egress packet pattern을 바꾸는가?`
- `gPTP lock 상태에서 endpoint software taprio가 공존하는가?`
- `CPSW <-> CPSW direct pair에서도 hardware taprio가 같은 방식으로 동작하는가?`
- `SK CPSW endpoint를 Qbv sender로 계속 쓸 수 있는가?`

다음 질문은 blocker 트랙으로 본다.

- `switch_mode=true`에서 왜 SLAVE lock이 깨지는가?
- `bridge/ALE/VLAN admission이 gPTP를 막는가?`
- `switchdev path의 CPTS/timestamp path가 깨지는가?`
