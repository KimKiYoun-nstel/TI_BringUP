# Phase 4 Qbv Effect

## 목적

gate schedule 변경이 실제 receiver packet arrival pattern 변화로 이어지는지 확인한다.

## 준비 자산

- Phase 3 결과
- sender / receiver capture 절차

## 1차 pass 기준

- schedule 변경에 따라 flow별 수신 pattern이 달라짐

## 현재 상태

- 완료

## 이번 적용 상태

- live 시작점은 `Phase 3 reusable state`
- baseline taprio state:

```text
index 0 cmd S gatemask 0xff interval 100000000
```

- test load:
  - UDP `5001`, `p7`, `10 Mbits/sec`
  - UDP `5003`, `p0`, `10 Mbits/sec`

## baseline(all-open) 관찰

receiver capture에서 `p7`와 `p0` packet이 거의 같은 시점에 섞여 들어왔다.

예:

```text
1782464119.601383 vlan 301, p 7 ... 5001
1782464119.601106 vlan 301, p 0 ... 5003
1782464119.604220 vlan 301, p 0 ... 5003
1782464119.604795 vlan 301, p 7 ... 5001
```

즉 all-open 상태에서는 두 flow가 시간축에서 interleaved pattern을 보였다.

## selective gate schedule

다음 2-entry schedule을 destroy/recreate 방식으로 적용했다.

```text
entry 0: gate 0x1, 50 ms   # p7/TC0 window
entry 1: gate 0x4, 50 ms   # p0/TC2 window
cycle   : 100 ms
```

적용 결과:

```text
qdisc taprio 8006: root tc 3 map 2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
index 0 cmd S gatemask 0x1 interval 50000000
index 1 cmd S gatemask 0x4 interval 50000000
```

## selective schedule 관찰

receiver capture에서 초반에 `p0` burst가 먼저 몰리고,
이후 `p7` burst가 연속적으로 몰리는 패턴이 관찰되었다.

예:

```text
1782464170.527661 vlan 301, p 0 ... 5003
1782464170.530465 vlan 301, p 0 ... 5003
1782464170.531567 vlan 301, p 0 ... 5003

1782464170.555789 vlan 301, p 7 ... 5001
1782464170.556944 vlan 301, p 7 ... 5001
1782464170.558116 vlan 301, p 7 ... 5001
```

마지막 부분에서도 같은 flow의 연속 burst가 보였다.

```text
1782464170.638286 vlan 301, p 7 ... 5001
1782464170.638286 vlan 301, p 7 ... 5001
1782464170.638286 vlan 301, p 7 ... 5001
```

즉 all-open의 interleaved pattern이 selective gate schedule에서는 burst/grouped pattern으로 바뀌었다.

## continuity

selective schedule 상태에서도 control-path는 완전히 깨지지 않았다.

- `ping -I br-tsn.301 10.31.0.2`: 성공
- RTT: 약 `0.584 ~ 8.889 ms`

이는 gate window 영향으로 해석 가능하다.

또한 두 UDP flow 모두 receiver까지 전달되었다.

## 판정

Phase 4는 완료로 본다.

근거:

1. taprio gate schedule을 selective하게 적용할 수 있었다.
2. all-open 대비 receiver timestamp pattern이 interleaved -> burst/grouped 형태로 바뀌었다.
3. control-path와 test traffic이 모두 완전히 끊기지 않고 유지되었다.

즉 현재 환경에서 **gate schedule 변경이 실제 traffic arrival pattern 변화로 이어진다**는 점을 확인했다.

## 현재 live 유지 상태

다음 `Phase 5` 시작을 위해 현재 selective schedule을 그대로 유지한다.

- `eth0`: taprio selective schedule 유지
- `br-tsn.301`: sender path 유지
- TMDS `ep1`/`ep2`, `5001`/`5002`/`5003` receiver 유지
