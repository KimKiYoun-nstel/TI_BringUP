# Test B Replay Guide

## 목적

이 문서는 다음 검증을 **언제든지 다시 재시험**할 수 있도록 절차를 정리한다.

```text
TMDS eth2(ICSSG) sender가 만든 VLAN PCP p7/p6
-> SK CPSW switchdev forwarding
-> TMDS eth1 final receiver
```

최종 확인 목표는 다음이다.

- `TMDS eth2` sender에서 `vlan 301, p 7 / p 6`
- `TMDS eth1` final receiver에서도 `vlan 301, p 7 / p 6`

## 이번 세션에서 확정된 핵심 판단

### 1. 문제의 본질은 patch 부재가 아니었다.

- `RX_REMAP_VLAN` patch는 이미 local TI SDK 12 kernel source에 들어 있었다.
- direct sender `p0` 증상은 source patch 누락보다 **runtime QoS prerequisite 미충족** 영향이 더 컸다.

### 2. direct sender PCP emission은 설정 이슈였다.

다음 조건을 맞추자 SK CPSW direct sender에서 실제 wire PCP가 나왔다.

- `p0-rx-ptype-rrobin off`
- `mqprio hw 1 mode channel`
- VLAN subinterface `egress-qos-map`
- `tc skbedit priority`

### 3. Test B 첫 실패에는 sender 재구성 누락도 있었다.

같은 날 첫 Test B 재실행에서는 `TMDS ep2 eth2.301`를 다시 만들면서
`egress-qos-map`을 다시 넣지 않아 sender-side부터 `p0`가 나왔다.

즉 이 부분은 forwarding 문제라기보다 sender setup fault였다.

## 현재 확보한 TSN 목표

이번 검증으로 최소한 다음 목표를 추진할 수 있는 기반이 확보되었다.

1. `802.1Q VLAN PCP`를 endpoint에서 의도적으로 주입할 수 있다.
2. SK-AM64B의 CPSW를 switchdev mode에서 **L2 switch candidate**로 사용할 수 있다.
3. ICSSG endpoint가 넣은 PCP를 SK를 거쳐 다른 endpoint까지 전달하는 **priority-preserving forwarding** 경로를 확보했다.
4. 이후 `mqprio`, `CBS`, `taprio`, queue mapping, TSN class separation을 **PCP 기준**으로 검증할 수 있다.

주의:

- 이번 세션은 `PCP emission/preservation`을 본 것이다.
- 아직 `gPTP`, `802.1AS time-aware scheduling`, `Qbv gate schedule`까지 완료된 것은 아니다.

## 재시험 전제

### SK 쪽

- SK는 UART로 제어한다.
- SSH 제어 경로에 의존하지 않는다.
- 원하는 검증 상태:
  - `switch_mode=true`
  - `br-tsn vlan_filtering=1`
  - `eth0`, `eth1` 모두 `br-tsn` slave + `forwarding`
  - `p0-rx-ptype-rrobin=off`
  - `mqprio hw 1 mode channel` on both ports

### TMDS 쪽

- `TMDS eth0`는 control 유지
- `eth1`은 receiver용 `ep1`
- `eth2`는 ICSSG sender용 `ep2`
- test VLAN은 `301`
- test IP는 유효한 IPv4인 `10.31.0.x/24`

주의:

- `10.301.0.x/24`는 유효한 IPv4가 아니다.
- VLAN device를 다시 만들면 `egress-qos-map`도 다시 넣어야 한다.

## 재시험 자산

### 1. baseline topology 복구

host에서:

```bash
bash projects/tsn_dscp_pcp/board/apply_tsn_env.sh
```

역할:

- TMDS/SK rootfs overlay 재적용
- `Host -> TMDS -> SK` bridge control 환경 복구

### 2. TMDS Test B namespace 준비 helper

host에서:

```bash
bash projects/tsn_dscp_pcp/board/setup_testb_tmds_netns.sh
```

역할:

- TMDS `ep1`/`ep2` namespace 재생성
- `ep1 eth1.301 = 10.31.0.2/24`
- `ep2 eth2.301 = 10.31.0.1/24`
- `eth2.301 egress-qos-map` 재적용
- `tc skbedit priority` 재적용
- `iperf3` receiver 시작

## SK UART 절차

다음은 재시험에 필요한 SK 쪽 핵심 절차다.

### 1. switchdev/QoS 상태 만들기

```bash
tc qdisc del dev eth0 root 2>/dev/null
tc qdisc del dev eth1 root 2>/dev/null
ip link del br-tsn 2>/dev/null
ip addr flush dev eth0
ip addr flush dev eth1
ip link set eth0 down
ip link set eth1 down

ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off

devlink dev param set platform/8000000.ethernet \
  name switch_mode value true cmode runtime

ip link add name br-tsn type bridge
ip link set dev br-tsn type bridge ageing_time 1000
ip link set eth0 up
ip link set eth1 up
ip link set eth0 master br-tsn
ip link set eth1 master br-tsn
ip link set br-tsn up
ip link set dev br-tsn type bridge vlan_filtering 1

bridge vlan add dev br-tsn vid 1 pvid untagged self
bridge vlan add dev eth0 vid 301 master
bridge vlan add dev eth1 vid 301 master
bridge vlan add dev br-tsn vid 301 self

tc qdisc replace dev eth0 root handle 100: mqprio num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 hw 1 mode channel

tc qdisc replace dev eth1 root handle 100: mqprio num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 \
  queues 1@0 1@1 2@2 hw 1 mode channel
```

### 2. 상태 확인

```bash
bridge -d vlan show
bridge link
devlink dev param show platform/8000000.ethernet
ethtool --show-priv-flags eth0
ethtool --show-priv-flags eth1
tc -s qdisc show dev eth0
tc -s qdisc show dev eth1
```

pass 기준:

- `switch_mode=true`
- `p0-rx-ptype-rrobin=off`
- `eth0`, `eth1` forwarding
- `mqprio ... mode:channel`

## Capture 원칙

### 권장 capture point

1. `TMDS eth2` sender (`ep2`)
2. `TMDS eth1` final receiver (`ep1`)

### 보조 capture point

3. `SK eth1` ingress
4. `SK eth0` egress

주의:

- 이번 세션에서는 `SK tcpdump -i eth1`, `tcpdump -i eth0`가 switchdev hardware offload 상태에서 `0 packets captured`로 남았다.
- 따라서 **SK local capture가 비더라도 곧바로 forwarding failure로 단정하지 않는다.**
- 최종 판정은 TMDS sender/final receiver wire capture를 우선 기준으로 한다.

## Pass / Fail 기준

### 성공

`TMDS eth2` sender:

```text
vlan 301, p 7
vlan 301, p 6
```

`TMDS eth1` final receiver:

```text
vlan 301, p 7
vlan 301, p 6
```

### 실패 해석

#### Case 1

sender-side부터 `p0`

의미:

- `ep2 eth2.301` 재구성 시 `egress-qos-map` 또는 `tc skbedit priority`가 빠졌을 가능성이 높다.

#### Case 2

sender-side는 `p7/p6`, final receiver는 `p0`

의미:

- SK switchdev forwarding path에서 PCP preservation 문제를 의심한다.

#### Case 3

sender-side와 final receiver는 둘 다 `p7/p6`

의미:

- end-to-end PCP preservation은 성공
- SK local capture 부재는 offload visibility 문제로 본다.

## 관련 문서

- `docs/2026-06-26_am64x-cpsw-qos-runtime-prerequisite-validation.md`
- `docs/2026-06-26_testB-revalidation.md`
- `docs/2026-06-26_am64x-cpsw-vlan-pcp-remap-patch-investigation.md`
