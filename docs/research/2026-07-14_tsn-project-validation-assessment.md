# AM64x TSN 프로젝트 검증 상태 및 자동화 정보 수집

## 목적

이 문서는 `SK-AM64B`와 `TMDS64EVM` 두 보드에서 수행한 gPTP, DSCP/PCP,
Qbv, Qbu 프로젝트를 검토하여 다음을 구분한다.

- 현재 증적으로 검증되었다고 말할 수 있는 기능 범위
- 아직 미검증 또는 실패로 남은 범위
- 자동 재검증을 구성하기 위해 고정해야 할 입력, 절차, pass/fail 증거
- 프로젝트 전체를 close할 수 있는지 여부

판정은 과거 문서의 선언만 따르지 않고, repo에 관리되는 raw log, curated evidence,
replay procedure, helper script의 존재 여부를 함께 반영한다.

## 공통 시험 환경

| 항목 | 기준 |
|---|---|
| 보드 | `SK-AM64B`, `TMDS64EVM` |
| SK 제어 | UART (`tools/uart`의 `sk` target) |
| TMDS 제어 | control port `eth0`, 기본 `root@192.168.0.220`; 필요 시 UART |
| 증적 보관 | run별 command, stdout/stderr, `tcpdump`/`ptp4l`, before/after counter, kernel/DTB/rootfs identity |
| 재시험 원칙 | 기존 TSN runtime state를 명시적으로 제거하거나 기능별 baseline을 적용한 뒤 시험 |

현재 board profile은 SK를 UART-only 관리 대상으로 정의한다. 따라서 host에서 SK SSH가
가능하다는 가정을 자동화의 필수 조건으로 두면 안 된다.

## 종합 판정

| 기능 | 검증된 최소 범위 | 증적 수준 | 자동 재검증 준비도 | 프로젝트 close 판정 |
|---|---|---|---|---|
| gPTP | direct `SK eth1 <-> TMDS eth2` L2/P2P/HW timestamp 동기화와 path delay | 문서화된 성공 결과는 충분하나 canonical raw `SLAVE`/`phc2sys` bundle 부재 | 낮음 | 조건부 1차 완료, 전체 close 불가 |
| DSCP/PCP | endpoint PCP injection 및 `TMDS eth2 -> SK switchdev -> TMDS eth1` PCP 보존 | sender/final receiver 값과 CPSW counter가 문서화됨, raw capture 보관은 불완전 | 중간 | PCP emission/preservation 범위 close 가능 |
| Qbv | `switch_mode=false` direct endpoint egress의 SW/HW taprio; CPSW reference path의 HW+gPTP coexistence | helper, raw pcap, raw `ptp4l`, canonical matrix 보유 | 중간 | Phase A만 close, 프로젝트 전체 close 불가 |
| Qbu | CPSW MAC Merge/IET actual fragment/reassembly: TMDS sender 1 Gbps, SK sender 100 Mbps | counter delta ledger는 강함, raw before/after archive 및 reproducible image provenance 부족 | 중간 이하 | close 불가 |

## 1. gPTP

### 확정된 범위

- canonical topology: `SK eth1 <-> TMDS eth2` direct cable.
- L2 transport, P2P delay mechanism, hardware timestamp를 사용한다.
- 프로젝트 결과 문서는 `MASTER -> UNCALIBRATED -> SLAVE`, 안정화된 RMS/delay,
  `phc2sys` system-clock 동기화를 1차 성공으로 기록한다.
- local L2 switch 경유 시험은 frame/BMCA까지만 확인되었으며 stable `SLAVE`에는
  도달하지 못했다. 이는 성공 경로에 포함하면 안 된다.

### 증적 및 결손

- `projects/am64x-gptp-eth1-lab/logs/`에는 다수의 BMCA/path-delay 실험 로그가 있다.
- 그러나 현재 canonical direct path의 stable `SLAVE`, 안정 RMS/delay, `phc2sys`
  전후 offset을 한 run 디렉터리에 함께 보관한 raw evidence bundle은 확인되지 않았다.
- `docs/results.md`의 이전 `eth1 <-> eth1` 서술은 최신 canonical `SK eth1 <-> TMDS eth2`
  와 다르므로 자동화 입력으로 사용하면 안 된다. `docs/plan.md`와 `docs/board-matrix.md`
  를 canonical topology로 사용한다.

### 자동화 입력과 판정

1. 양쪽 link up, 1 Gbps/full duplex, `ethtool -T` hardware timestamp를 저장한다.
2. TMDS `eth2`를 up하고, MASTER 후보 SK의 PHC epoch를 `CLOCK_REALTIME`과 비교한다.
3. 동일한 gPTP config로 양쪽 `ptp4l -m`을 실행하고 전체 로그를 저장한다.
4. TMDS에서 `UNCALIBRATED -> SLAVE`와 안정 RMS/delay를 wait condition으로 판정한다.
5. `phc2sys -s eth2 -c CLOCK_REALTIME -O 0 -m`의 pre/post offset을 저장한다.
6. `tcpdump ... ether proto 0x88f7` pcap 또는 text capture를 함께 저장한다.

pass는 stable `SLAVE`, 안정 path delay, `phc2sys` offset 수렴 및 PTP L2 frame 관측이다.
local switch path는 별도 expected-fail/diagnostic scenario로 관리한다.

### 종료 판정

direct two-board gPTP의 기능 범위는 1차 완료다. raw certificate와 실행 helper가 없고
switch-forwarded gPTP가 실패 상태이므로 프로젝트 전체를 closed로 처리하면 안 된다.

## 2. DSCP/PCP

### 확정된 범위

- topology: `TMDS eth2` (ICSSG sender) -> `SK eth1` ingress -> SK CPSW switchdev/
  `br-tsn` -> `SK eth0` egress -> `TMDS eth1` receiver.
- VID `301`, UDP `5001 -> PCP 7`, UDP `5002 -> PCP 6`을 기준으로 한다.
- sender와 final receiver에서 `vlan 301, p 7/p 6`가 관측됐다.
- SK의 `p0-rx-ptype-rrobin off`, 양 port의 `mqprio hw 1 mode channel`, VLAN
  `egress-qos-map`, `tc skbedit priority`가 필수 runtime prerequisite다.

### 자동화 자산과 결손

- `board/apply_tsn_env.sh`는 overlay deploy, networkd apply, TMDS 경유 SK reconnect를 수행한다.
- `board/setup_testb_tmds_netns.sh`는 TMDS namespace, VLAN, QoS map, filters, receiver를 구성한다.
- SK switchdev/QoS setup은 replay guide의 UART command block으로만 존재한다. host/UART 실행,
  state validation, capture 시작/종료, 결과 archive를 묶은 runner는 없다.
- final receiver raw capture가 `logs/`에 독립 certificate로 보관되지 않아, 다음 run부터는
  sender와 final receiver의 raw output을 동일 run ID 아래에 저장해야 한다.

### 자동화 pass/fail

- pass: sender와 final receiver 모두 PCP 7 및 6을 관측한다.
- invalid: sender부터 PCP 0이면 endpoint VLAN QoS map/filter 설정 실패다.
- fail: sender는 PCP 7/6인데 final receiver가 PCP 0이면 forwarding path 문제다.
- SK local tcpdump가 비어 있어도 offloaded forwarding에서 알려진 관측 한계이므로 단독 fail이 아니다.

### 종료 판정

PCP emission 및 priority-preserving forwarding 범위는 close 가능하다. DSCP-to-PCP
priority effect, queue scheduling, gPTP/Qbv conformance는 이 프로젝트의 성공 주장에 포함되지 않는다.

## 3. Qbv

### 확정된 범위

- Phase A는 `switch_mode=false` direct endpoint egress 전용 closeout이다.
- reference path `SK eth0 -> TMDS eth1`은 SW/HW taprio와 SW/HW+gPTP coexistence가 성공했다.
- `SK eth1 -> TMDS eth2`는 HW+gPTP coexistence가 partial/unstable이다.
- `TMDS eth2 -> SK eth1`은 HW+gPTP coexistence가 `tx timestamp timeout`으로 실패한다.
- `switch_mode=true` TSN switch path의 gPTP convergence blocker와 Phase B strong timing proof는
  미해결이다.

### 자동화 자산과 결손

- target-local helper `prepare_endpoint_target.sh`, `apply_taprio.sh`, `write_gptp_cfg.sh`가 있다.
- replay guide는 command template, topology, expected result, pass/fail signature를 갖춘다.
- helper는 target에 배포되어 있다는 가정을 하지 않으므로 host deploy와 two-board orchestration이 필요하다.
- `apply_taprio.sh`는 qdisc 적용 결과만 출력한다. `flags 0x2`, traffic/capture,
  `ptp4l` health, dmesg 검증과 run archive는 상위 runner가 수행해야 한다.
- Phase B는 B4/B5 strong proof가 없어 closeout 보류다. Phase A runner와 Phase B timing runner를
  같은 pass 기준으로 합치면 안 된다.

### 자동화 pass/fail

- HW pass: `tc -s qdisc`의 `flags 0x2`, intended PCP receiver capture, traffic success를 모두 만족한다.
- SW pass: `clockid TAI`, intended PCP receiver capture, traffic success를 모두 만족한다.
- coexistence pass: traffic 중 stable `SLAVE`와 `FAULTY`, tx timestamp timeout,
  Pdelay failure 부재를 만족한다.
- CPSW reference path만 hardware-Qbv regression baseline으로 우선 자동화한다.

### 종료 판정

Phase A endpoint egress Qbv는 close 가능하다. Qbv 전체, time-aware bridge, switch-mode path,
Phase B strong timing claim은 close 불가다.

## 4. Qbu

### 확정된 범위

- actual Qbu 판정은 MAC Merge/IET sender fragment와 receiver reassembly counter의 동일
  traffic-window delta를 사용한다.
- TMDS CPSW sender -> SK CPSW receiver, 1 Gbps direct path에서 두 receiver port에 대해
  fragment/reassembly가 반복 확인됐다.
- SK CPSW sender -> TMDS CPSW receiver는 100 Mbps에서 actual Qbu가 확인됐다.
- SK sender 1 Gbps는 hardware failure가 아니라 current single-CPU userspace generator가
  overlap을 만들지 못했을 가능성으로 미판정이다.

### 자동화 자산과 결손

- `REPRODUCTION.md`에 canonical TMDS sender 1 Gbps procedure와 strict counter acceptance rule이 있다.
- Qbu 전용 executable runner는 없고, clean-baseline rootfs script도 target에 배포하는 host-side
  apply flow가 없다.
- baseline script는 network profile을 `.qbu-disabled`로 영구 변경하므로 restore/deploy policy를
  runner에 명시해야 한다.
- evidence ledger는 curated delta만 보관한다. historical raw before/after `show-mm`, stats,
  qdisc/filter, traffic stdout bundle은 없다.
- historical image는 `-dirty`이며 source diff/build provenance가 없다. hash는 비교 기준으로
  사용할 수 있지만 reproducible source artifact는 아니다.

### 자동화 pass/fail

- pass: sender fragment delta > 0, receiver fragment 및 reassembly success delta > 0,
  traffic/filter/priority counter 증가, error counter가 success를 지배하지 않음을 한 window에서 확인한다.
- invalid: image/DTB hash mismatch, TX queue != 4, sender `TX active` off, traffic/filter delta 없음이다.
- SK 1 Gbps는 `pktgen` 또는 동등한 kernel-level overlap generator가 준비되기 전까지
  regression pass target으로 두지 않는다.

### 종료 판정

Qbu control plane과 일부 CPSW dataplane은 검증됐지만 프로젝트 close 조건은 미충족이다.
최소한 canonical TMDS sender raw certificate 재수집, clean baseline deploy/reboot evidence,
SK 1 Gbps 범위 결정, Pair A verify-on 및 ICSSG sender의 scope 결정을 완료해야 한다.

## 자동 재검증 구현 전 필수 공통 계약

1. 기능별 baseline/apply/restore를 분리하고, 이전 기능의 bridge, VLAN, qdisc, MAC Merge,
   networkd service가 남아 있으면 run을 invalid로 처리한다.
2. board profile과 실제 link mapping을 run 시작 시 확인한다. 특히 gPTP canonical TMDS port는 `eth2`다.
3. UART와 SSH 명령 모두 timeout, exit status, full output을 run ID별 디렉터리에 저장한다.
4. kernel release, Image/DTB SHA-256, boot ID, rootfs baseline version, interface driver/PHY/link,
   command line을 manifest로 저장한다.
5. 기능별 raw evidence를 pass/fail parser의 입력으로 정한다. 문서 요약이나 단일 control-plane
   success만으로 pass 처리하지 않는다.
6. destructive 또는 persistent rootfs/network 변경에는 명시적인 restore step과 pre-existing
   file backup을 포함한다.

## 우선 구현 순서

1. gPTP direct certificate runner: 가장 적은 runtime mutation으로 two-board UART/SSH orchestration과
   evidence archive 형식을 먼저 확정한다.
2. DSCP/PCP Test B runner: existing TMDS helper와 SK UART command block을 결합하고 양 endpoint
   capture를 archive한다.
3. Qbv Phase A CPSW reference runner: `SK eth0 -> TMDS eth1` HW taprio + gPTP coexistence만
   regression baseline으로 자동화한다.
4. Qbu canonical TMDS sender runner: clean baseline deploy/reboot, TX=4, before/after counter,
   raw archive를 구현한다. SK 1 Gbps는 별도 experimental scenario로 유지한다.
