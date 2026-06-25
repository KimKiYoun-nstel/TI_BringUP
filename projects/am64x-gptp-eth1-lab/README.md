# AM64x gPTP eth1 Lab

## 목적

이 프로젝트는 `SK-AM64B`와 `TMDS64EVM` 사이의 gPTP 실험을
실험 단위로 관리하기 위한 작업 구역이다.

현재 기준의 canonical direct 경로는 다음이다.

- `SK-AM64B eth1 <-> TMDS64EVM eth2`

이 프로젝트의 범위는 다음을 포함한다.

- direct link 상태 확인
- CPSW/ICSSG 기반 hardware timestamp 경로 확인
- `ptp4l` MASTER/SLAVE 상태 전이 확인
- `phc2sys` 기반 system clock 동기화 확인
- `ether proto 0x88f7` L2 PTP frame 관찰
- local L2 switch 경유 시 gPTP 형상 성립 여부 비교

## 참여 보드

- `sk-am64b`
- `tmds64evm`

상세 접속 프로필은 다음을 우선 기준으로 본다.

- `board/sk-am64b/profile.yaml`
- `board/tmds64evm/profile.yaml`

## 문서

- `docs/plan.md`: 실험 목표와 진행 순서
- `docs/board-matrix.md`: 관리 IP, 현재 배선, 역할 표
- `docs/results.md`: 현재까지 확인된 결과 요약
- `docs/2026-06-24_pairwise-2x3-over-switch.md`: local L2 switch 경유 pairwise 결과
- `docs/2026-06-25_phc-external-pulse-runtime-check.md`: PHC external pulse runtime 점검 결과

## 현재 관찰된 핵심 사항

- 관리용 SSH는 `eth0` IP로 접근한다.
- direct 경로 `SK eth1 <-> TMDS eth2`에서는 stable `SLAVE`와 path delay 측정이 가능했다.
- local L2 switch 경유에서는 `0x88f7` frame 송수신과 BMCA는 보였지만 stable `SLAVE`까지는 내려가지 않았다.
- 현재 배선은 `SK eth0`, `TMDS eth0`를 control port로 유지하고 `SK eth1 <-> TMDS eth2`를 직결한다.
- `TMDS eth0`, `TMDS eth1`은 local L2에 연결된 상태를 유지한다.
- TMDS64EVM은 실험 전 `ip link set eth2 up` 여부를 확인한다.
- `phc2sys` 검증 전 MASTER 측 PHC epoch가 wall clock와 맞는지 확인해야 한다.
- external pulse 관점에서는 TMDS `eth2 -> /dev/ptp2`가 runtime capability와 pinmux 기준으로 가장 유망하다.
- SK `eth1 -> /dev/ptp0`도 perout/PPS capability는 있으나 현재 booted image에서는 output pinmux가 활성화되지 않았다.

## 마감 정리

- gPTP direct 동기화와 path delay 측정 경로는 확보했다.
- local L2 switch 경유에서는 gPTP frame 교환과 BMCA까지는 보이지만 stable `SLAVE`는 재현하지 못했다.
- PHC external pulse는 Linux runtime 기준으로 capability를 확인했다.
- 즉 하드웨어/PHC 측면의 가능성은 확인했지만, 실제 scope 측정을 바로 수행할 수 있을 정도로 board-level probe point와 booted image pinmux까지 완전히 정리된 상태는 아니다.
