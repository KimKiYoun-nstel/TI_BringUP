# AM64x TSN Qbu Lab

## 목적

이 프로젝트는 `SK-AM64B`와 `TMDS64EVM`의 현재 직결 포트 조합을 기준으로
IEEE 802.1Qbu frame preemption 검증을 수행하기 위한 작업 구역이다.

이번 프로젝트의 1차 목표는 다음 3가지를 분리해서 확인하는 것이다.

1. 현재 보드/포트 조합이 Qbu 실험 대상으로 적합한가
2. Linux driver/iproute2/ethtool 경로가 MAC Merge와 preemptible TC를 제어할 수 있는가
3. 어떤 포트 조합을 baseline으로 먼저 검증할 것인가

## 기준 문서

- 현재 검증 결론과 다음 작업: `docs/VALIDATION_STATUS.md`
- clean base와 최소 보드 상태: `docs/CLEAN_BASE_CONTRACT.md`
- 재현 절차: `docs/REPRODUCTION.md`
- kernel/DTB/rootfs provenance: `docs/PROVENANCE.md`
- project close 조건: `docs/CLOSURE_CHECKLIST.md`
- validation counter evidence: `logs/2026-07-13_validation_evidence_ledger.md`
- 현재 포트 역할: `docs/board-matrix.md`
- rootfs clean baseline: `docs/baseline.md`
- TI 공식 예제 reference: `am64x_qbu_official_example_validation_guide.md`

## 현재 시작점

- SK-AM64B
  - `eth0`, `eth1`: 둘 다 `CPSW3G` (`am65-cpsw-nuss`)
  - control plane: UART
- TMDS64EVM
  - `eth0`: `CPSW3G` control port
  - `eth1`: `CPSW3G` data/test port
  - `eth2`: `ICSSG` (`icssg-prueth`) data/test port

## 현재 우선 포트 조합

```text
Canonical: SK eth1 (CPSW) <-> TMDS eth1 (CPSW)
Comparative: SK eth0 (CPSW) <-> TMDS eth2 (ICSSG)
```

초기 Pair A candidate는 배선 재확인 전의 가정이었다.

현재 canonical path 선택 이유:

- 양 끝이 모두 CPSW라서 driver 차이를 줄일 수 있다.
- 두 포트 모두 `ethtool --show-mm`와 CPSW IET stats가 확인된다.
- clean baseline에서 TSN overlay IP/서비스 간섭은 제거했다.

comparative path는 2차 후보로 유지한다.

이유:

- 현재 물리 직결 페어로 살아 있다.
- ICSSG 쪽 `eth2`에서도 `ethtool --show-mm`가 동작한다.
- 하지만 이 조합은 CPSW/ICSSG 혼합 경로이며, 현재 `eth2` MAC Merge 상태가 이미 비기본값(`pMAC enabled: on`)이라 초기 reset 기준을 먼저 고정해야 한다.

## 작업 원칙

- SK control은 항상 UART 기준으로 진행한다.
- TMDS control은 `eth0` 또는 UART로 진행한다.
- Qbu readiness 확인 단계에서는 기존 TSN overlay/service 영향과 residual MM 상태를 먼저 제거한다.
- pass/fail은 가능하면 다음 3개 증거를 함께 남긴다.
  - `ethtool --show-mm`
  - `tc qdisc show`
  - `ethtool -S`의 IET/MM 관련 counter

## 현재 요약

- TMDS `eth1` sender의 actual Qbu fragment/reassembly는 SK receiver 두 port에서 반복 확인됐다.
- SK sender의 actual Qbu는 100 Mbps에서는 확인됐다.
- SK sender 1 Gbps 결과는 hardware/spec failure가 아니라, current userspace generator가
  overlap을 충분히 만들었는지 아직 입증하지 못한 상태다.
- Qbu feature에는 custom kernel/DTB/rootfs image 변경이 필요하지 않으며, clean rootfs baseline과
  runtime 설정으로 시험한다. TI SDK prebuilt image의 actual certificate는 별도 미취득 상태다.
- 상세 결론과 다음 검증은 `docs/VALIDATION_STATUS.md`를 따른다.
