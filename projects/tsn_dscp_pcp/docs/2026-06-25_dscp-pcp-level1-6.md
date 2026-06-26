# 2026-06-25 DSCP PCP Level 1-6 Verification

## 목적

`.agents/am64x_tsn_dscp_pcp_step_guide.md`를 기준으로,

- SK `br-tsn`
- TMDS `eth1`, `eth2`

구성에서 DSCP/PCP/queue/scheduler readiness를 단계별로 확인했다.

## 전제 상태

- Host -> `TMDS eth0 192.168.0.220`
- SK control IP: `br-tsn 10.50.0.2/24`
- direct links:
  - `TMDS eth1 <-> SK eth0`
  - `TMDS eth2 <-> SK eth1`
- DSCP/PCP 실험 전 `ptp4l`, `phc2sys`는 중지했다.

## namespace 구성

실험 중 TMDS endpoint 분리를 위해 namespace를 사용했다.

- `ep1`: `eth1`
- `ep2`: `eth2`

실험 중 주소:

- `ep1 eth1`: `10.50.0.1/24`, `10.60.0.1/24`
- `ep2 eth2`: `10.60.0.2/24`

주의:

- namespace 실험 중에는 일반 `Host -> TMDS -> SK` ProxyJump 경로가 일시적으로 깨질 수 있다.
- 실험 중 SK 접근은 `TMDS root -> ip netns exec ep1 ssh root@10.50.0.2`로 유지했다.
- 실험 후 `eth1`, `eth2`는 root namespace로 되돌리고 TMDS profile을 재적용했다.

## Level 1 - L2 forwarding

### 결과

- `ip netns exec ep1 ping -c 5 10.60.0.2`: 성공
- `ip netns exec ep2 ping -c 5 10.60.0.1`: 성공
- loss: 양방향 모두 `0%`

### tcpdump 관측

`ep2 eth2`에서 다음이 관측되었다.

```text
70:ff:76:20:22:99 > 70:ff:76:20:22:9a, ethertype IPv4, 10.60.0.1 > 10.60.0.2: ICMP echo request
70:ff:76:20:22:9a > 70:ff:76:20:22:99, ethertype IPv4, 10.60.0.2 > 10.60.0.1: ICMP echo reply
```

### SK FDB

SK `br-tsn`에서 다음이 유지되었다.

- `70:ff:76:20:22:99 dev eth0 master br-tsn`
- `70:ff:76:20:22:9a dev eth1 master br-tsn`

### 판단

- `TMDS ep1 -> SK br-tsn -> TMDS ep2` L2 forwarding 성공

## Level 2 - DSCP preservation

다음 TOS 값을 `ep1`에서 송신하고 `ep2`에서 tcpdump로 관측했다.

- `0x00`
- `0x28`
- `0x88`
- `0xb8`

### 관측 결과

```text
0x00 -> tcpdump tos 0x0
0x28 -> tcpdump tos 0x28
0x88 -> tcpdump tos 0x88
0xb8 -> tcpdump tos 0xb8
```

대표 관측:

```text
IP (tos 0xb8, ttl 64, ...) 10.60.0.1 > 10.60.0.2: ICMP echo request
IP (tos 0xb8, ttl 64, ...) 10.60.0.2 > 10.60.0.1: ICMP echo reply
```

### 판단

- DSCP/TOS 값은 SK bridge를 지나도 보존되었다.

## Level 3 - VLAN PCP preservation

VLAN sub-interface:

- `ep1 eth1.100 -> 10.100.0.1/24`
- `ep2 eth2.100 -> 10.100.0.2/24`

송신:

- `ip netns exec ep1 ping -I eth1.100 -Q 0xb8 -c 3 10.100.0.2`

`ep2 eth2` tcpdump 관측:

```text
ethertype 802.1Q (0x8100), vlan 100, p 0, ethertype IPv4, (tos 0xb8, ...)
```

### 판단

- VLAN tag `100`은 SK bridge를 지나 보존되었다.
- DSCP `0xb8`도 VLAN frame 안에서 유지되었다.
- 그러나 이번 조건에서는 PCP가 `0`으로 관측되었다.
- 즉 현재 단계 해석은 다음과 같다.

```text
VLAN transparency: yes
DSCP preservation with VLAN: yes
desired PCP mapping: not yet confirmed
```

- 이후 PCP를 의도한 값으로 밀어 넣으려면 `skb priority`, `tc filter flower + skbedit priority`, 또는 더 명시적 queue mapping이 필요하다.

## PCP remediation probe

PCP `0`을 보완하기 위해 추가로 다음을 시도했다.

### 1. `tc flower + skbedit priority`

TMDS `ep1`에서:

```text
tc qdisc add dev eth1.100 clsact
tc filter add dev eth1.100 egress protocol ip flower ip_tos 0xb8 action skbedit priority 6
```

결과:

- filter 설치는 성공
- 하지만 wire capture는 계속 `vlan 100, p 0`

### 2. socket `SO_PRIORITY=6` 직접 송신

TMDS `ep1`에서 Python UDP sender로 다음을 직접 설정했다.

- `SO_PRIORITY = 6`
- `IP_TOS = 0xb8`
- bind device = `eth1.100`

결과:

- 수신 wire capture는 계속 `vlan 100, p 0`

### 3. 강제 `egress-qos-map 0:6`

`eth1.100`을 다시 만들며 다음처럼 강제로 맵을 바꿨다.

```text
egress-qos-map 0:6 1:6 2:6 3:6 4:6 5:6 6:6 7:6
```

결과:

- `ip -d link show`에서 map은 정상 반영됨
- 그럼에도 wire capture는 계속 `vlan 100, p 0`

### 4. VLAN offload 상태 확인

TMDS `eth1` feature 확인 결과:

- `tx-vlan-offload: off [fixed]`
- `rx-vlan-offload: off [fixed]`

즉 단순 hardware vlan offload on/off 문제로 보이지 않는다.

### remediation probe 결론

현재 확보한 증거만 보면:

```text
SK bridge가 PCP를 지우는 현상으로 보기보다,
TMDS eth1 VLAN egress path에서 PCP가 실제 tag에 반영되지 않는 쪽으로 보인다.
```

보다 정확히는:

- DSCP는 보존됨
- VLAN tag는 보존됨
- 하지만 TMDS `eth1` sender path에서 non-zero PCP emission이 확인되지 않음

따라서 다음 우선 조사 대상은 `SK bridge`보다 먼저 다음이다.

1. TMDS CPSW `eth1` VLAN PCP egress behavior
2. 사용 중 kernel/driver에서 `egress-qos-map` 반영 경로
3. alternative path로 `tc` class/priority -> hardware queue mapping이 실제 tag priority에 연결되는지

## Level 4 - SK qdisc/queue stats

DSCP `0xb8` ICMP 20개 송신 전후 비교:

- `eth0` `rx_good_frames`: `675 -> 739`
- `eth1` `tx_good_frames`: `696 -> 763`
- `tc -s qdisc show dev eth0` root counter: `443 pkt -> 484 pkt`
- `tc -s qdisc show dev eth1` root counter: `54 pkt -> 77 pkt`

### 판단

- TMDS `ep1 -> ep2` traffic이 SK `eth0` RX, `eth1` TX, qdisc counter에 반영되는 것을 확인했다.
- 이번 단계에서는 drop/overlimit 증가는 관찰되지 않았다.

## Level 5 - congestion / priority effect

### background UDP

- `ip netns exec ep2 iperf3 -s`
- `ip netns exec ep1 iperf3 -c 10.60.0.2 -u -b 900M -t 8 -S 0x00`

결과:

- sender: 약 `470 Mbit/s`
- receiver: 약 `255 Mbit/s`
- UDP datagram loss: 약 `46%`

### high-priority ping during load

- `ip netns exec ep1 ping -I eth1 -Q 0xb8 -i 0.02 -c 200 10.60.0.2`

결과:

- loss: `0%`
- RTT avg: `0.330 ms`

### low vs high quick comparison

같은 background UDP 조건에서 비교:

- low (`0x00`): avg `0.425 ms`, loss `0%`
- high (`0xb8`): avg `0.334 ms`, loss `0%`

### 판단

- 이번 실험만으로 DSCP만의 명확한 우선순위 보호 효과를 입증했다고 보기는 어렵다.
- 다만 heavy UDP loss가 있는 상황에서도 ICMP RTT/loss는 크게 악화되지 않았다.
- 다음 단계는 `mqprio`, `skb priority mapping`, `tc filter`, `taprio` 같은 명시적 분류/스케줄링 설정이다.

## Level 6 - scheduler readiness

SK에서 다음 module load를 확인했다.

- `sch_mqprio`
- `sch_taprio`
- `cls_flower`
- `act_skbedit`

또한 다음 `mqprio` qdisc 적용이 성공했다.

```text
tc qdisc add dev eth1 root handle 100: mqprio num_tc 4 ... hw 0
```

관측된 qdisc:

```text
qdisc mqprio 100: root tc 4 ...
mode:dcb
shaper:dcb
```

### 판단

- software mode 기준 `mqprio` 설정 가능
- `taprio` module 존재 확인
- hardware offload 가능 여부는 아직 미확인

## 환경 원복

실험 후 다음 상태로 복구했다.

- TMDS root namespace:
  - `eth0 = 192.168.0.220/24`
  - `eth1 = 10.50.0.1/24`
  - `eth2 = no IP`
- Host -> `ssh -J root@192.168.0.220 root@10.50.0.2` 경로 재확인 완료

## 최종 결론

- SK `br-tsn` 기반 2-port L2 forwarding은 정상 동작
- DSCP 값은 bridge를 지나 보존됨
- VLAN tag도 bridge를 지나 보존됨
- 현재 조건에서는 PCP는 `0`으로 관측되며, 추가 remediation probe 후에도 non-zero PCP emission을 재현하지 못함
- SK qdisc/stat counter는 traffic 전후 증가를 관찰 가능
- 기본 상태에서 DSCP만으로 명확한 priority differentiation을 확정하기는 어려움
- 다음 실작업 우선순위는 다음과 같다.

1. TMDS `eth1` VLAN PCP egress path 원인 확인
2. `mqprio` traffic class 매핑이 tag priority에 연결되는지 확인
3. 필요 시 `taprio`/CBS/ETF로 확장
