# Bidirectional Endpoint Hardware Taprio Validation

> Evidence-only note: current canonical summary is `docs/phaseA-endpoint-egress-qbv.md`.

## 목적

`switch_mode=false` direct endpoint topology에서 양방향 모두 hardware `taprio`가 실제로 동작하는지 확인한다.

- `SK eth1 (CPSW) -> TMDS eth2 (ICSSG)`
- `TMDS eth2 (ICSSG) -> SK eth1 (CPSW)`

핵심 판정 포인트는 다음이다.

1. `flags 2` qdisc가 실제로 apply 되는가
2. UDP traffic이 loss 없이 흐르는가
3. VLAN PCP가 wire에서 의도한 `p7/p6`로 보이는가
4. 양 endpoint의 hardware 제약이 서로 같은가 다른가

## Topology / 공통 조건

- direct path: `SK eth1 <-> TMDS eth2`
- `switch_mode=false`
- VLAN: `301`
- IP:
  - `SK eth1.301 = 10.31.0.1/24`
  - `TMDS eth2.301 = 10.31.0.2/24`

공통 주의사항:

- 양쪽 VLAN subinterface가 시험 중 `169.254.x.x` link-local로 drift할 수 있다.
- trial 중 여러 번 실제 실패 원인은 offload가 아니라 이 IP drift였다.
- traffic 시작 전마다 반드시 `ip -4 addr show dev ethX.301` 재확인이 필요하다.

## 1. SK CPSW sender -> TMDS ICSSG receiver

### schedule

TI CPSW EST reference와 같은 minimal schedule을 사용했다.

```bash
tc qdisc replace dev eth1 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 125000 \
  sched-entry S 02 125000 \
  sched-entry S 01 250000 \
  flags 2
```

### result

- `flags 2` apply 성공
- `tc -s qdisc show dev eth1`에 `flags 0x2`, `cycle-time 500000` 확인
- UDP `5001 -> p7`, `5002 -> p6`
- `iperf3` result:
  - `5001`: sender/receiver `20.0 Mbits/sec`, loss `0/8634`
  - `5002`: sender/receiver `20.0 Mbits/sec`, loss `0/8634`
- TMDS wire capture saved:
  - `projects/tsn_qbv/logs/2026-06-29_est_hw_taprio_eth2.txt`
- TMDS capture count:
  - `p7 = 8635`
  - `p6 = 8635`
  - `p0 = 2`

### 판정

`SK eth1(CPSW)`는 TI reference 그대로의 `500 us` cycle hardware `taprio`를 정상 지원한다.

## 2. TMDS ICSSG sender -> SK CPSW receiver

### 초기 실패 조건 분리

처음에는 기존 인식대로 `hardware taprio`가 안 되는 것처럼 보였지만, 실제로는 조건이 더 많았다.

1. `eth2`가 up/VLAN active 상태에서 `ethtool -L eth2 tx 3`를 시도하면:

```text
netlink error: Device or resource busy
```

2. `eth2`를 down 한 뒤 `TX=3` 적용 전 상태에서는 multi-TC qdisc가 다음으로 실패한다.

```text
Error: sch_mqprio_lib: Queues 1:1 for TC 1 exceed the 1 TX queues available.
```

3. `TX=3` 적용 후에도 CPSW와 같은 `500 us` cycle을 그대로 쓰면 다음으로 실패한다.

```text
Error: icssg_prueth: cycle_time 500000 is less than min supported cycle_time 1000000.
```

즉 ICSSG endpoint 쪽 hardware offload는 아예 불가가 아니라,

- 먼저 `TX=3` 구성 필요
- 그 다음 `cycle_time >= 1000000 ns` 조건 필요

로 정리되었다.

### 동작한 schedule

ICSSG 최소 cycle 조건에 맞춰 다음 schedule을 사용했다.

```bash
tc qdisc replace dev eth2 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 250000 \
  sched-entry S 02 250000 \
  sched-entry S 01 500000 \
  flags 2
```

추가 prerequisite:

```bash
ip link set eth2 down
ethtool -L eth2 tx 3
ip link set eth2 up

ip link set eth2.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
```

### result

- `ethtool -l eth2` after reconfig:
  - `Current hardware settings: TX 3`
- `tc -s qdisc show dev eth2`:
  - `flags 0x2`
  - `cycle-time 1000000`
  - `queues offset 0 count 1 offset 1 count 1 offset 2 count 1`
- UDP `5001 -> p7`, `5002 -> p6` filter counter 증가:
  - priority `7`: `25735501 bytes / 17304 pkt`
  - priority `6`: `25733746 bytes / 17299 pkt`
- `iperf3` result:
  - `5001`: sender/receiver `20.0 Mbits/sec`, loss `0/8635`
  - `5002`: sender/receiver `20.0 Mbits/sec`, loss `0/8635`
- SK receiver capture count:
  - `p7 = 8381`
  - `p6 = 8636`
  - `p0 = 3`
- sample capture:
  - `vlan 301, p 7` confirmed on SK `eth1`
  - later `vlan 301, p 6` count also confirmed

### 판정

`TMDS eth2(ICSSG)`도 hardware `taprio` offload 자체는 가능하다.
다만 `SK CPSW`와 동일 조건은 아니고, 최소 동작 조건이 더 엄격하다.

## 3. 최종 결론

양방향 endpoint 경로 모두에서 hardware `taprio`는 동작한다.

단, 두 endpoint의 조건은 동일하지 않다.

- `SK CPSW eth1`
  - TI reference `500 us` cycle 그대로 동작
  - `p0-rx-ptype-rrobin off`, `TX=3` 필요

- `TMDS ICSSG eth2`
  - `eth2 down -> ethtool -L eth2 tx 3 -> eth2 up` 필요
  - `cycle_time >= 1 ms` 필요
  - VLAN `egress-qos-map` 필요

따라서 현재 기준 결론은 다음과 같다.

```text
Bidirectional endpoint hardware taprio validation: PASS

SK CPSW sender path:
  500 us TI reference schedule로 정상 동작

TMDS ICSSG sender path:
  1 ms 이상 cycle과 TX queue/VLAN prerequisite를 맞추면 정상 동작
```

## 4. 다음 액션

1. `TMDS ICSSG`의 `cycle_time >= 1 ms` 제약이 driver 문서/소스에서 어디서 오는지 추가 확인
2. 양방향 모두에서 burst/gap pattern을 더 정밀하게 계측
3. 양방향 hardware `taprio` 상태에서 gPTP coexistence를 단계적으로 다시 붙이기
