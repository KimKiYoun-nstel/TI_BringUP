# AM64x TSN DSCP PCP Lab

## 목적

이 프로젝트는 `SK-AM64B`를 TSN switch candidate로, `TMDS64EVM`을 control + dual endpoint로 두고
DSCP/PCP 확인을 위한 사전 환경 구성과 후속 실험을 관리하기 위한 작업 구역이다.

현재 단계의 1차 목표는 다음이다.

- `TMDS eth0` control 경로 유지
- `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1` 구성 확인
- `TMDS -> SK` 제어 경로 확보
- `SK` Linux bridge 기반 L2 forwarding 환경 구성
- 이후 DSCP/PCP 실험을 위한 기준 topology 정리

## 기준 문서

- `.agents/am64x_sk_tsn_switch_tmds_endpoint_env_setup.md`

## 문서

- `docs/plan.md`: 환경 구성 목표와 진행 순서
- `docs/board-matrix.md`: 포트 역할, PHC, 현재 토폴로지
- `docs/results.md`: 확인 결과와 판정
- `docs/issues.md`: 실패/주의사항 기록
- `docs/2026-06-25_dscp-pcp-level1-6.md`: DSCP/PCP/qdisc/scheduler readiness 확인 결과
- `docs/2026-06-25_vlan-pcp-dscp-mapping-investigation.md`: TI SDK reference 기반 VLAN PCP emission 조사 보고서
- `docs/2026-06-26_am64x-cpsw-qos-runtime-prerequisite-validation.md`: CPSW QoS prerequisite 적용 후 direct sender / switchdev forwarding 검증 보고서
- `docs/2026-06-26_testB-revalidation.md`: Test B 재검증 기록
- `docs/2026-06-26_testb-replay-guide.md`: 언제든지 다시 시험할 수 있는 재현 가이드

## 적용 자산

- host-side one-shot apply:
  - `board/apply_tsn_env.sh`
- Test B TMDS namespace/helper:
  - `board/setup_testb_tmds_netns.sh`
- persistent rootfs overlay:
  - `rootfs/overlays/tmds64evm-tsn-dscp-pcp/`
  - `rootfs/overlays/sk-am64b-tsn-dscp-pcp/`

이 프로젝트의 network topology는

- live rootfs에 설치되는 `systemd-networkd` 파일
- 보드 내부 `/usr/local/sbin/ti-tsn-dscp-pcp-*.sh` apply script
- host에서 실행하는 `board/apply_tsn_env.sh`

조합으로 관리한다.

## 현재 가정

- `TMDS eth0`는 office/control 네트워크를 유지한다.
- Host는 `TMDS eth0`로 접속하고, SK는 TMDS를 jump host로 사용해 접근한다.
- `SK eth0`, `SK eth1`은 같은 CPSW PHC `/dev/ptp0`를 공유하는 switch candidate port다.
- `TMDS eth1`은 CPSW endpoint, `TMDS eth2`는 ICSSG endpoint 후보다.

## 현재 상태

- 물리 연결은 `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1`로 정리했다.
- `TMDS eth0`는 `192.168.0.220/24` control port로 유지했다.
- SK direct host SSH는 현재 불가하며, 최종 제어 경로는 `Host -> TMDS -> SK`로 확보했다.
- bootstrap 단계에서는 SK reachable IP가 없어서 UART로 `eth0` 임시 IP를 부여한 뒤 TMDS 경유 SSH를 열었다.
- 현재 SK는 `br-tsn` Linux bridge를 사용하고, control IP는 `br-tsn`에 `10.50.0.2/24`로 올려 두었다.
- 현재 TMDS는 `eth1 = 10.50.0.1/24`, `eth2 = no IP` 상태로 endpoint/control test용으로 둔다.

## 현재 결론

- `RX_REMAP_VLAN` patch 부재가 핵심 문제는 아니었다. 이 patch는 local TI SDK 12 source에 이미 포함되어 있었다.
- direct sender에서 계속 `p0`가 보였던 핵심 이유는 source patch 누락보다 **runtime QoS prerequisite 미충족** 쪽이었다.
- 실제로 다음 조건을 맞추자 SK CPSW direct sender는 실제 wire에 `vlan p7/p6`를 emit했다.
  - `p0-rx-ptype-rrobin off`
  - `mqprio hw 1 mode channel`
  - VLAN subinterface `egress-qos-map`
  - `tc skbedit priority`
- 같은 구성 계열에서 `TMDS eth2(ICSSG)`가 만든 `p7/p6`는 `SK switchdev`를 지나 `TMDS eth1` final receiver에서도 유지되었다.
- 즉 현재까지의 1차 결론은 **SK-AM64B CPSW를 switch candidate처럼 사용하면서 PCP-preserving forwarding을 확인했다**는 것이다.
- 다만 SK local `tcpdump -i eth0/eth1`는 switchdev hardware offload 상태에서 `0 packets captured`로 남아, SK 내부 포트의 host-side packet visibility는 별도 한계로 남는다.

## 확보한 TSN 목표

이번 단계에서 확보한 것은 다음과 같다.

1. `802.1Q VLAN PCP`를 endpoint에서 의도적으로 주입할 수 있다.
2. SK-AM64B CPSW를 `switch_mode=true` 기반의 L2 switch candidate로 운용할 수 있다.
3. ICSSG endpoint가 넣은 PCP를 SK를 거쳐 다른 endpoint까지 보존시키는 forwarding 경로를 확보했다.
4. 이후 `mqprio`, `CBS`, `taprio`, TSN class separation, queue mapping 검증을 **PCP 기반**으로 진행할 수 있다.

주의:

- 이번 완료는 `PCP emission/preservation` 기준의 1차 완료다.
- 아직 `gPTP/802.1AS`, `802.1Qbv time-aware schedule`, strict TSN conformance 전체를 끝낸 것은 아니다.

## Persistence 정리

- 처음 구성은 runtime `ip` 명령으로 bootstrap 했다.
- 이후에는 두 보드의 live rootfs에 `systemd-networkd` persistent 파일을 설치했다.
- 따라서 다음부터는 **reboot 때마다 수동으로 bridge/IP를 다시 입력하는 구조가 아니라**, rootfs에 들어간 network profile이 자동 적용되는 형태다.
- TMDS는 boot 직후 `eth1`이 잠깐 `DOWN/NO-CARRIER`로 보일 수 있어 boot-time re-apply service를 추가했다.
- 이 service가 실행된 뒤 `eth1 = 10.50.0.1/24`, `eth2 = up`, `Host -> TMDS -> SK` 경로가 다시 복구되는 것까지 확인했다.
- 또한 같은 상태를 즉시 재적용하려면 host에서 다음 스크립트를 실행하면 된다.

```bash
bash projects/tsn_dscp_pcp/board/apply_tsn_env.sh
```
