# 2026-06-26 Test B Revalidation

## 목적

현재 live switchdev 상태에서 `TMDS eth2(ICSSG)`가 만든 VLAN PCP `p7/p6`가
`SK CPSW switchdev forwarding`을 지나 `TMDS eth1` 최종 수신에서도 유지되는지 재검증한다.

## Topology

- `TMDS eth2(ICSSG sender, ep2)` -> `SK eth1(CPSW ingress)`
- `SK br-tsn switchdev/vlan-aware forwarding`
- `SK eth0(CPSW egress)` -> `TMDS eth1(receiver, ep1)`

주소:

- `ep2 eth2.301 = 10.31.0.1/24`
- `ep1 eth1.301 = 10.31.0.2/24`

포트 규칙:

- `dport 5001 -> skb priority 7`
- `dport 5002 -> skb priority 6`

## SK 상태

재검증 시점 SK는 다음 조건을 만족했다.

- `switch_mode=true`
- `br-tsn vlan_filtering=1`
- `eth0`, `eth1` 모두 `br-tsn` slave + `forwarding`
- `p0-rx-ptype-rrobin=off`
- `eth0`, `eth1` 모두 `mqprio hw 1 mode channel`
- VLAN `301`은 tagged membership만 부여됨
  - `eth0: vid 301`
  - `eth1: vid 301`
  - `br-tsn: vid 301 self`

즉 사용자가 요구한 runtime prerequisite는 충족된 상태였다.

## 중요한 수정 사항

이전 같은 날 첫 Test B 재실행에서는 `TMDS ep2`를 다시 만들면서
`eth2.301`에 `egress-qos-map`을 다시 넣지 않았다.

그 상태에서는 sender-side capture부터 `vlan 301, p 0`이 나왔고,
이 결과는 sender configuration fault였다.

이번 재검증에서는 다음을 명시적으로 다시 적용했다.

```bash
ip netns exec ep2 ip link set eth2.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
```

이 수정 후 sender-side PCP가 다시 정상화되었다.

## Capture Points

### 1. TMDS eth2 sender

`dport 5001`

```text
vlan 301, p 7
10.31.0.1.33768 > 10.31.0.2.5001
```

`dport 5002`

```text
vlan 301, p 6
10.31.0.1.45076 > 10.31.0.2.5002
```

판정:

- sender-side PCP insertion 정상

### 2. SK eth1 ingress

`tcpdump -i eth1`를 physical port에 직접 걸었지만,
switchdev offloaded forwarding 상태에서는 다음으로 남았다.

```text
0 packets captured
0 packets received by filter
```

즉 이번 세션에서는 SK local tcpdump로 hardware offloaded ingress frame을 보지 못했다.

### 3. SK eth0 egress

`tcpdump -i eth0`도 동일하게:

```text
0 packets captured
0 packets received by filter
```

즉 SK local tcpdump로 hardware offloaded egress frame도 보지 못했다.

### 4. TMDS eth1 final receiver

`dport 5001`

```text
vlan 301, p 7
10.31.0.1.33768 > 10.31.0.2.5001
```

`dport 5002`

```text
vlan 301, p 6
10.31.0.1.45076 > 10.31.0.2.5002
```

판정:

- final receiver에서도 PCP `p7/p6` 유지 확인

## Counter 변화

재검증 전후 SK 주요 변화:

### eth1 (ingress 쪽에 해당)

- `rx_good_frames`: `3625 -> 7115` (`+3490`)
- `rx_octets`: `5197280 -> 10377860` (`+5180580`)

### eth0 (egress 쪽에 해당)

- `tx_good_frames`: `7123 -> 10613` (`+3490`)
- `tx_octets`: `10399230 -> 15579810` (`+5180580`)

관찰:

- ingress 측 `eth1` RX 증가량과 egress 측 `eth0` TX 증가량이 대응한다.
- 반면 `tx_pri6/tx_pri7` counter는 여전히 증가하지 않았고 `tx_pri0`만 주로 증가했다.
- 따라서 이번 path 판정 기준도 여전히 `wire capture`가 우선이다.

## 최종 판정

사용자가 제시한 실패 case로 보면,

- **Case 1 아님**
  - sender-side `TMDS eth2`에서 이미 `p7/p6` 확인됨
- **Case 2로 볼 증거 없음**
  - SK local `eth1/eth0` tcpdump는 hardware offload 때문에 frame을 관측하지 못함
- **Case 3도 아님**
  - final receiver `TMDS eth1`에서도 `p7/p6`가 그대로 확인됨

즉 이번 재검증의 실제 결론은:

```text
TMDS eth2(ICSSG) sender가 만든 PCP p7/p6는
현재 SK CPSW switchdev forwarding path를 지나
TMDS eth1 final receiver에서도 유지되었다.
```

## 한 줄 요약

- 이전 같은 날 Test B 실패는 `ep2 eth2.301 egress-qos-map` 누락 상태의 false fail 성격이 있었고,
- sender 설정을 바로잡아 다시 시험하자 **end-to-end PCP preservation은 성공**했다.
