# AM64x CPSW QoS Runtime Prerequisite Validation

## 1. Test Purpose

이번 검증의 목적은 SK-AM64B 보드를 **UART 콘솔로만 제어**하면서,
AM64x CPSW QoS 공식 prerequisite를 실제 runtime에 적용했을 때

- CPSW direct sender가 VLAN PCP를 non-zero로 wire에 emit하는지
- ICSSG가 넣은 PCP가 SK CPSW switchdev forwarding egress 후에도 유지되는지

를 확인하는 것이었다.

이번 검증은 source patch 확인이 아니라 runtime prerequisite 충족 여부에 집중했다.

적용 대상으로 본 핵심 조건:

```text
p0-rx-ptype-rrobin off
mqprio hw 1 mode channel
VLAN subinterface egress-qos-map
tc skbedit priority
wire VLAN PCP p7/p6 확인
```

## 2. Hardware Topology

- `TMDS eth1 <-> SK eth0`
- `TMDS eth2 <-> SK eth1`
- `TMDS eth0 = 192.168.0.220/24` control 유지
- SK는 이번 세션에서 SSH가 아니라 UART로만 제어

시험별 사용 경로:

- Test A-1: `SK eth1(CPSW sender) -> TMDS eth2(ICSSG receiver/capture)`
- Test A-2: `SK eth0(CPSW sender) -> TMDS eth1(CPSW receiver/capture)`
- Test B: `TMDS eth2(ICSSG sender) -> SK eth1(CPSW ingress) -> SK switchdev/bridge -> SK eth0(CPSW egress) -> TMDS eth1(receiver/capture)`

## 3. Control Method

- SK: UART
- TMDS: SSH

SK는 테스트 중 `eth0`, `eth1`, `br-tsn`, `switch_mode`를 크게 바꾸므로
기존 `Host -> TMDS -> SK` SSH 경로를 신뢰하지 않고 UART만 사용했다.

## 4. Baseline

### SK

baseline 시점 관찰:

- kernel: `Linux am64xx-evm 6.18.13-gc21449208550`
- `devlink dev param show platform/8000000.ethernet`:
  - `switch_mode=false`
- `ethtool --show-priv-flags eth0/eth1`:
  - `p0-rx-ptype-rrobin: on`
  - `cut-thru: off`
- `ethtool -l eth0/eth1`:
  - `TX: 8`
- `tc qdisc show dev eth0/eth1`:
  - 기본 `mq` + `pfifo_fast`
- runtime bridge:
  - `br-tsn` 존재
  - `br-tsn=10.50.0.2/24`
  - `eth0`, `eth1`는 bridge slave 상태

즉 시작점은 기존 steady-state lab 그대로였고,

```text
switch_mode=false
br-tsn vlan_filtering=0
p0-rx-ptype-rrobin=on
```

상태였다.

### TMDS

baseline 시점 관찰:

- kernel: `Linux am64xx-evm 6.18.13-ti-00778-gc21449208550-dirty`
- `eth0=192.168.0.220/24`
- `eth1=10.50.0.1/24`
- `eth2=no IP`
- driver:
  - `eth1 = am65-cpsw-nuss`
  - `eth2 = icssg-prueth`
- `ethtool -k eth1`, `ethtool -k eth2`:
  - `rx-vlan-offload: off [fixed]`
  - `tx-vlan-offload: off [fixed]`

## 5. Test A: SK CPSW Direct Sender PCP Emission

### A-1 eth1 -> TMDS eth2

#### Commands

SK UART에서:

1. `br-tsn`, 기존 qdisc, 기존 VLAN device 정리
2. `ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off`
3. `ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off`
4. `ip link add link eth1 name eth1.301 type vlan id 301`
5. `ip link set eth1.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7`
6. `tc qdisc replace dev eth1 root handle 100: mqprio ... hw 1 mode channel`
7. `tc filter add dev eth1.301 egress ... dport 5001 ... skbedit priority 7`
8. `tc filter add dev eth1.301 egress ... dport 5002 ... skbedit priority 6`

TMDS SSH에서:

1. `eth2.301` 생성
2. `iperf3 -s -D -p 5001`, `iperf3 -s -D -p 5002`
3. `tcpdump -i eth2 -e -vvv -n ...`

주의:

- 사용자 초안의 `10.301.0.x/24`는 유효한 IPv4가 아니므로,
  실제 시험에는 `10.31.0.1/24 <-> 10.31.0.2/24`를 사용했다.

#### Results

- `p0-rx-ptype-rrobin off` 적용: 성공
- `mqprio ... hw 1 mode channel` 적용: 성공
- `tc skbedit priority` egress filter 설치: 성공
- `iperf3` UDP 송신/수신: 성공
- `tc filter` hit counter 증가: 성공

#### tcpdump Evidence

TMDS `eth2` physical capture에서 다음이 직접 확인되었다.

`dport 5001`:

```text
vlan 301, p 7
10.31.0.1.35397 > 10.31.0.2.5001
```

`dport 5002`:

```text
vlan 301, p 6
10.31.0.1.42285 > 10.31.0.2.5002
```

반대 방향 응답 패킷은 `p 0`으로 보였지만,
이번 시험의 pass/fail 기준은 sender emission이므로 문제로 보지 않았다.

#### tc / ethtool Counters

- `tc -s filter show dev eth1.301 egress`
  - `priority 7` filter hit 증가
  - `priority 6` filter hit 증가
- `tc -s qdisc show dev eth1`
  - `mqprio 100:` root traffic 증가
- 그러나 `ethtool -S eth1`는 다음처럼 보였다.
  - `tx_pri0`만 증가
  - `tx_pri6`, `tx_pri7`는 증가하지 않음

즉 이번 세션에서는 **wire PCP 증거가 `ethtool -S` priority counter보다 더 신뢰할 수 있는 pass/fail 기준**이었다.

#### Decision

`SK eth1(CPSW)` direct sender는 공식 prerequisite 적용 후 실제 wire에 `p7`, `p6`를 emit했다.

### A-2 eth0 -> TMDS eth1

#### Commands

SK UART에서:

1. `ip link add link eth0 name eth0.300 type vlan id 300`
2. `ip link set eth0.300 type vlan egress 0:0 ... 7:7`
3. `tc qdisc replace dev eth0 root handle 100: mqprio ... hw 1 mode channel`
4. `tc filter add dev eth0.300 egress ... dport 5001 ... skbedit priority 7`
5. `tc filter add dev eth0.300 egress ... dport 5002 ... skbedit priority 6`

TMDS SSH에서:

1. `eth1.300` 생성
2. `iperf3` server 실행
3. receiver capture 시도

주의:

- 사용자 초안의 `10.300.0.x/24`도 유효한 IPv4가 아니므로,
  실제 시험에는 `10.30.0.1/24 <-> 10.30.0.2/24`를 사용했다.
- 첫 설정 직후에는 `eth0.300`, `eth1.300`에 static test IP가 남지 않고 link-local만 보였다.
  그래서 링크가 안정된 뒤 `ip addr replace`로 다시 넣어 reachability를 복구했다.

#### Results

- `mqprio ... hw 1 mode channel`: 성공
- `tc skbedit priority` filter 설치: 성공
- `ip addr replace 10.30.0.x/24`: 필요했고 이후 ping/iperf 성공
- `iperf3` UDP 송신/수신: 성공

#### tcpdump Evidence

이 경로에서는 **receiver-side physical capture에 예외가 있었다.**

- TMDS `eth1` physical `tcpdump`:
  - `0 packets captured`
- 그러나 TMDS `eth1.300` capture는 payload 수신을 보여주었고,
  sender-side SK `eth0` physical capture는 VLAN PCP를 직접 보여주었다.

SK `eth0` source-side capture에서 확인된 증거:

`dport 5001`:

```text
vlan 300, p 7
10.30.0.1.45803 > 10.30.0.2.5001
```

`dport 5002`:

```text
vlan 300, p 6
10.30.0.1.58282 > 10.30.0.2.5002
```

#### tc / ethtool Counters

- `tc -s filter show dev eth0.300 egress`
  - `priority 7` filter hit 증가
  - `priority 6` filter hit 증가
- `ethtool -S eth0`
  - 여전히 `tx_pri0`만 증가
  - `tx_pri6`, `tx_pri7`는 증가하지 않음

#### Decision

`SK eth0(CPSW)` direct sender도 실제 source-side wire capture 기준으로 `p7`, `p6` emission이 확인되었다.

단, `TMDS eth1` physical receiver capture는 이 세션에서 재현성 있게 보이지 않았고,
이는 TMDS CPSW receiver-side capture 특성 또는 capture 방법 차이로 남았다.

## 6. Test B: ICSSG PCP Injector -> SK CPSW Switchdev Forwarding

### Commands

SK UART에서:

1. direct sender 시험용 qdisc/VLAN 정리
2. `devlink dev param set platform/8000000.ethernet name switch_mode value true cmode runtime`
3. `ip link add name br-tsn type bridge`
4. `ip link set eth0 up`, `ip link set eth1 up`
5. `ip link set eth0 master br-tsn`, `ip link set eth1 master br-tsn`
6. `ip link set dev br-tsn type bridge vlan_filtering 1`
7. VLAN programming:
   - `bridge vlan add dev br-tsn vid 1 pvid untagged self`
   - `bridge vlan add dev eth0 vid 301 master`
   - `bridge vlan add dev eth1 vid 301 master`
   - `bridge vlan add dev br-tsn vid 301 self`

TMDS SSH에서:

1. `eth1` receiver용 `ep1` namespace
2. `eth2` sender용 `ep2` namespace
3. `ep1`:
   - `eth1.301 = 10.31.0.2/24`
   - `iperf3` server 실행
4. `ep2`:
   - `eth2.301 = 10.31.0.1/24`
   - `tc filter ... dport 5001 -> skbedit priority 7`
   - `tc filter ... dport 5002 -> skbedit priority 6`
5. `ep1 eth1` physical `tcpdump`
6. `ep2`에서 `iperf3` UDP 송신

### Results

- `switch_mode=true`: 성공
- `br-tsn vlan_filtering=1`: 성공
- `bridge vlan show`: `eth0`, `eth1`, `br-tsn` 모두 `vid 301` 반영 확인
- `bridge link`: `eth0`, `eth1` 모두 `forwarding`
- `ep2` sender filter hit counter 증가: 성공
- `iperf3` sender/receiver success: 성공

그러나 수신 side physical capture는 둘 다 다음으로 나왔다.

### tcpdump Evidence

`dport 5001`:

```text
vlan 301, p 0
10.31.0.1.58909 > 10.31.0.2.5001
```

`dport 5002`:

```text
vlan 301, p 0
10.31.0.1.45576 > 10.31.0.2.5002
```

즉 `TMDS eth2(ICSSG)` sender가 만든 `priority 7`, `priority 6`은
`SK switchdev forwarding`을 통과한 뒤 최종 `TMDS eth1` 수신 wire에서는 유지되지 않았다.

### bridge/devlink State

실패 시점 SK 상태:

- `switch_mode=true`
- `p0-rx-ptype-rrobin=off`
- `br-tsn vlan_filtering=1`
- `eth0`, `eth1` 모두 `bridge forwarding`
- `bridge vlan show`:
  - `eth0: 301`
  - `eth1: 301`
  - `br-tsn: 301 self`

즉 이번 실패는 단순히 switchdev 미적용 상태에서 나온 결과가 아니었다.

### ethtool Counters

Test B 종료 시점 SK `ethtool -S`에서 관찰된 점:

- `eth0`, `eth1` 모두 `tx_pri0`만 유의미하게 증가
- `tx_pri6`, `tx_pri7`는 증가하지 않음
- `eth0` 쪽에 일부 drop 카운터 존재
  - `ale_drop: 22`
  - `rx_port_mask_drop: 23`
  - `ale_vid_ingress_drop: 12`
- `eth1` 쪽에도 일부 drop 카운터 존재
  - `ale_drop: 10`
  - `rx_port_mask_drop: 11`

이번 세션만으로 이 drop이 곧바로 root cause라고 단정할 수는 없지만,
switchdev forwarding path 추가 분석 포인트로 남는다.

### Decision

`TMDS eth2(ICSSG)` sender filter는 정상 hit했고 sender/receiver 애플리케이션도 성공했지만,
SK CPSW switchdev forwarding egress 후 최종 PCP는 `p 0`으로 보였다.

즉 **이번 세션에서는 switchdev forwarding PCP preservation은 실패**다.

## 7. Conclusion

이번 결과는 세 가지 case 중 하나로 단순 분류되지 않고,
다음처럼 **혼합 결과**로 정리하는 것이 정확하다.

### Direct Sender Conclusion

`Case 1`에 해당한다.

의미:

- 이전 CPSW sender `p 0`는 source patch 부재보다 runtime prerequisite 미충족 영향이 컸다.
- 실제로 다음 조건을 맞추자 `SK eth0`, `SK eth1` direct sender 모두 wire에서 `p7`, `p6`가 나왔다.

```text
p0-rx-ptype-rrobin off
mqprio hw 1 mode channel
VLAN subinterface egress-qos-map
tc skbedit priority
```

### Switchdev Forwarding Conclusion

하지만 `Case 2`는 아니고,
실제로는 다음이 확인되었다.

```text
ICSSG sender p7/p6 -> SK CPSW switchdev forwarding -> final receiver p0
```

즉 **CPSW endpoint sender emission은 해결됐지만,
SK CPSW switchdev forwarding path의 PCP preservation 문제는 남아 있다.**

정리하면:

1. `RX_REMAP_VLAN` 패치 부재가 direct sender `p0`의 주원인은 아니었다.
2. official QoS prerequisite 적용 후 CPSW direct sender PCP emission은 정상 동작했다.
3. 그러나 switchdev forwarding path는 여전히 ingress PCP를 egress에서 보존하지 못했다.

## 8. Next Action Items

1. Test B 실패 원인 분석을 위해 `am65-cpsw-switchdev.c`, ALE/VLAN admission 경로, host-port priority map 경로를 source level로 다시 좁힌다.
2. `bridge vlan` programming을 `pvid/tagged/self/master` 조합별로 더 미세하게 바꿔 보며 PCP preservation에 차이가 있는지 확인한다.
3. `ethtool -S`의 `ale_drop`, `rx_port_mask_drop`, `ale_vid_ingress_drop`가 어떤 순간에 증가하는지 단계별로 분리 측정한다.
4. 필요하면 SK egress side에서 추가 `tcpdump` / register instrumentation / tracepoint 수준 관찰을 붙인다.
5. direct sender 쪽은 이미 동작이 확인되었으므로, 이후 DSCP -> PCP -> `mqprio`/`CBS`/`taprio` 실험은 endpoint sender 기준으로는 진행 가능하다.

## 현재 live 상태 메모

이 세션 종료 시점 runtime은 실험 상태 그대로 남아 있다.

- SK: `switch_mode=true`, `br-tsn vlan_filtering=1`, UART 제어 상태
- TMDS: `ep1`/`ep2` namespace 기반 sender/receiver 분리 상태

즉 기존 `Host -> TMDS -> SK` SSH 기반 bridge 운영 상태로는 자동 복구하지 않았다.
