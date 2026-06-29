# 2026-06-26 Phase 4 Qbv Effect Validation

## 목적

Phase 4 목표는 gate schedule 변화가 실제 receiver packet arrival pattern 변화로 이어지는지 확인하는 것이다.

## 시작 live 상태

Phase 3 reusable state에서 시작했다.

- `eth0`: root `taprio` all-open schedule
- `br-tsn.301 = 10.31.0.3/24` sender 유지
- TMDS `ep1` receiver 유지

## baseline: all-open schedule

baseline taprio state:

```text
index 0 cmd S gatemask 0xff interval 100000000
```

동시 부하:

- UDP `5001`, PCP `7`, `10 Mbits/sec`
- UDP `5003`, PCP `0`, `10 Mbits/sec`

receiver throughput:

- `5001`: `9.99 Mbits/sec`
- `5003`: `9.99 Mbits/sec`

receiver capture에서는 두 flow가 거의 같은 시간대에 섞여 들어왔다.

예:

```text
1782464119.601106 vlan 301, p 0 ... 5003
1782464119.601383 vlan 301, p 7 ... 5001
1782464119.604220 vlan 301, p 0 ... 5003
1782464119.604795 vlan 301, p 7 ... 5001
```

즉 baseline은 interleaved arrival pattern이다.

## selective schedule 적용

다음 2-entry schedule로 `eth0` root taprio를 destroy/recreate 했다.

```text
entry 0: gate 0x1, 50 ms
entry 1: gate 0x4, 50 ms
cycle   : 100 ms
```

의도:

- `0x1`: `p7/TC0` window
- `0x4`: `p0/TC2` window

적용 결과:

```text
qdisc taprio 8006: root tc 3 map 2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
index 0 cmd S gatemask 0x1 interval 50000000
index 1 cmd S gatemask 0x4 interval 50000000
```

## selective schedule 결과

receiver throughput:

- `5001`: `10.0 Mbits/sec`
- `5003`: `10.0 Mbits/sec`

average throughput 자체는 유지됐지만,
receiver timestamp pattern이 baseline과 달라졌다.

### p0 burst 구간 예

```text
1782464170.527661 vlan 301, p 0 ... 5003
1782464170.530465 vlan 301, p 0 ... 5003
1782464170.531567 vlan 301, p 0 ... 5003
```

### p7 burst 구간 예

```text
1782464170.555789 vlan 301, p 7 ... 5001
1782464170.556944 vlan 301, p 7 ... 5001
1782464170.558116 vlan 301, p 7 ... 5001
```

### capture tail 예

```text
1782464170.638286 vlan 301, p 7 ... 5001
1782464170.638286 vlan 301, p 7 ... 5001
1782464170.638286 vlan 301, p 7 ... 5001
```

즉 selective schedule에서는 같은 PCP flow가 시간창 안에서 몰려 나오는 grouped/burst pattern이 관찰되었다.

## continuity

selective schedule 상태에서도 traffic은 완전히 끊기지 않았다.

- `ping -I br-tsn.301 10.31.0.2`: 성공
- RTT: `0.584 ~ 8.889 ms`

이는 gate schedule 영향으로 RTT가 baseline보다 커진 것으로 해석 가능하다.

## 판정

Phase 4는 완료로 본다.

확정된 사실:

1. selective taprio gate schedule이 실제로 적용되었다.
2. receiver arrival pattern이 interleaved -> grouped/burst 형태로 바뀌었다.
3. control-path와 test traffic은 selective schedule 상태에서도 유지되었다.

즉 현재 환경에서 **Qbv gate schedule 변경이 실제 수신 패턴 변화로 이어진다**는 점을 확인했다.

## 다음 단계 준비 상태

다음 `Phase 5`를 위해 현재 selective schedule을 그대로 유지한다.

- `eth0`: selective taprio schedule 유지
- `br-tsn.301`: sender path 유지
- TMDS receiver namespace / `iperf3` server 유지
