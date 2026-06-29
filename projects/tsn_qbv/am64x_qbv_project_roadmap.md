# AM64x Qbv Project Roadmap

> Project candidate: `projects/tsn_qbv`
>
> Purpose: `tsn_dscp_pcp` 프로젝트에서 확보한 PCP marking / preservation 기반 위에, SK-AM64B CPSW를 TSN switch candidate로 사용하여 `mqprio -> CBS -> taprio/Qbv` 순서로 단계 검증한다.

---

## 0. 현재 출발점

### 이미 확보한 것

이 로드맵은 기존 `projects/tsn_dscp_pcp` 결과를 baseline으로 삼는다.

확정된 내용:

- SK-AM64B CPSW direct sender는 공식 QoS prerequisite 적용 후 VLAN PCP `p7/p6`를 wire에 emit 가능하다.
- TMDS eth2(ICSSG) sender는 VLAN PCP `p7/p6`를 안정적으로 생성 가능하다.
- `TMDS eth2(ICSSG) -> SK CPSW switchdev -> TMDS eth1` 경로에서 PCP `p7/p6` preservation이 확인되었다.
- SK CPSW switch candidate 구성에서 다음 runtime prerequisite가 중요하다.
  - `p0-rx-ptype-rrobin off`
  - `switch_mode=true`
  - `br-tsn vlan_filtering=1`
  - VLAN tagged forwarding
  - `mqprio hw 1 mode channel`
  - VLAN egress-qos-map
  - `tc skbedit priority`

### Qbv 프로젝트의 최종 목표

```text
TMDS eth2 endpoint
  -> VLAN PCP p7/p6 traffic generation
  -> SK-AM64B CPSW switchdev
  -> PCP -> TC -> TX queue mapping
  -> CBS or taprio/Qbv scheduling
  -> TMDS eth1 receiver observation
```

최종적으로 확인하고 싶은 것은 단순히 PCP가 유지되는지가 아니라, **PCP 기반 traffic class가 시간표 기반 gate schedule에 의해 실제 송신 패턴이 제어되는지**이다.

---

## 1. 프로젝트 구조 제안

```text
projects/tsn_qbv/
├── README.md
├── docs/
│   ├── roadmap.md
│   ├── results.md
│   ├── board-matrix.md
│   ├── issues.md
│   ├── phase0-baseline.md
│   ├── phase1-mqprio-tc-mapping.md
│   ├── phase2-cbs-shaping.md
│   ├── phase3-taprio-software-check.md
│   ├── phase4-qbv-offload.md
│   └── phase5-gptp-integrated-qbv.md
├── board/
│   ├── setup_sk_switchdev_base.sh
│   ├── setup_tmds_netns_endpoints.sh
│   ├── setup_mqprio.sh
│   ├── setup_cbs.sh
│   ├── setup_taprio.sh
│   └── cleanup.sh
└── logs/
    └── YYYY-MM-DD_<test-name>/
```

`tsn_dscp_pcp` 프로젝트는 “PCP를 만들고 보존하는 단계”로 닫고, `tsn_qbv`는 “PCP를 queue/scheduler에 연결하는 단계”부터 시작한다.

---

## 2. Phase 0 — Baseline 재현 및 고정

### 목적

기존 `tsn_dscp_pcp`에서 성공한 환경을 Qbv 프로젝트의 baseline으로 재현한다.

### 진행 내용

- SK는 UART control 기준으로 구성한다.
- TMDS는 SSH control 기준으로 구성한다.
- SK CPSW를 switch candidate로 구성한다.
- TMDS eth2는 sender endpoint, TMDS eth1은 receiver endpoint로 분리한다.
- 가능하면 TMDS에서는 `ep1`, `ep2` network namespace 구성을 유지한다.

Baseline topology:

```text
TMDS ep2 / eth2 / ICSSG sender
  -> SK eth1 / CPSW ingress
  -> SK br-tsn / CPSW switchdev
  -> SK eth0 / CPSW egress
  -> TMDS ep1 / eth1 / CPSW receiver
```

### 확인할 것

- `switch_mode=true`
- `br-tsn vlan_filtering=1`
- `eth0`, `eth1` bridge forwarding
- VLAN 301 tagged membership
- `p0-rx-ptype-rrobin off`
- `mqprio hw 1 mode channel` 적용 가능
- TMDS eth2 sender에서 `vlan 301, p7/p6`
- TMDS eth1 receiver에서 `vlan 301, p7/p6`

### 성공 조건

```text
TMDS eth2 sender: vlan 301, p7/p6
TMDS eth1 receiver: vlan 301, p7/p6
```

### 다음 단계 진입 조건

PCP preservation이 재현되어야 한다. 이 단계가 흔들리면 Qbv/taprio 결과 해석이 불가능하다.

### 산출물

- `docs/phase0-baseline.md`
- `board/setup_sk_switchdev_base.sh`
- `board/setup_tmds_netns_endpoints.sh`
- `logs/<date>_phase0_baseline/`

---

## 3. Phase 1 — mqprio 기반 PCP -> TC / Queue Mapping 확인

### 목적

Qbv 이전에 PCP가 실제 traffic class 또는 TX queue 분리에 연결되는지 확인한다.

Qbv는 queue gate를 시간표로 여닫는 기능이다. 따라서 그 전에 `p7`, `p6`, best-effort traffic이 서로 다른 TC/queue로 분리될 수 있어야 한다.

### 진행 내용

SK egress port 기준으로 `mqprio hw 1 mode channel`을 적용한다.

예상 traffic 분류:

```text
PCP 7 -> high priority TC
PCP 6 -> medium/high priority TC
PCP 0 -> best-effort TC
```

테스트 traffic:

- Flow A: VLAN PCP 7, UDP dport 5001
- Flow B: VLAN PCP 6, UDP dport 5002
- Flow C: VLAN PCP 0 또는 unmarked background, UDP dport 5003

### 확인할 것

- `tc -s qdisc show dev eth0/eth1`
- `ethtool -S eth0/eth1 | grep -Ei "pri|prio|queue|fifo|tx|drop"`
- SK egress capture에서 PCP 유지 여부
- receiver에서 flow별 수신량, loss, jitter

주의: 이전 실험에서 `ethtool -S tx_pri*` counter가 wire PCP와 직관적으로 맞지 않는 경우가 있었다. 따라서 counter만 pass/fail 기준으로 삼지 않는다.

### 성공 조건

최소 성공:

```text
mqprio hw 1 mode channel 적용 성공
p7/p6/p0 traffic이 wire에서 구분되어 유지됨
qdisc 또는 driver statistic에서 traffic class/queue 관련 변화가 관찰됨
```

강한 성공:

```text
p7/p6/p0 traffic이 서로 다른 TC/queue counter 또는 shaping behavior로 분리됨
```

### 다음 단계 진입 조건

- `mqprio` 설정이 안정적으로 적용되어야 한다.
- PCP별 traffic을 재현 가능하게 생성할 수 있어야 한다.
- 최소한 p7/p6/p0 flow를 독립적으로 측정할 수 있어야 한다.

### 실패 시 의심 지점

- `p0-rx-ptype-rrobin`이 다시 on 상태로 돌아감
- `mqprio hw 1` offload reject
- switchdev forwarding 경로와 qdisc 적용 포트 불일치
- 통계 counter 해석 오류
- receiver namespace routing/ARP 문제

### 산출물

- `docs/phase1-mqprio-tc-mapping.md`
- `board/setup_mqprio.sh`
- `logs/<date>_phase1_mqprio/`

---

## 4. Phase 2 — CBS 기반 priority queue shaping 확인

### 목적

Qbv 전에 queue scheduling의 더 단순한 형태인 CBS, Credit-Based Shaper, 를 확인한다.

CBS는 시간표 기반 gate 제어는 아니지만, 특정 traffic class의 bandwidth와 burst 특성을 조절하는 단계다. Qbv보다 원인 분석이 쉽기 때문에 중간 단계로 적합하다.

### 진행 내용

- Phase 1에서 확인한 TC/queue mapping을 유지한다.
- 특정 TC에 CBS qdisc를 적용한다.
- high priority flow와 background flow를 동시에 흘린다.
- CBS 적용 전후의 throughput, jitter, drop, burst pattern을 비교한다.

예상 traffic:

```text
Flow A: PCP 7, latency-sensitive
Flow B: PCP 0, background load
```

### 확인할 것

- CBS qdisc 적용 성공 여부
- `tc -s qdisc show`
- flow별 iperf3 jitter/loss
- receiver tcpdump timestamp 간격
- SK egress port drop/queue counter

### 성공 조건

```text
CBS qdisc 적용 성공
CBS 적용 전후로 target TC traffic의 rate 또는 burst pattern 차이가 관찰됨
background load 중에도 high priority flow의 품질 차이가 관찰됨
```

### 다음 단계 진입 조건

- queue/class 단위 shaping이 재현 가능해야 한다.
- traffic generator와 receiver 측정 방식이 안정적이어야 한다.
- qdisc 설정과 실제 traffic 변화 사이의 인과관계를 설명할 수 있어야 한다.

### 실패 시 의심 지점

- TC/queue mapping이 아직 불안정
- CBS offload 미지원 또는 qdisc 설정 오류
- iperf3 traffic이 충분한 부하를 만들지 못함
- 수신 측 측정 granularity 부족

### 산출물

- `docs/phase2-cbs-shaping.md`
- `board/setup_cbs.sh`
- `logs/<date>_phase2_cbs/`

---

## 5. Phase 3 — taprio/Qbv 사전 적용성 확인

### 목적

Qbv 본실험 전에 Linux `taprio` qdisc 적용 가능 여부와 driver offload 수용 여부를 확인한다.

이 단계에서는 아직 “정확한 시간 제어 효과”를 검증하지 않는다. 먼저 설정이 driver에 accepted 되는지, base-time/cycle-time/gate mask 구성이 가능한지만 확인한다.

### 진행 내용

- 현재 kernel config 확인
  - `CONFIG_NET_SCH_TAPRIO`
  - `CONFIG_TI_AM65_CPSW_TAS`
  - `CONFIG_TI_K3_AM65_CPTS`
- `sch_taprio` module load 확인
- SK egress port에 간단한 taprio schedule 적용
- offload mode 가능 여부 확인
- `dmesg`에서 reject reason 확인

예상 최소 schedule:

```text
cycle-time: 1 ms or 2 ms
window A: TC for PCP 7 open
window B: TC for PCP 0/6 open
```

### 확인할 것

- `tc qdisc replace ... taprio ...` 성공 여부
- `flags` / `txtime-delay` / `base-time` 사용 가능 여부
- hardware offload accepted 여부
- `dmesg | grep -Ei "taprio|tas|est|cpsw|offload"`
- `tc -s qdisc show dev <port>`

### 성공 조건

최소 성공:

```text
taprio qdisc가 적용되고 traffic이 계속 흐름
```

강한 성공:

```text
taprio hardware offload가 accepted 되고 dmesg에 fatal reject가 없음
```

### 다음 단계 진입 조건

- taprio schedule이 적용 가능해야 한다.
- 어떤 clock 기준으로 base-time을 잡는지 정리되어야 한다.
- traffic class와 gate mask의 대응이 문서화되어야 한다.

### 실패 시 의심 지점

- `p0-rx-ptype-rrobin` conflict
- `mqprio`와 `taprio` qdisc 계층 충돌
- hardware offload unsupported mode
- base-time이 과거이거나 PHC 기준이 맞지 않음
- cycle-time / interval이 CPSW EST 제한을 벗어남

### 산출물

- `docs/phase3-taprio-software-check.md`
- `board/setup_taprio.sh`
- `logs/<date>_phase3_taprio_apply/`

---

## 6. Phase 4 — Qbv Gate Schedule 효과 확인

### 목적

실제 Qbv 효과, 즉 gate schedule에 따라 특정 traffic class의 송신 가능 시간이 제한되는지 확인한다.

### 진행 내용

- PCP 7 traffic과 PCP 0 또는 PCP 6 traffic을 동시에 생성한다.
- taprio schedule에서 특정 시간 window에만 특정 TC gate를 open한다.
- receiver에서 packet arrival pattern, burst, loss, jitter를 측정한다.
- gate schedule 변경 전후를 비교한다.

예상 구조:

```text
Cycle 1 ms
  0~200 us: TC high open
  200~1000 us: best-effort open
```

또는 더 관찰하기 쉽게 초기에는 큰 window를 사용한다.

```text
Cycle 100 ms
  0~50 ms: high TC open
  50~100 ms: low TC open
```

초기 검증은 사람이 tcpdump timestamp로 볼 수 있게 큰 cycle을 사용하는 것이 좋다. 이후 점차 실제 TSN에 가까운 짧은 cycle로 줄인다.

### 확인할 것

- receiver tcpdump timestamp pattern
- iperf3 flow별 throughput/loss/jitter
- SK `tc -s qdisc show`
- SK driver/EST/TAS counters 또는 logs
- gate schedule 변경 시 traffic pattern 변화

### 성공 조건

최소 성공:

```text
taprio schedule 변경에 따라 flow별 수신 pattern이 달라짐
```

강한 성공:

```text
PCP/TC별 traffic이 지정된 gate window에서만 송신되는 패턴이 관찰됨
```

### 다음 단계 진입 조건

- schedule 변경과 packet arrival pattern 사이의 관계가 재현 가능해야 한다.
- p7/p6/p0 flow를 분리해서 관찰 가능해야 한다.
- base-time/cycle-time 계산 절차가 문서화되어야 한다.

### 실패 시 의심 지점

- taprio가 software path로만 동작
- hardware offload가 적용되지 않음
- traffic generator가 gate window보다 느림 또는 부하 부족
- receiver timestamp precision 부족
- gPTP/PHC clock 기준 불명확

### 산출물

- `docs/phase4-qbv-offload.md`
- `logs/<date>_phase4_qbv_effect/`

---

## 7. Phase 5 — gPTP 통합 Qbv 검증

### 목적

Qbv를 단독 qdisc 실험에서 끝내지 않고, gPTP 시간 동기화와 연결한다.

Qbv의 본질은 네트워크 전체가 같은 시간 기준을 공유하고, 그 시간 기준으로 gate schedule을 실행하는 것이다. 따라서 최종 단계에서는 gPTP와 taprio/Qbv를 함께 본다.

### 진행 내용

- SK CPSW PHC와 TMDS endpoint PHC의 gPTP 상태 확인
- `ptp4l` 상태 확인
- 필요 시 `phc2sys`는 별도 검토하되, 1차 목표는 PHC 동기화
- taprio base-time을 PHC 기준 미래 시각으로 설정
- gPTP lock 전/후 Qbv behavior 비교

### 확인할 것

- `ptp4l` port state
- master/slave role
- offset/rms/path delay
- `/dev/ptpX` mapping
- taprio base-time 적용 시점
- gate schedule 시작 시점
- receiver timestamp pattern

### 성공 조건

```text
gPTP 동기화 상태에서 taprio/Qbv schedule이 안정적으로 적용되고,
traffic pattern이 schedule에 따라 재현 가능하게 나타남
```

### 다음 단계

이 단계가 성공하면 이후는 실제 application traffic 또는 custom board bring-up 항목으로 넘어간다.

- custom board CPSW pinmux/PHY/DT 반영
- production BSP에서 TSN config 자동화
- boot-time TSN setup service 구성
- application-level DSCP/PCP marking policy 설계

### 산출물

- `docs/phase5-gptp-integrated-qbv.md`
- `logs/<date>_phase5_gptp_qbv/`

---

## 8. 단계별 Go / No-Go 요약

| Phase | 목표 | Go 조건 | No-Go 조건 |
|---|---|---|---|
| Phase 0 | PCP preservation baseline | ICSSG -> SK -> receiver p7/p6 유지 | p0로 재현되거나 topology 불안정 |
| Phase 1 | PCP -> TC/queue mapping | mqprio 적용 및 flow 분리 증거 확보 | mqprio reject 또는 flow 구분 불가 |
| Phase 2 | CBS shaping | CBS 적용 전후 traffic 변화 확인 | qdisc 적용 실패 또는 변화 없음 |
| Phase 3 | taprio 적용성 | taprio 적용 성공, offload/reject 상태 확인 | taprio reject 원인 미해결 |
| Phase 4 | Qbv 효과 | gate schedule에 따른 traffic pattern 변화 | schedule과 traffic 변화 연결 불가 |
| Phase 5 | gPTP 통합 | gPTP 동기화 + Qbv schedule 재현 | clock/base-time 불명확 |

---

## 9. 실험 중 공통 기록 항목

각 phase마다 최소한 아래를 기록한다.

```bash
hostname
uname -a
ip -br link
ip -br addr

devlink dev param show platform/8000000.ethernet
ethtool --show-priv-flags eth0
ethtool --show-priv-flags eth1
ethtool -l eth0
ethtool -l eth1

bridge link
bridge -d vlan show

tc qdisc show dev eth0
tc qdisc show dev eth1
tc -s qdisc show dev eth0
tc -s qdisc show dev eth1

ethtool -S eth0 | grep -Ei "ale|drop|vlan|pri|prio|queue|fifo|tx|rx"
ethtool -S eth1 | grep -Ei "ale|drop|vlan|pri|prio|queue|fifo|tx|rx"

dmesg | grep -Ei "cpsw|taprio|mqprio|cbs|tas|est|offload|vlan|ale" | tail -n 200
```

---

## 10. 현재 단계에서의 판단

### Decision

`tsn_dscp_pcp` 프로젝트는 Qbv 진입 전 prerequisite 확보 프로젝트로 마무리한다.

`tsn_qbv` 프로젝트는 다음 순서로 진행한다.

```text
Phase 0: PCP preservation baseline 재현
Phase 1: mqprio PCP -> TC/queue mapping
Phase 2: CBS shaping
Phase 3: taprio 적용성 확인
Phase 4: Qbv gate schedule 효과 확인
Phase 5: gPTP 통합 Qbv 검증
```

### Assumption

- SK-AM64B CPSW는 Qbv switch candidate로 계속 사용한다.
- TMDS eth2 ICSSG는 PCP-capable sender endpoint로 사용한다.
- TMDS eth1 CPSW는 receiver endpoint로 사용한다.
- SK control은 위험한 runtime 변경 시 UART 기준으로 수행한다.

### Open Question

- SK CPSW switchdev path에서 `mqprio` counter와 실제 wire PCP/queue behavior가 어떻게 연결되는가?
- `taprio`가 현재 kernel/rootfs에서 hardware offload로 accepted 되는가?
- AM64x CPSW EST 제한, cycle-time, interval granularity, base-time 조건은 현재 SDK 기준으로 어느 정도인가?
- gPTP PHC와 taprio base-time 연결을 어떤 방식으로 안정화할 것인가?

### Action Item

1. `projects/tsn_qbv` 디렉토리 생성
2. 이 문서를 `projects/tsn_qbv/docs/roadmap.md`로 저장
3. Phase 0 baseline 재현부터 시작
4. Phase 1에서 `mqprio` mapping 증거 확보
5. Phase 2 이후부터 CBS/taprio/Qbv로 확장

---

## 11. 참고 자료

- TI Processor SDK Linux AM64X TSN with CPSW 문서는 CPSW TSN 테스트가 MAC mode와 SWITCH mode에서 수행되었고, 테스트 setup/script/output을 문서화한다고 설명한다.
- TI Processor SDK Linux CPSW Ethernet 문서는 AM64x CPSW3G가 Linux에서 MAC mode와 Switch mode TSN 기능을 지원한다고 설명한다.
- TI Processor SDK Linux CPSW EST 문서는 CPSW EST/Qbv 구성 전 priority queue mode 전환, round robin mode disable, taprio/EST 관련 조건을 설명한다.
- TI MCU+ SDK EST/TAS 문서는 EST schedule이 여러 time interval로 구성되고, 각 interval의 gate mask가 traffic class queue gate open/close 상태를 정의한다고 설명한다.

