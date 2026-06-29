# 2026-06-26 Phase 3 taprio Apply Validation

## 목적

Phase 3 목표는 Qbv 본실험 전에 `taprio` qdisc가 현재 kernel/runtime에서 적용 가능한지,
그리고 적용 후 traffic continuity를 유지할 수 있는지 확인하는 것이다.

## 시작 live 상태

Phase 2 reusable state에서 시작했다.

- `eth0`: Phase 2 `mqprio map` 기반
- `eth0 parent 100:1`: `CBS offload 0`
- `br-tsn.301 = 10.31.0.3/24` sender 유지
- TMDS receiver namespace 유지

## 지원 상태 확인

live kernel / module 상태:

```text
CONFIG_NET_SCH_TAPRIO=m
CONFIG_TI_K3_AM65_CPTS=y
CONFIG_TI_AM65_CPSW_QOS=y
sch_taprio loaded
```

즉 `taprio` qdisc와 CPSW QoS/CPTS 의존성은 현재 rootfs/kernel에서 사용 가능했다.

## 첫 적용 시도

다음 selective schedule을 시도했다.

```text
entry 0: gate 0x1, 50 ms
entry 1: gate 0x6, 50 ms
cycle: 100 ms
clockid: CLOCK_TAI
base-time: 0
```

결과:

- `tc qdisc replace ... taprio ...` 자체는 성공
- `qdisc taprio`가 root에 생성됨

하지만 같은 running schedule 상태에서 schedule/mapping 변경을 다시 시도하면:

```text
Error: Changing the traffic mapping of a running schedule is not supported.
```

또한 이 selective schedule 상태에서는 `br-tsn.301 -> TMDS` control-path traffic이 끊겼다.

즉 이 단계에서 확인한 사실은 다음과 같다.

1. `taprio` 자체는 apply 가능하다.
2. 그러나 gate mask가 공격적이면 continuity가 깨질 수 있다.
3. running schedule은 destroy/recreate 없이 자유롭게 바꾸기 어렵다.

## 재시도: all-open reusable schedule

위 상태를 다음처럼 다시 만들었다.

```bash
tc qdisc del dev eth0 root
tc qdisc replace dev eth0 root taprio \
  num_tc 3 \
  map 2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S ff 100000000 \
  clockid CLOCK_TAI
```

결과:

```text
TAPRIO_RECREATE_RC=0
qdisc taprio 8005: root tc 3 map 2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
index 0 cmd S gatemask 0xff interval 100000000
```

즉 all-open schedule은 current live에서 안전한 reusable taprio state로 볼 수 있다.

## continuity 확인

all-open schedule 상태에서:

- `ping -I br-tsn.301 10.31.0.2`: 성공
- UDP `5001`, `5 Mbits/sec`, `2 sec`: 성공
- UDP `5003`, `5 Mbits/sec`, `2 sec`: 성공

receiver 결과:

`5001`:

```text
1.19 MBytes  5.00 Mbits/sec  receiver
```

`5003`:

```text
1.19 MBytes  5.00 Mbits/sec  receiver
```

## 판정

Phase 3은 완료로 본다.

확정된 사실:

1. `taprio` qdisc는 현재 kernel/runtime에서 실제 적용 가능하다.
2. selective schedule은 continuity를 깨뜨릴 수 있다.
3. `tc qdisc del` 후 all-open schedule로 recreate 하면 continuity를 유지할 수 있다.

따라서 다음 Phase 4는 이 **all-open taprio reusable state** 위에서,
gate schedule을 점진적으로 좁혀가며 효과를 보는 방식으로 진행한다.
