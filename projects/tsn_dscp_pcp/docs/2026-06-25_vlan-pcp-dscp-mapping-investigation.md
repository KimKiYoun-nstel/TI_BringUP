# AM64x VLAN PCP / DSCP Mapping Investigation

## 1. Local TI SDK Reference Search

### Found Documents

- `workspace/ti-linux-kernel-sdk12/Documentation/networking/device_drivers/ethernet/ti/am65_nuss_cpsw_switchdev.rst`
  - AM65/AM64 CPSW switchdev 공식 문서
  - `devlink switch_mode`, `bridge vlan add`, `vlan_filtering`, CPU port VLAN self entry 요구사항 포함
- `workspace/ti-linux-kernel-sdk12/Documentation/networking/devlink/am65-nuss-cpsw-switch.rst`
  - AM65/AM64 CPSW devlink parameter 문서
  - `switch_mode`가 runtime driver-specific parameter임을 설명
- `workspace/ti-linux-kernel-sdk12/Documentation/networking/device_drivers/ethernet/ti/cpsw.rst`
  - TI CPSW QoS 예제 문서
  - `mqprio`, `cbs`, VLAN subinterface, `egress` QoS map, `SO_PRIORITY` 예시 포함
  - 예제는 AM572x/BBB 기준이지만 Linux/QoS 경로 설명에는 직접 참고 가치가 큼
- `workspace/ti-linux-kernel-sdk12/Documentation/networking/device_drivers/ethernet/ti/icssg_prueth.rst`
  - ICSSG PRUETH 공식 문서
  - tagged / priority-tagged / untagged / not-member VLAN drop 관련 firmware stat 항목 설명

### Found Example Commands

TI 문서에서 직접 확인한 대표 명령:

```bash
devlink dev param set platform/c000000.ethernet name switch_mode value true cmode runtime

ip link add name br0 type bridge
ip link set dev br0 type bridge ageing_time 1000
ip link set dev sw0p1 up
ip link set dev sw0p2 up
ip link set dev sw0p1 master br0
ip link set dev sw0p2 master br0
bridge vlan add dev br0 vid 1 pvid untagged self

bridge vlan add dev sw0p1 vid 100 pvid untagged master
bridge vlan add dev sw0p2 vid 100 pvid untagged master
bridge vlan add dev br0 vid 100 pvid untagged self

ip link add link eth0 name eth0.100 type vlan id 100
ip link set eth0.100 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7

tc qdisc replace dev eth0 handle 100: parent root mqprio num_tc 3 \
  map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 queues 1@0 1@1 2@2 hw 1
```

### Relevant Kernel Source

- `include/linux/if_vlan.h`
  - `vlan_dev_get_egress_qos_mask()`
  - `skb->priority`를 VLAN PCP mask로 변환하는 generic Linux 경로 확인
- `net/8021q/vlan_dev.c`
  - `vlan_tci |= vlan_dev_get_egress_qos_mask(dev, skb->priority);`
  - generic 802.1Q sender path가 원래는 `skb priority -> PCP` 반영을 의도함을 확인
- `drivers/net/ethernet/ti/am65-cpsw-qos.c`
  - AM65/AM64 QoS 구현 핵심
  - 코드 주석상 `if VLAN tagged, VLAN priority is used as packet_priority`
  - `packet_priority -> header_priority -> switch_priority` 매핑 설명 포함

## 2. Current Test Topology

```text
Host
  -> TMDS eth0 192.168.0.220
  -> SSH jump
  -> SK br-tsn 10.50.0.2

TMDS eth1 <-> SK eth0
TMDS eth2 <-> SK eth1
```

현재 SK:

- `eth0`: `master br-tsn`
- `eth1`: `master br-tsn`
- `br-tsn`: `10.50.0.2/24`

현재 TMDS:

- `eth0`: control
- `eth1`: CPSW endpoint path
- `eth2`: ICSSG endpoint path

## 3. Previous Failure Summary

기존까지 확인된 실패 요약:

1. SK 2-port bridge 자체는 정상
2. DSCP/TOS는 bridge를 지나 보존됨
3. VLAN tag도 bridge를 지나 보존됨
4. 그러나 VLAN PCP는 계속 `p 0`
5. `tc flower + skbedit priority 6`
6. `SO_PRIORITY=6`
7. `egress-qos-map 0:6 ... 7:6`

모두 시도했지만 이전 관측에서는 계속 `p 0`이었다.

## 4. Hypothesis

초기 가설은 다음과 같았다.

```text
physical interface egress가 아니라
VLAN subinterface egress에서 skb priority를 먼저 세팅해야,
VLAN tag 생성 시 PCP로 반영될 수 있다.
```

즉 TI 예제 경로는 다음으로 해석했다.

```text
application / iperf / UDP
  -> VLAN subinterface egress tc filter
  -> action skbedit priority N
  -> VLAN egress-qos-map
  -> VLAN tag 생성 시 PCP N
  -> physical TX
```

## 5. TI Reference Path

### Sender Path

generic Linux VLAN path:

```text
skb->priority
  -> vlan_dev_get_egress_qos_mask()
  -> vlan_tci |= qos mask
  -> 802.1Q tag PCP 반영
```

TI QoS driver path (`am65-cpsw-qos.c`):

```text
if VLAN tagged:
  VLAN priority -> packet_priority
if untagged:
  thread_id -> packet_priority
packet_priority -> header_priority -> switch_priority
```

### Switch Path

TI AM65/AM64 switchdev 문서는 다음을 요구한다.

- `devlink ... switch_mode value true`
- 포트를 `UP` 시킨 후 bridge join
- `bridge vlan add dev br0 vid 1 pvid untagged self` mandatory
- `vlan_filtering=1`이면 CPU port VLAN self entry를 명시적으로 넣어야 함

현재 SK는 아직:

- `switch_mode = false`
- `br-tsn vlan_filtering = 0`

상태다.

## 6. Improvement Test Plan

### Test A: TMDS eth1.100 CPSW VLAN PCP emission

적용한 경로:

```bash
ip netns exec ep1 ip link add link eth1 name eth1.100 type vlan id 100
ip netns exec ep1 ip link set eth1.100 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip netns exec ep1 tc qdisc add dev eth1.100 clsact
ip netns exec ep1 tc filter add dev eth1.100 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff action skbedit priority 7
ip netns exec ep1 tc filter add dev eth1.100 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff action skbedit priority 6
```

SK ingress capture:

```bash
tcpdump -i eth0 -e -vvv -n vlan and udp
```

### Test B: TMDS eth2.100 ICSSG VLAN PCP emission

동일 구조를 `eth2.101`에 적용:

```bash
ip netns exec ep2 ip link add link eth2 name eth2.101 type vlan id 101
ip netns exec ep2 ip link set eth2.101 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip netns exec ep2 tc qdisc add dev eth2.101 clsact
ip netns exec ep2 tc filter add dev eth2.101 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff action skbedit priority 7
ip netns exec ep2 tc filter add dev eth2.101 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff action skbedit priority 6
```

SK ingress capture:

```bash
tcpdump -i eth1 -e -vvv -n vlan and udp
```

### Test C: SK CPSW switch_mode and vlan_filtering check

비파괴 확인만 수행:

```bash
devlink dev show
devlink dev param show platform/8000000.ethernet
ip -d link show br-tsn
bridge link
bridge vlan show
```

### Test D: mqprio/CBS/taprio readiness check

문서/driver/source 기준 readiness 확인 위주로 수행:

- SK `eth0`/`eth1` TX queue 개수: `8`
- SK `switch_mode`: `false`
- 공식 source: `am65-cpsw-qos.c`
- 공식 example: `cpsw.rst`

## 7. Expected Results

성공 기대:

```text
eth1.100 sender -> SK eth0 ingress:
  dport 5001 => p 7
  dport 5002 => p 6

eth2.101 sender -> SK eth1 ingress:
  dport 5001 => p 7
  dport 5002 => p 6
```

실패 해석:

```text
둘 다 p 0이면
TMDS image/kernel/iproute2/tc/VLAN path 공통 문제 의심
```

## 8. Actual Results

### Test A actual: TMDS eth1.100 CPSW egress

`tc filter` hit counter는 실제로 증가했다.

```text
match dport 5001 -> action skbedit priority 7: used yes
match dport 5002 -> action skbedit priority 6: used yes
```

SK `eth0` ingress capture:

```text
10.100.0.1 > 10.100.0.2.5001: vlan 100, p 0
10.100.0.1 > 10.100.0.2.5002: vlan 100, p 0
```

즉:

```text
eth1.100 (CPSW) sender path에서는
VLAN subinterface egress에서 skbedit priority를 걸어도 PCP가 0으로 유지되었다.
```

### Test B actual: TMDS eth2.101 ICSSG egress

`tc filter` hit counter:

```text
dport 5001 -> priority 7: 1 pkt hit
dport 5002 -> priority 6: 1 pkt hit
```

SK `eth1` ingress capture:

```text
10.101.0.1 > 10.101.0.2.5001: vlan 101, p 7
10.101.0.1 > 10.101.0.2.5002: vlan 101, p 6
```

즉:

```text
eth2 (ICSSG) egress에서는
TI 방식 VLAN subinterface egress tc skbedit priority -> PCP emission이 정상 동작했다.
```

### Additional check: SK CPSW direct sender

사용자 우려대로, SK 자체도 `eth0`, `eth1` 모두 CPSW이므로 sender path를 직접 검증했다.

실험:

- SK `eth0.200` -> TMDS `eth1.200`
- SK `eth1.201` -> TMDS `eth2.201`
- 각 VLAN subinterface에 TI 방식 `tc skbedit priority 7/6` 적용

결과:

- `tc` action hit counter는 증가
- 그러나 TMDS 수신 capture는 둘 다 계속 `p 0`

대표 관측:

```text
SK eth0.200 -> TMDS eth1.200:
  vlan 200, p 0, dport 5001
  vlan 200, p 0, dport 5002

SK eth1.201 -> TMDS eth2.201:
  vlan 201, p 0, dport 5001
  vlan 201, p 0, dport 5002
```

즉 현재 이미지 기준으로는:

```text
SK의 CPSW port sender path도 PCP emission이 되지 않는다.
```

### Additional check: ICSSG sender through SK bridge to CPSW receiver

다음 경로도 확인했다.

```text
TMDS eth2(ICSSG) -> SK(br-tsn Linux bridge) -> TMDS eth1(CPSW)
```

여기서 TMDS `eth2.301` sender는 direct sender 실험에서 `p7/p6` emission이 가능한 경로다.

그러나 SK를 통과해 TMDS `eth1`에서 관측하면:

```text
vlan 301, p 0, dport 5001
vlan 301, p 0, dport 5002
```

이 되었다.

이 결과는 다음을 의미한다.

```text
현재 SK Linux bridge mode에서
ICSSG가 만든 non-zero PCP가
SK CPSW egress를 거치며 p0로 나가는 쪽으로 보인다.
```

### Test C actual: SK switch_mode / bridge state

SK 확인 결과:

- `devlink dev show`: `platform/8000000.ethernet`
- `devlink dev param show platform/8000000.ethernet`
  - `switch_mode = false`
- `br-tsn vlan_filtering = 0`
- `bridge vlan show`
  - `eth0`, `eth1`, `br-tsn` 모두 기본 VLAN `1 PVID Egress Untagged`

즉 현재 SK는 TI CPSW switchdev 모드가 아니라 Linux bridge 기반 상태다.

추가 시도:

- UART fallback을 사용해 SK에서 runtime `switch_mode=true` 및 `br-tsn vlan_filtering=1` 전환 자체는 성공
- `devlink`에서 `switch_mode=true` 확인
- `bridge vlan show`에서 `vid 301` membership도 확인

하지만:

- 이후 host-side `ProxyJump -> SK` 경로가 불안정해졌고
- TMDS sender 쪽 VLAN/SSH 경로도 흔들려
- `switch_mode=true` 상태에서의 end-to-end PCP forwarding 결과는 **결정적으로 확보하지 못했다**

따라서 이번 문서에서 switch mode 관련 확정 사실은 다음까지만 남긴다.

```text
runtime switch_mode 전환은 가능하다.
그러나 PCP forwarding pass/fail은 아직 확정하지 못했다.
```

### Test D actual: mqprio/CBS/taprio readiness

공식 source와 현재 시스템 기준:

- SK `eth0`, `eth1` 모두 TX queue `8`
- `am65-cpsw-qos.c`는 `mqprio`/`taprio`/QoS mapping 경로를 구현하고 있음
- 이전 확인 기준 `sch_mqprio`, `sch_taprio`, `cls_flower`, `act_skbedit` module load 가능
- `cpsw.rst`는 `hw 1` 기반 `mqprio`/`cbs` 예시를 제공

이번 턴에서는 실제 `hw 1 mode channel` qdisc apply는 수행하지 않았다.

## 9. Conclusion

현재 가장 설득력 있는 결론은 다음과 같다.

1. **SK bridge는 현재 문제의 핵심이 아니다.**
   - DSCP 보존됨
   - VLAN tag 보존됨
   - ICSSG sender path에서는 direct sender 기준 PCP `7/6`이 실제로 관측됨

2. **TMDS eth1 CPSW sender path가 문제 지점이다.**
   - 같은 TI 방식 `VLAN subinterface egress tc skbedit priority`를 적용해도 `eth1.100`은 계속 `p 0`
   - 반면 `eth2.101` ICSSG는 같은 방식으로 `p 7/p 6` 성공

3. **SK CPSW sender path도 현재는 동일하게 `p 0`이다.**
   - `eth0.200`, `eth1.201` direct sender 모두 `p 0`

4. **현재 Linux bridge mode에서 SK CPSW egress forwarding path도 PCP를 유지하지 못하는 것으로 보인다.**
   - `TMDS eth2(ICSSG)` sender가 direct path에서는 `p7/p6` 가능
   - 그러나 `TMDS eth2 -> SK -> TMDS eth1` 경로에서는 `p0`

5. 따라서 현재 문제는

```text
CPSW sender/egress path
그리고 현재 SK Linux bridge mode의 CPSW forwarding egress path
```

가 아니라,

```text
AM64x CPSW 기반 PCP emission/preservation path 전체
  - TMDS CPSW sender
  - SK CPSW sender
  - SK Linux bridge mode CPSW egress forwarding
```

로 좁혀진다.

6. 질문에 대한 직접 답:

```text
TMDS eth1 sender만의 문제가 아니라,
현재 확인 범위에서는 AM64x CPSW path에서 non-zero PCP emission/preservation이 안 되는 쪽으로 보는 것이 맞다.
```

단,

```text
ICSSG eth2 egress는 non-zero PCP를 실제로 내보낼 수 있다.
```

## 10. Next Action Items

1. CPSW TX path source-level root cause 추가 추적
   - `am65-cpsw-nuss.c`
   - `am65-cpsw-qos.c`
   - VLAN PCP가 실제 wire tag에 들어가는 TX 경로 확인

2. SK `switch_mode=true` 상태에서의 PCP forwarding을 더 안정적으로 재검증
   - UART 기준 통제
   - control path 별도 보존 방안 필요

3. TMDS에서 `eth2(ICSSG)`를 PCP-capable sender 기준 포트로 사용해,
   SK queue/scheduler 실험을 우선 진행하는 우회 경로 검토

4. SK switch side는 다음 단계에서
   - `switch_mode`
   - `vlan_filtering 1`
   - CPU port VLAN self entry
   - `mqprio`/`cbs`/`taprio`
   순으로 별도 검증

5. 필요 시 다음 추가 확인
   - `ethtool -S eth2` firmware counter에서 tagged/priority 관련 변화 추적
   - TMDS CPSW 쪽 PCP emission을 TI 문서/patch history와 비교
   - `eth2(ICSSG)` sender 기준으로 DSCP -> PCP -> SK queue mapping 실험 계속 진행
