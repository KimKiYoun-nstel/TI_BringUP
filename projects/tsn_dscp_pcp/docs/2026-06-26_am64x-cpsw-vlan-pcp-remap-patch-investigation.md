# AM64x CPSW VLAN PCP Remap Patch Investigation

## 1. Problem Summary

현재 관측된 문제는 다음 두 갈래다.

1. AM64x CPSW sender path에서 VLAN PCP가 wire에 non-zero로 나오지 않는다.
2. ICSSG가 만든 non-zero PCP도 SK CPSW egress를 지나면 최종적으로 `p 0`으로 관측된다.

이번 조사 목표는 `P0_RX_REMAP_VLAN` 또는 동등한 host-port priority remap 설정이
현재 TI SDK 12 Linux kernel source에 실제로 포함되어 있는지 확인하고,
없다면 패치 후보를 작성하는 것이었다.

## 2. Current Evidence

이미 확보된 실험 증거는 다음과 같다.

- `TMDS eth2(ICSSG)` sender는 `tc skbedit priority -> VLAN PCP` emission이 실제로 동작했다.
  - `vlan 101, p 7`
  - `vlan 101, p 6`
- 반면 CPSW sender path는 다음 모두 `p 0`이었다.
  - `TMDS eth1.100 -> SK eth0`
  - `SK eth0.200 -> TMDS eth1`
  - `SK eth1.201 -> TMDS eth2`
- `TMDS eth2(ICSSG)`가 만든 non-zero PCP를 `SK br-tsn` Linux bridge로 통과시키면,
  최종 `TMDS eth1(CPSW receiver)`에서 `vlan 301, p 0`으로 관측되었다.
- SK에서 `switch_mode=true` 와 `br-tsn vlan_filtering=1` 전환 자체는 가능했지만,
  그 상태에서 end-to-end PCP forwarding pass/fail 로그는 아직 확정하지 못했다.

즉 현재 문제는 단순 generic Linux VLAN 기능보다는
`AM64x CPSW host-port / QoS / internal priority mapping` 쪽이 더 의심되는 상태였다.

## 3. Running Kernel and Source Version

### Local source

- source path: `workspace/ti-linux-kernel-sdk12`
- `git log -1 --oneline`:
  - `c21449208 TI: HACK: drivers: bluetooth: btti_uart: remove serdev_set_rts troublesome functions`
- `git describe --always --dirty --tags`:
  - `cicd.master.202603261656`
- branch:
  - `base-clean`
- local repo state:
  - `git rev-list --count HEAD = 1`
  - `git rev-parse --is-shallow-repository = true`

주의:

- local kernel workspace는 shallow repository라서 로컬 `git log`만으로는
  과거 patch 도입 이력을 충분히 추적할 수 없었다.
- patch history는 TI 공개 cgit와 source blame/commit 페이지를 함께 사용했다.

### Running kernel: TMDS64EVM

- `uname -a`:
  - `Linux am64xx-evm 6.18.13-ti-00778-gc21449208550-dirty #1 SMP PREEMPT Thu Mar 26 20:21:19 UTC 2026 aarch64 GNU/Linux`
- `cat /proc/version`:
  - same base commit `gc21449208550`
- config evidence:
  - `CONFIG_TI_K3_AM65_CPSW_NUSS=y`
  - `CONFIG_TI_K3_AM65_CPSW_SWITCHDEV=y`
  - `CONFIG_TI_AM65_CPSW_QOS=y`
  - `CONFIG_BRIDGE_VLAN_FILTERING=y`
  - `CONFIG_NET_SCH_MQPRIO=m`
  - `CONFIG_NET_SCH_TAPRIO=m`
  - `CONFIG_NET_SCH_CBS=m`
  - `CONFIG_NET_CLS_FLOWER=m`
  - `CONFIG_NET_ACT_SKBEDIT=m`

판단:

- TMDS running kernel은 local source와 **같은 base commit hash**를 사용한다.
- 하지만 version string에 `-ti-00778` 및 `-dirty`가 있으므로,
  TMDS image는 `c21449208550` 기반의 dirty build였다.
- 따라서 **TMDS running image가 local source와 완전히 동일하다고 단정할 수는 없다.**

### Running kernel: SK-AM64B

- `uname -a`:
  - `Linux am64xx-evm 6.18.13-gc21449208550 #1 SMP PREEMPT Thu May 14 09:49:02 KST 2026 aarch64 GNU/Linux`
- `cat /proc/version`:
  - same base commit `gc21449208550`
- config evidence:
  - `CONFIG_TI_K3_AM65_CPSW_NUSS=y`
  - `CONFIG_TI_K3_AM65_CPSW_SWITCHDEV=y`
  - `CONFIG_TI_AM65_CPSW_QOS=y`
  - `CONFIG_BRIDGE_VLAN_FILTERING=y`
  - `CONFIG_NET_SCH_MQPRIO=m`
  - `CONFIG_NET_SCH_TAPRIO=m`
  - `CONFIG_NET_SCH_CBS=m`
  - `CONFIG_NET_CLS_FLOWER=m`
  - `CONFIG_NET_ACT_SKBEDIT=m`

판단:

- SK running kernel도 local source와 **같은 base commit hash**를 사용한다.
- SK version string에는 `-dirty`가 없어서 TMDS보다 source 일치성이 더 높다.

## 4. Source Search Result

### RX_REMAP_VLAN Presence

결론부터 말하면, **현재 local TI SDK 12 kernel source에는 이미 있다.**

파일:

- `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-nuss.c`

확인된 코드:

```c
#define AM65_CPSW_P0_REG_CTL_RX_REMAP_VLAN BIT(16)
```

- 위치: `am65-cpsw-nuss.c:92`

그리고 open/init 시점에 실제 enable도 하고 있다.

```c
writel(AM65_CPSW_P0_REG_CTL_RX_CHECKSUM_EN |
       AM65_CPSW_P0_REG_CTL_RX_REMAP_VLAN,
       host_p->port_base + AM65_CPSW_P0_REG_CTL);
```

- 위치: `am65-cpsw-nuss.c:1031-1032`

즉 이번 source tree는 사용자가 제시한 “checksum만 enable하고 remap은 빠진” 상태가 아니다.

### Related QoS Source

파일:

- `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-qos.c`

핵심 주석:

```c
 * Queues get mapped to Channels (thread_id),
 *     if not VLAN tagged, thread_id is used as packet_priority
 *     if VLAN tagged. VLAN priority is used as packet_priority
 * packet_priority gets mapped to header_priority in p0_rx_pri_map,
 * header_priority gets mapped to switch_priority in pn_tx_pri_map.
 * As p0_rx_pri_map is left at defaults (0x76543210), we can
 * assume that Queue_n gets mapped to header_priority_n. We can then
 * set the switch priority in pn_tx_pri_map.
```

- 위치: `am65-cpsw-qos.c:255-265`

이 주석은 CPSW QoS 경로를 다음처럼 설명한다.

```text
VLAN PCP -> packet_priority
packet_priority -> p0_rx_pri_map -> header_priority
header_priority -> pn_tx_pri_map -> switch_priority / FIFO
```

또한 `mqprio` 적용 시 `AM65_CPSW_PN_REG_TX_PRI_MAP`를 실제로 프로그램한다.

- `am65-cpsw-qos.c:281`

### Switchdev Source

파일:

- `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-switchdev.c`
- `workspace/ti-linux-kernel-sdk12/Documentation/networking/device_drivers/ethernet/ti/am65_nuss_cpsw_switchdev.rst`

문서상 필수 조건:

- `devlink ... switch_mode value true`
- 포트를 `UP` 시킨 후 bridge join
- `bridge vlan add dev br0 vid 1 pvid untagged self`
- `vlan_filtering=1`이면 CPU port VLAN self entry가 mandatory

현재 steady-state SK는 이 공식 switchdev 상태가 아니다.

- `switch_mode = false`
- `br-tsn vlan_filtering = 0`

## 5. Upstream/TI Patch History

### RX_REMAP_VLAN patch itself

TI cgit / upstream-integrated history에서 다음 commit을 확인했다.

- commit: `86e2eca4ddedc07d639c44c990e1c220cac3741e`
- title:
  - `net: ethernet: ti: am65-cpsw: enable p0 host port rx_vlan_remap`
- author date:
  - `2023-03-27`
- committer:
  - `Paolo Abeni`
- committer date:
  - `2023-03-28`

commit 설명 핵심 원문:

```text
By default, the tagged ingress packets to the switch from the host port P0
get internal switch priority assigned equal to the DMA CPPI channel number
they came from, unless CPSW_P0_CONTROL_REG.RX_REMAP_VLAN is enabled.
...
Hence enable CPSW_P0_CONTROL_REG.RX_REMAP_VLAN so packet will preserve
internal switch priority assigned following the VLAN(priority) tag no matter
through which DMA CPPI Channels packets enter the switch.
```

이 설명은 사용자가 제기한 의심점과 정확히 일치한다.

### DSCP remap related patch

- commit: `a208f417582ffc9e73d2e27a41d1d5c67528be5f`
- title:
  - `net: ethernet: ti: am65-cpsw: enable DSCP to priority map for RX`
- committer date:
  - `2024-11-18`

즉 upstream/TI 쪽도 최근까지

- `RX_REMAP_VLAN`
- `DSCP -> priority map`

을 별도 기능으로 계속 다듬고 있었다.

### mqprio channel-mode QoS path

- commit: `90bc21aaef4adaefceda2d385756138fc247c0c2`
- title:
  - `net: ethernet: ti: am65-cpsw: add mqprio qdisc offload in channel mode`
- committer date:
  - `2023-08-16`

이 commit 설명에서 중요한 문구:

```text
VLAN/priority tagged packets mapped to TC0 will exit switch with VLAN tag priority 0
```

그리고 example에 다음이 포함된다.

```bash
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
tc qdisc replace dev eth1 ... mqprio ... hw 1 mode channel
ip link add link eth1 name eth1.100 type vlan id 100
ip link set eth1.100 type vlan egress 0:0 1:1 ... 7:7
```

즉 TI/upstream 공식 QoS path는
단순 VLAN subinterface만이 아니라,

- `p0-rx-ptype-rrobin off`
- `mqprio hw 1 mode channel`

까지 포함한 CPSW QoS configuration을 전제로 한다.

## 6. TRM / SDK Documentation Evidence

Linux kernel source 외에 MCU+ SDK source도 같은 의미를 직접 설명한다.

### MCU+ SDK host port config

파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/include/mod/cpsw_hostport.h`

설명:

```c
/* RX VLAN remap controls whether the hardware switch priority for VLAN
 * tagged or priority tagged packets is determined from CPPI thread number
 * (remap disabled) or via ENET_HOSTPORT_IOCTL_SET_EGRESS_QOS_PRI_MAP
 * (remap enabled) */
bool rxVlanRemapEn;
```

즉 MCU+ SDK 문서도 `RX_REMAP_VLAN` 의미를 다음처럼 규정한다.

```text
disabled: CPPI thread number 기준
enabled : VLAN PCP / egress QoS priority map 기준
```

### MCU+ SDK register programming

파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/src/mod/cpsw_hostport.c`

코드:

```c
cppiP0ControlCfg.p0RxRemapVlan     = hostPortCfg->rxVlanRemapEn ? TRUE : FALSE;
cppiP0ControlCfg.p0RxRemapDscpIpv4 = hostPortCfg->rxDscpIPv4RemapEn ? TRUE : FALSE;
cppiP0ControlCfg.p0RxRemapDscpIpv6 = hostPortCfg->rxDscpIPv6RemapEn ? TRUE : FALSE;
```

### MCU+ SDK EST example

파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/enet_cpsw_est/V1/enet_cpsw_est_cfg.c`

코드:

```c
/* Hardware switch priority is taken from packet's PCP or DSCP */
hostPortCfg->rxVlanRemapEn     = true;
hostPortCfg->rxDscpIPv4RemapEn = true;
hostPortCfg->rxDscpIPv6RemapEn = true;
```

이 근거는 Linux와 MCU+ 모두에서 같은 hardware model을 전제하고 있음을 보여준다.

## 7. Patch Requirement Decision

### Case A: Patch Already Present

이번 source 기준 결론은 **Case A**다.

```text
RX_REMAP_VLAN patch는 현재 local TI SDK 12 kernel source에 이미 포함되어 있다.
```

따라서 현재 `p 0` 현상은
**“RX_REMAP_VLAN patch가 빠져서 발생했다”** 로 정리할 수 없다.

오히려 현재 증거는 다음 해석을 더 강하게 지지한다.

1. `RX_REMAP_VLAN`은 host port `P0` ingress 시 internal switch priority remap 기능이다.
2. 이 비트는 **VLAN PCP -> internal switch priority** 단계에는 직접 관련이 있다.
3. 하지만 지금 사용자가 본 문제 중 하나인
   **CPSW sender direct emission 자체가 `p 0`인 현상**은
   이 비트 하나만으로 설명되지 않는다.

핵심 이유는 다음과 같다.

#### 1. runtime에서 `p0-rx-ptype-rrobin`이 현재 `on`

TMDS와 SK에서 모두 확인:

- `ethtool --show-priv-flags ethX`
  - `p0-rx-ptype-rrobin: on`

그리고 driver는 이 flag가 QoS/taprio와 충돌한다고 직접 말한다.

- `drivers/net/ethernet/ti/am65-cpsw-ethtool.c:754-757`
  - `p0-rx-ptype-rrobin flag conflicts with QOS`
- `drivers/net/ethernet/ti/am65-cpsw-qos.c:893-896`
  - `p0-rx-ptype-rrobin flag conflicts with taprio qdisc`

또한 `am65_cpsw_nuss_set_p0_ptype()`는 rrobin이 켜진 경우
`P0_RX_PRI_MAP`를 `0x0`으로 만들어 사실상 host port receive priority를
FIFO0 쪽으로 몰아버린다.

- `drivers/net/ethernet/ti/am65-cpsw-nuss.c:530-542`

이 상태는 QoS / PCP / FIFO mapping 검증에 불리하다.

#### 2. official CPSW QoS path는 `mqprio hw 1 mode channel`까지 포함한다

현재까지 실패한 CPSW sender 실험은

- VLAN subinterface
- `egress-qos-map`
- `tc skbedit priority`

까지는 적용했지만,
TI 문서와 upstream commit이 전제로 삼는 전체 QoS setup,
즉

- `p0-rx-ptype-rrobin off`
- `mqprio hw 1 mode channel`
- TX queue / TC / FIFO mapping

까지는 current control topology 제약 때문에 안전하게 검증하지 못했다.

특히 TMDS는 `eth0` control도 같은 CPSW common에 묶여 있으므로,
`usage_count > 0` 상태에서는 private flag 변경 자체가 막힌다.

- `drivers/net/ethernet/ti/am65-cpsw-ethtool.c:751-752`
  - `if (common->usage_count) return -EBUSY;`

즉 현재 topology에서는
**공식 QoS expected path를 끝까지 올리기 어려운 구조적 제약**이 있다.

#### 3. steady-state SK는 아직 switchdev QoS path가 아니다

현재 steady-state SK runtime:

- `devlink ... switch_mode = false`
- `br-tsn vlan_filtering = 0`

즉 normal running state는 TI 공식 hardware switchdev + VLAN-aware CPU-port path가 아니라
Linux bridge mode다.

따라서 `TMDS eth2(ICSSG) -> SK -> TMDS eth1(CPSW)` 경로에서 본 `p 0` 결과도
아직은

- Linux bridge forwarding
- host port reinjection
- CPSW QoS mapping
- switchdev offload 미사용

이 섞인 상태의 결과로 봐야 한다.

#### 4. capture artifact 가능성은 상대적으로 낮다

현재 증거에서 capture artifact 가능성을 완전히 0으로 만들 수는 없지만,
우선순위는 낮다.

이유:

- 같은 tcpdump 방식으로 `ICSSG -> SK CPSW receiver` 에서는 실제 `p7/p6`가 보였다.
- TMDS/SK CPSW 포트 모두 `tx-vlan-offload: off [fixed]`, `rx-vlan-offload: off [fixed]` 상태다.

즉 “tcpdump가 non-zero PCP를 아예 못 본다”는 설명보다는,
현재 CPSW runtime classification / QoS path가 기대대로 올라오지 않았다는 설명이 더 설득력 있다.

### Case B: Patch Missing

이번 source 기준으로는 해당하지 않는다.

```text
RX_REMAP_VLAN 관련 최소 패치 후보는 현재 필요 없다.
```

이미 source에 존재하고 enable도 되어 있기 때문이다.

## 8. Verification Plan

현재 상태에서 가장 중요한 다음 검증은
**kernel rebuild보다 runtime QoS prerequisite를 제대로 충족한 상태에서 CPSW PCP emission을 다시 보는 것**이다.

### Prerequisite 0. alternate control path 확보

`p0-rx-ptype-rrobin`을 끄려면 같은 CPSW common 사용을 모두 내려야 할 가능성이 높다.

따라서 다음 중 하나가 필요하다.

1. UART-only 제어
2. 별도 control NIC 경로
3. 동일 보드의 non-CPSW control path

현재 TMDS는 `eth0` control도 같은 CPSW common이므로,
그 상태로는 공식 QoS setup을 끝까지 검증하기 어렵다.

### Prerequisite 1. sender board에서 official QoS mode 적용

sender로 쓸 CPSW board에서:

1. 해당 CPSW common 포트들 down
2. `ethtool --set-priv-flags <port> p0-rx-ptype-rrobin off`
3. 필요 시 `ethtool -L <port> rx 1 tx 8`
4. `tc qdisc replace dev <port> root ... mqprio ... hw 1 mode channel`
5. VLAN subinterface 생성
6. `egress-qos-map 0:0 ... 7:7`
7. `SO_PRIORITY` 또는 `skbedit priority` 로 송신

### Test 1. CPSW host-originated VLAN PCP emission

추천 경로는 control path와 분리 가능한 CPSW sender direct path다.

예:

```bash
ip link add link eth1 name eth1.301 type vlan id 301
ip link set eth1.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
tc qdisc replace dev eth1 root handle 100: mqprio num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 queues 1@0 1@1 2@2 hw 1 mode channel
```

송신은 다음 둘 중 하나:

1. `SO_PRIORITY=7/6`
2. VLAN subinterface egress의 `skbedit priority 7/6`

수신 capture 기대:

```text
vlan 301, p 7
vlan 301, p 6
```

동시에 sender 쪽에서 다음 counter를 전후 비교한다.

```bash
ethtool -S eth1 | grep -Ei "tx_pri|p0_tx_pri|fifo|drop"
```

기대:

- `tx_pri6`
- `tx_pri7`

또는 그에 대응하는 queue/fifo counter 증가

### Test 2. ICSSG PCP injector -> SK CPSW forwarding

이 단계는 sender direct emission이 먼저 통과한 뒤 수행하는 것이 맞다.

경로:

```text
TMDS eth2(ICSSG) -> SK CPSW -> TMDS eth1(CPSW)
```

단, 이 테스트는 **SK를 switchdev 공식 경로로 올린 뒤** 다시 보는 것을 권장한다.

필수 조건:

```bash
devlink dev param set platform/8000000.ethernet name switch_mode value true cmode runtime
ip link set sw-port up
bridge vlan add dev br-tsn vid 1 pvid untagged self
ip link set dev br-tsn type bridge vlan_filtering 1
bridge vlan add dev br-tsn vid <VID> self
bridge vlan add dev eth0 vid <VID> master
bridge vlan add dev eth1 vid <VID> master
```

기대:

```text
vlan <VID>, p 7
vlan <VID>, p 6
```

### Test 3. Queue / priority counter correlation

각 sender/forwarding 테스트마다 반드시 다음을 같이 본다.

```bash
ethtool -S eth0 | grep -Ei "pri|prio|vlan|tx|rx|fifo|drop"
ethtool -S eth1 | grep -Ei "pri|prio|vlan|tx|rx|fifo|drop"
```

현재 baseline에서는 `tx_pri0` 편중이 강하다.

즉 다음 변화가 나와야 의미가 있다.

- test traffic 후 `tx_pri6/7` 증가
- `p0_tx_pri6/7` 또는 port `tx_pri6/7` 증가

## 9. Risks / Rollback

### Risks

1. `p0-rx-ptype-rrobin` 변경은 common usage가 0이어야 할 가능성이 높다.
2. TMDS는 `eth0` control도 CPSW common이므로 test setup이 현재 SSH control을 끊을 수 있다.
3. SK `switch_mode=true` + `vlan_filtering=1` 전환은 현재 bridge/control path를 흔들 수 있다.
4. `mqprio hw 1` 및 queue 재구성은 실험 중 traffic path를 바꾼다.

### Rollback

실험 후 기본 복귀 순서는 다음을 권장한다.

```bash
tc qdisc del dev <port> root
ip link del <port>.<vid>
ethtool -L <port> rx 1 tx 1    # 또는 원래 queue layout
ethtool --set-priv-flags <port> p0-rx-ptype-rrobin on
devlink dev param set platform/8000000.ethernet name switch_mode value false cmode runtime
bash projects/tsn_dscp_pcp/board/apply_tsn_env.sh
```

단, 실제 rollback은 current control path를 잃지 않는 순서로 조정해야 한다.

## 10. Next Action Items

1. `RX_REMAP_VLAN missing patch` 가설은 닫는다.
2. 다음 우선 가설은 다음으로 전환한다.

```text
현재 p0 현상은
RX_REMAP_VLAN 부재보다,
공식 CPSW QoS prerequisite
  - p0-rx-ptype-rrobin off
  - mqprio hw 1 mode channel
  - switchdev/VLAN-aware CPU-port path
가 아직 충족되지 않은 쪽이 더 유력하다.
```

3. control path를 보존한 alternate setup을 먼저 설계한다.
4. 그 뒤 official CPSW sender path를 direct emission 기준으로 재시험한다.
5. direct emission이 통과한 뒤에만 `ICSSG -> SK CPSW -> CPSW receiver` preservation을 다시 본다.
6. 만약 위 조건을 모두 충족해도 계속 `p 0`이면,
   그 다음 patch 후보는 `RX_REMAP_VLAN` backport가 아니라
   `am65-cpsw` TX/tag preservation debug instrumentation 쪽으로 잡는 것이 맞다.
