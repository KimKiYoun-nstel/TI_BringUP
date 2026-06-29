# 2026-06-26 Phase 1 mqprio Early Findings

## 목적

Phase 1에 들어가기 전에,
현재 baseline `mqprio` 구성이 실제로 `p0/p6/p7`을 서로 다른 TC로 분리할 수 있는지와
candidate map을 live 상태에서 적용할 수 있는지를 먼저 확인했다.

## 확인 1: baseline map 제약

현재 SK baseline `eth0`, `eth1`는 다음 `mqprio` map을 사용하고 있었다.

```text
2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2
```

이 map은 priority `0`, `6`, `7`을 모두 `TC 2`로 보낸다.

즉 이 구성은 Phase 0 PCP preservation prerequisite에는 유효했지만,
Phase 1의 핵심 질문인 `p0/p6/p7` queue/class separation을 검증하는 map은 아니다.

## 확인 2: candidate map apply 방식

Phase 1용 후보로 다음 map을 잡았다.

```text
0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0
```

의도:

- `p0 -> TC0`
- `p6 -> TC1`
- `p7 -> TC2`

처음에는 다음처럼 `replace`를 시도했다.

```bash
tc qdisc replace dev eth0 root handle 100: mqprio \
  num_tc 3 map 0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 hw 1 mode channel
```

결과:

```text
Error: Change operation not supported by specified qdisc.
```

하지만 다음 방식은 `eth0`에서 accept 되었다.

```bash
tc qdisc del dev eth0 root
tc qdisc add dev eth0 root handle 100: mqprio \
  num_tc 3 map 0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 hw 1 mode channel
```

즉 이 드라이버/runtime 조합에서는 Phase 1 map 전환 시 `replace`보다 `del -> add`를 우선 고려해야 한다.

## 확인 3: candidate map 상태의 wire evidence

candidate map을 `eth0`에 적용한 상태에서 TMDS receiver capture를 다시 확인했다.

UDP `5001`:

```text
vlan 301, p 7
10.31.0.1.40738 > 10.31.0.2.5001
```

UDP `5002`:

```text
vlan 301, p 6
10.31.0.1.54747 > 10.31.0.2.5002
```

UDP `5003`:

```text
vlan 301, p 0
10.31.0.1.55428 > 10.31.0.2.5003
```

즉 candidate map 상태에서 receiver wire 기준 `p7`, `p6`, `p0` 세 flow를 모두 다시 구분해서 관찰할 수 있었다.

## 확인 4: qdisc/class 통계 한계

같은 상태에서 `tc -s qdisc show dev eth0`와 `tc -s class show dev eth0`를 확인했지만,
traffic 이후에도 모두 다음처럼 남았다.

```text
Sent 0 bytes 0 pkt
```

즉 switchdev forwarding egress 경로에서 이번 관측만으로는
Linux qdisc/class 통계를 queue separation pass/fail 근거로 쓰기 어렵다.

## 확인 5: driver counter의 coarse signal

같은 구간에서 `ethtool -S eth0`를 비교했다.

변화:

- `tx_good_frames`: `20092 -> 20658` (`+566`)
- `tx_octets`: `29574412 -> 30356791` (`+782379`)
- `tx_pri0`: `20090 -> 20656` (`+566`)
- `tx_pri2`: `2 -> 2` (변화 없음)
- `tx_pri6`: `0 -> 0`
- `tx_pri7`: `0 -> 0`

이 결과는 적어도 `eth0` egress에서 frame/octet level traffic 증가는 보여주지만,
priority queue separation을 직접 설명하는 counter로는 해석하기 어렵다.

## 확인 6: host-originated control path에서 class separation 재현

switchdev forwarding 경로에서는 `tc -s qdisc`와 `tc -s class`가 `0 pkt`로 남아,
Phase 1 판정 기준으로 쓰기 어려웠다.

그래서 현재 live Phase 0 topology는 유지한 채,
SK 내부에 `br-tsn.301` sender를 추가한 control experiment를 수행했다.

설정:

- `br-tsn.301 = 10.31.0.3/24`
- `eth0` candidate map:

```text
map 0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0
queues 1@0 1@1 1@2
```

- `br-tsn.301` egress filter:
  - UDP `5001` -> `skbedit priority 7`
  - UDP `5002` -> `skbedit priority 6`
  - UDP `5003` -> no filter, default `p0`

이 경로에서는 `tc -s class show dev eth0`가 실제로 증가했다.

### p7 flow

UDP `5001`만 송신했을 때:

```text
class mqprio 100:3 parent 100:ffe2
Sent 517004 bytes 361 pkt
```

즉 `p7 -> TC2 -> class 100:3`로 관찰되었다.

### p6 flow

UDP `5002`만 송신했을 때:

```text
class mqprio 100:2 parent 100:ffe1
Sent 516987 bytes 361 pkt
```

즉 `p6 -> TC1 -> class 100:2`로 관찰되었다.

### p0 flow

UDP `5003`만 송신했을 때:

```text
class mqprio 100:1 parent 100:ffe0
Sent 516986 bytes 361 pkt
```

즉 `p0 -> TC0 -> class 100:1`로 관찰되었다.

## 확인 7: hardware register evidence

`ethtool -d eth0` register dump에서 다음을 직접 확인했다.

- baseline map state:

```text
00022018:reg(00002210)
```

- candidate map state:

```text
00022018:reg(00000210)
```

driver source 기준 이 register는 `AM65_CPSW_PN_REG_TX_PRI_MAP`이며,
`am65_cpsw_setup_mqprio()`가 실제 hardware port mapping을 이 값으로 프로그램한다.

즉 candidate `mqprio` map은 단순 userspace accepted 상태가 아니라,
port register 레벨에서도 실제 반영된 것이 확인되었다.

## Phase 1 판정 기준 초안

현재까지의 관측을 기준으로, switchdev forwarding 기반 Phase 1은 다음처럼 판정하는 것이 안전하다.

### 확정 근거로 쓸 수 있는 것

1. candidate `mqprio` map이 실제로 accept 되는지
   - 현재는 `replace`보다 `del -> add`를 우선 사용
2. sender/receiver wire capture에서 `p7/p6/p0`가 의도대로 구분되는지
3. TMDS sender `tc filter` hit 증가로 `p7`, `p6` marking injection이 실제로 발생했는지
4. host-originated control path에서 `tc -s class show dev eth0`가
   `p7 -> class100:3`, `p6 -> class100:2`, `p0 -> class100:1`로 증가하는지
5. `ethtool -d eth0`의 `00022018` register가 candidate map 값으로 실제 바뀌는지
6. `ethtool -S eth0`의 `tx_good_frames`, `tx_octets` delta로 egress traffic 증가가 있었는지

### 보조 근거로만 볼 것

1. `ethtool -S eth0`의 `tx_pri*` counter
2. SK local `tcpdump -i eth0`

### 현재 pass/fail 기준에서 제외할 것

1. `tc -s qdisc show dev eth0`
2. switchdev forwarding 경로에서의 `tc -s class show dev eth0`

이 둘은 switchdev forwarding 관측에서는 `0 pkt`로 남아 유효한 판정 기준이 되지 못했다.

다만 host-originated control path에서는 `tc -s class show dev eth0`가 유효했다.

## 미해결

1. candidate map을 `eth0`만 아니라 `eth1`에도 동일 적용할지 결정해야 한다.
2. switchdev forwarding만으로 queue separation을 더 직접 보여줄 hardware-specific stat 또는 tracepoint가 있는지 확인해야 한다.

## 정리

이번 세션에서 확정된 것은 다음 두 가지다.

1. baseline `mqprio` map은 Phase 1 separation map이 아니다.
2. candidate map 전환은 `replace`가 아니라 `del -> add` 경로를 써야 할 가능성이 높다.
3. switchdev forwarding 경로에서는 wire capture와 coarse driver delta는 유효하지만, `qdisc/class` 통계는 직접 기준이 되지 않았다.
4. 그러나 같은 `eth0` egress를 쓰는 host-originated control path에서
   `p7 -> class100:3`, `p6 -> class100:2`, `p0 -> class100:1`이 재현되었고,
   `TX_PRI_MAP` register도 candidate map 값으로 실제 변했다.

따라서 현재 Phase 1 목표인 **PCP -> TC / queue mapping 확인**은 완료로 볼 수 있다.

테스트 후 `eth0`는 다시 baseline `mqprio` map으로 복구했다.
