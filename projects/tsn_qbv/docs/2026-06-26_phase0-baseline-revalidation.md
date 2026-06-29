# 2026-06-26 Phase 0 Baseline Revalidation

## 목적

`tsn_qbv` 프로젝트 시작 전에,
기존 `tsn_dscp_pcp`에서 확보한 PCP preservation baseline이 현재 live 상태에서 다시 재현되는지 확인했다.

검증 목표:

```text
TMDS eth2 sender: vlan 301, p7/p6
TMDS eth1 receiver: vlan 301, p7/p6
```

## 제어 방식

- SK: UART
- TMDS: SSH

## 확인한 baseline 상태

### SK

UART에서 확인한 상태:

- `switch_mode=true`
- `br-tsn=10.50.0.2/24`
- `eth0`, `eth1` 모두 `master br-tsn state forwarding`
- `bridge vlan`에서 `301` membership 유지
- `p0-rx-ptype-rrobin=off` on `eth0`, `eth1`
- `mqprio ... hw 1 mode channel` on `eth0`, `eth1`

즉 이번 재현은 SK를 다시 재설정하기보다,
이미 유지 중이던 validated switchdev baseline 위에서 TMDS endpoint를 다시 맞추고 wire capture를 확인하는 방식으로 진행했다.

### TMDS

host helper:

```bash
bash projects/tsn_qbv/board/setup_tmds_netns_endpoints.sh
```

재구성 후 상태:

- `ep1 eth1.301 = 10.31.0.2/24`
- `ep2 eth2.301 = 10.31.0.1/24`
- `eth2.301`에 `egress-qos-map` 유지
- `eth2.301` egress `tc skbedit priority`:
  - UDP `5001` -> priority `7`
  - UDP `5002` -> priority `6`

주의:

- helper 출력 직후 한 번은 `LOWERLAYERDOWN`처럼 보였으나,
  후속 `ip -br link` 및 `ethtool` 확인 시 `eth1`, `eth2` 모두 `LOWER_UP`, `1000Mb/s`, `Link detected: yes`로 안정화되었다.

## 트래픽 생성

TMDS `ep2` sender에서 다음 UDP flow를 생성했다.

- Flow A: `10.31.0.1 -> 10.31.0.2:5001`, `5 Mbits/sec`
- Flow B: `10.31.0.1 -> 10.31.0.2:5002`, `5 Mbits/sec`

receiver는 `ep1`에서 `iperf3 -s`로 대기했고,
sender와 receiver 양쪽 physical interface에서 `tcpdump`로 wire capture를 확인했다.

## 증거

### PCP 7, sender

```text
07:11:03.349876 70:ff:76:20:22:9a > 70:ff:76:20:22:99, ethertype 802.1Q (0x8100), length 50: vlan 301, p 7
10.31.0.1.47718 > 10.31.0.2.5001
```

### PCP 7, receiver

```text
07:11:03.349998 70:ff:76:20:22:9a > 70:ff:76:20:22:99, ethertype 802.1Q (0x8100), length 60: vlan 301, p 7
10.31.0.1.47718 > 10.31.0.2.5001
```

### PCP 6, sender

```text
07:11:28.777828 70:ff:76:20:22:9a > 70:ff:76:20:22:99, ethertype 802.1Q (0x8100), length 50: vlan 301, p 6
10.31.0.1.44254 > 10.31.0.2.5002
```

### PCP 6, receiver

```text
07:11:28.777928 70:ff:76:20:22:9a > 70:ff:76:20:22:99, ethertype 802.1Q (0x8100), length 60: vlan 301, p 6
10.31.0.1.44254 > 10.31.0.2.5002
```

## 부가 관찰

`ep2 eth2.301` egress filter counter:

- priority `7`: `1313 pkt`
- priority `6`: `1311 pkt`

`iperf3` 결과:

- UDP `5001`: receiver loss `0/1296 (0%)`, jitter `0.009 ms`
- UDP `5002`: receiver loss `0/864 (0%)`, jitter `0.009 ms`

## 판정

Phase 0 baseline은 현재 `tsn_qbv` 프로젝트 기준으로 다시 재현되었다.

확정된 사실:

- `TMDS eth2(ICSSG)` sender가 `vlan 301, p7/p6`를 생성했다.
- `SK CPSW switchdev`를 지난 뒤 `TMDS eth1` receiver에서도 같은 `p7/p6`가 유지되었다.

따라서 다음 단계는 Phase 1 `mqprio` 기반 PCP -> TC / queue mapping 증거 확보로 진행한다.
