# Hardware vs Software Taprio Summary

> Evidence-only note: current canonical summary is `docs/phaseA-endpoint-egress-qbv.md`.

## 목적

현재까지 `tsn_qbv` 프로젝트에서 확보한 결과를 기준으로 hardware `taprio(flags 2)`와 software `taprio(clockid CLOCK_TAI)`의 차이를 정리한다.

## 1. 공통점

- 둘 다 `tc qdisc` 기반으로 sender egress gate schedule을 구성한다.
- 둘 다 `skbedit priority` + VLAN `egress-qos-map`과 결합되어야 wire PCP 결과를 확실히 해석할 수 있다.
- 둘 다 pass/fail은 host-side counter보다 wire capture가 더 중요하다.

## 2. Hardware taprio 특징

### 장점

- 실제 하드웨어 EST/Qbv offload 여부를 직접 검증할 수 있다.
- `tc qdisc show`에 `flags 0x2`가 나타나면 offload acceptance 근거가 명확하다.
- wire capture에서 실제 `p7/p6` delivery와 gate effect를 확인했다.
- `SK eth0 -> TMDS eth1` 경로에서는 gPTP coexistence도 확인했다.

### 제약

- endpoint/driver별 prerequisite 차이가 크다.
- 예:
  - SK CPSW: `p0-rx-ptype-rrobin off`, `TX=3`, `500 us` cycle 가능
  - TMDS ICSSG: `TX=3`, `cycle_time >= 1 ms`, VLAN `egress-qos-map` 필요
  - TMDS CPSW `eth1`: 현재는 TMDS `eth0` control-port 유지 조건 때문에 `p0-rx-ptype-rrobin off` prerequisite를 안전하게 맞추기 어려움
- 긴 interval에서는 fetch RAM budget 때문에 `No fetch RAM`이 발생할 수 있다.
- running schedule 상태에서 traffic mapping 변경이 제한될 수 있다.

## 3. Software taprio 특징

### 장점

- hardware offload prerequisite가 까다로운 포트에서도 상대적으로 유연하게 적용된다.
- long interval, large cycle 실험을 쉽게 할 수 있다.
- direct endpoint 경로에서 `software taprio + gPTP coexistence` 성공 이력이 이미 있다.
- TMDS ICSSG처럼 hardware 제약이 많은 포트에서도 단일 queue 또는 fallback 구성으로 실험을 이어가기 쉽다.

### 제약

- 실제 hardware EST offload인지 여부를 증명하지 못한다.
- host scheduler 영향과 NIC/driver queue gating을 분리하기 어렵다.
- timing effect는 보이더라도, 그것이 hardware gate effect인지 software pacing 영향인지 더 조심해서 해석해야 한다.

## 4. 현재까지의 실무적 결론

### Hardware taprio가 더 적합한 질문

- 이 포트가 실제 hardware Qbv/EST를 지원하는가?
- driver가 요구하는 queue / private flag / minimum cycle 조건은 무엇인가?
- hardware offload accepted 상태에서 wire PCP와 gate effect가 재현되는가?

### Software taprio가 더 적합한 질문

- hardware prerequisite가 아직 정리되지 않은 상태에서 gate concept를 빨리 검증하고 싶은가?
- gPTP와의 공존을 먼저 기능적으로 보고 싶은가?
- long cycle / large interval 실험을 빠르게 바꿔 보고 싶은가?

## 5. 현재 프로젝트 기준 한 줄 요약

```text
software taprio는 빠른 기능 탐색과 공존 실험에 유리하고,
hardware taprio는 실제 EST/Qbv capability와 port별 제약을 확정하는 데 유리하다.
```

## 6. 현재 확정 사실

- `SK eth1(CPSW) -> TMDS eth2(ICSSG)`: hardware taprio success at `500 us`
- `TMDS eth2(ICSSG) -> SK eth1(CPSW)`: hardware taprio success at `1 ms`
- `SK eth0(CPSW) -> TMDS eth1(CPSW)`: hardware taprio success at `500 us`
- `SK eth0(CPSW) -> TMDS eth1(CPSW)`: hardware taprio + gPTP coexistence success
- `SK eth0(CPSW) -> TMDS eth1(CPSW)`: software taprio + gPTP coexistence success
- `SK eth1(CPSW) -> TMDS eth2(ICSSG)`: software taprio + gPTP coexistence success
- `SK eth1(CPSW) -> TMDS eth2(ICSSG)`: hardware taprio + gPTP coexistence는 partial / unstable
- `TMDS eth2(ICSSG) -> SK eth1(CPSW)`: software taprio + gPTP coexistence success
- `TMDS eth2(ICSSG) -> SK eth1(CPSW)`: hardware taprio + gPTP coexistence fail (`tx timestamp timeout`)
- `TMDS eth1(CPSW) -> SK eth0(CPSW)`: 현재 TMDS control-port model 때문에 hardware taprio blocked
- `switch_mode=false` direct path에서는 software taprio + gPTP coexistence success 이력 존재
