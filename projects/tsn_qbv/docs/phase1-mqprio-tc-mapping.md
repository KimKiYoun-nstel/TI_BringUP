# Phase 1 mqprio TC Mapping

## 목적

PCP `p7/p6/p0` traffic이 실제로 traffic class 또는 queue 분리에 연결되는지 확인한다.

## 준비 자산

- `../board/setup_mqprio.sh`
- Phase 0 baseline 재현 결과

## 주의

- 현재 Phase 0 baseline에서 확인된 `mqprio map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2`는 `p0`, `p6`, `p7`을 서로 다른 TC로 분리하지 않는다.
- 즉 이 baseline map은 PCP preservation prerequisite에는 유효했지만, Phase 1의 queue/class separation pass 기준에는 그대로 사용할 수 없다.
- Phase 1에서는 `MAP_SPEC`, `QUEUES_SPEC`를 명시적으로 바꿔 `p0`, `p6`, `p7`이 다른 TC로 들어가도록 설계해야 한다.

예시 후보:

```bash
MAP_SPEC="0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0" \
QUEUES_SPEC="1@0 1@1 1@2" \
bash projects/tsn_qbv/board/setup_mqprio.sh eth0
```

위 값은 Phase 1용 분리 후보일 뿐이며, 아직 live hardware에서 pass로 확정한 값은 아니다.

## 1차 pass 기준

- `mqprio hw 1 mode channel` 적용 성공
- `p7/p6/p0` traffic이 wire에서 구분됨
- qdisc 또는 driver statistic에서 queue/class 관련 변화가 관찰됨

## 현재 상태

- 완료

## 이번 세션 초기 확인

1. 현재 baseline `map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2`은 `p0/p6/p7` 분리 목적에 맞지 않음을 다시 확인했다.
2. candidate map

```text
0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0
```

은 `tc qdisc replace`로는 실패했고,

```text
Error: Change operation not supported by specified qdisc.
```

`tc qdisc del dev eth0 root` 후 `tc qdisc add ... mqprio ...`로는 `eth0`에서 accept 되었다.
3. candidate map 상태에서 receiver capture 기준 다음은 유지되었다.

```text
UDP 5001 -> vlan 301, p 7
UDP 5002 -> vlan 301, p 6
```

4. switchdev forwarding 경로에서는 `tc -s qdisc show dev eth0`와 `tc -s class show dev eth0`가 `0 pkt`로 남았다.
5. 그래서 같은 `eth0` egress를 쓰는 host-originated control path `br-tsn.301`를 추가했다.
6. 이 control path에서 다음이 직접 확인되었다.

```text
p7 / UDP5001 -> class 100:3
p6 / UDP5002 -> class 100:2
p0 / UDP5003 -> class 100:1
```

7. 동시에 `ethtool -d eth0`에서 `TX_PRI_MAP` register가 다음처럼 바뀌는 것도 확인했다.

```text
baseline : 00022018:reg(00002210)
candidate: 00022018:reg(00000210)
```

## 현재 판정 기준 초안

- 필수:
  - candidate `mqprio` map apply 성공
  - receiver wire capture에서 `p7/p6/p0` 구분 확인
  - sender 쪽 `tc filter` hit 증가 또는 equivalent injection evidence 확인
  - host-originated control path에서 `p7/p6/p0`가 각각 다른 `mqprio class`로 증가 확인
- 보조:
  - `ethtool -S eth0`의 `tx_good_frames`, `tx_octets` delta
  - `ethtool -d eth0`의 `TX_PRI_MAP` register 값
- 제외:
  - `tc -s qdisc show dev eth0`
  - switchdev forwarding 경로에서의 `tc -s class show dev eth0`

제외 이유:

- 이번 switchdev forwarding 관측에서는 두 항목 모두 traffic 후에도 `0 pkt`로 남았다.

## 판정

Phase 1은 완료로 본다.

근거:

1. candidate `mqprio` map이 `eth0`에 실제 적용되었다.
2. receiver wire에서 `p7/p6/p0` flow가 다시 구분되었다.
3. host-originated control path에서 `p7/p6/p0`가 서로 다른 `mqprio class`로 증가했다.
4. hardware `TX_PRI_MAP` register 값도 candidate map에 맞게 바뀌었다.
