# SK CPSW TX Fragmentation Root Cause

> 현재 판정: 이 문서는 register, kernel provenance, traffic-rate 비교의 상세 작업 기록이다.
> 후속 CPU pin 시험에서 TMDS도 single-CPU userspace generator 조건에서는 fragment가 0이었다.
> 그러므로 SK 1 Gbps sender를 hardware/spec failure로 판정하지 않는다. 현재 canonical
> 상태와 다음 검증은 [VALIDATION_STATUS.md](../VALIDATION_STATUS.md)를 따른다.

## 목적

이 문서는 다음 질문에 답하기 위해 작성한다.

```text
TMDS eth1 CPSW sender에서는 MACMergeFragCountTx가 증가하는데,
동일한 link, 동일한 Qbu 설정, 동일한 traffic 조건에서
SK eth1 CPSW sender는 왜 MACMergeFragCountTx가 0인가?
```

이 문서는 이미 확정된 사실을 다시 증명하지 않는다.

- TMDS `eth1` sender -> SK receiver에서는 actual Qbu가 동작한다.
- SK `eth1` sender -> TMDS `eth1` receiver에서는 fragment가 0이다.
- SK `eth0` sender -> TMDS `eth2` receiver도 fragment가 0이다.

핵심은 성공 경로와 실패 경로를 같은 datapath 단계에 놓고,
**최초로 달라지는 지점**을 찾는 것이다.

## 비교 대상

### Golden success

```text
A. TMDS eth1 sender -> SK eth1 receiver
```

### Known failure

```text
B. SK eth1 sender -> TMDS eth1 receiver
```

보강 failure:

```text
C. SK eth0 sender -> TMDS eth2 receiver
```

## 결론 요약

### Root cause

```text
SK sender failure의 최초 divergence는 userspace 설정, mqprio offload, TX queue 수,
slave-port register target, preemptible mask, 또는 kernel provenance 차이가 아니다.

동일 kernel provenance(TMDX dirty Image)로 SK를 수동 부팅해도,
SK sender는 여전히 MACMergeFragCountTx=0 이었다.

따라서 최초 divergence는 software-visible configuration 이후에 있다.
100 Mbps에서는 actual Qbu가 확인됐지만, 현재 1 Gbps 시험은 실제 preemptible
line-rate를 850 Mbps 이상으로 만들지 못했다. 그러므로 1 Gbps IET TX failure와
traffic overlap 부족 중 어느 쪽인지는 아직 확정할 수 없다.
```

### Evidence

```text
TMDS success와 SK failure는 아래 단계까지 모두 동일하다.

skb priority
 -> tc filter hit
 -> mqprio traffic class
 -> Linux TX queue
 -> common TX DMA channel(q_idx 매핑)
 -> slave-port TX priority map(0x00003210)
 -> preemptible TC mask(0x07)
 -> IET ctrl(0x00070105 in force-mode)
 -> TX active on

그러나 traffic run 후 실제 divergence는 다음이다.

TMDS sender success:
  - MACMergeFragCountTx 증가
  - iet_tx_frag 증가
  - qdisc requeues 존재(예: 13)

SK sender failure:
  - MACMergeFragCountTx = 0
  - iet_tx_frag = 0
  - qdisc requeues = 0
```

### Why it prevents Qbu

```text
MAC Merge TX fragmentation은 preemptible frame이 실제 송신 중일 때
express frame이 끼어들어야 발생한다.

SK sender는 register 관점에서는 preemption이 armed 상태이고,
100 Mbps에서는 fragment path도 정상 진입한다. 1 Gbps의 fragment counter가 0인
이유는 충분한 overlap을 아직 입증하지 못했으므로 미확정이다.
```

### Fix or workaround

```text
직접 수정 대상은 아직 특정되지 않았다. 우선 1 Gbps에서 실제 preemptible rate를
850~950 Mbps로 만들고, high-PPS express traffic을 병행하는 시험이 필요하다.

우선순위:
1. kernel-level generator로 saturation 조건을 만든다.
2. priority byte counter로 actual rate와 express PPS를 입증한다.
3. saturation에서도 실패할 때 PHY/RGMII 및 CPSW MAC register를 비교한다.
```

### Remaining uncertainty

```text
SK 1 Gbps에서 IET TX fragment가 발생하지 않는 직접 원인은 아직 확정되지 않았다.
먼저 충분한 mid-frame overlap을 만들었는지를 priority byte counter로 입증해야 한다.
그 뒤에도 실패하면 SK DP83867 PHY 설정, RGMII timing/clock, 또는 1 Gbps mode에서만
달라지는 CPSW MAC/PHY interface state를 조사한다.
```

## 1. 단계별 비교표

### 1.1 환경 / 드라이버 / DTB

| 항목 | A. TMDS eth1 sender | B. SK eth1 sender | 판정 |
|---|---|---|---|
| board | TMDS64EVM | SK-AM64B | 다름 |
| sender driver | `am65-cpsw-nuss` | `am65-cpsw-nuss` | 동일 |
| sender bus-info | `8000000.ethernet` | `8000000.ethernet` | 동일 |
| CPSW version | `0x6BA80903` | `0x6BA80903` | 동일 |
| quirks | `00000006` | `00000006` | 동일 |
| live DTB port id | `eth1 -> port@2` | `eth1 -> port@2` | 동일 |
| phy-mode | `rgmii-rxid` | `rgmii-rxid` | 동일 |
| PHY | `DP83869` | `DP83867` | 다름 |
| RGMII warning | 존재 | 존재 | 동일 |

### 1.2 kernel provenance

초기 비교 시에는 다음 차이가 있었다.

| 항목 | A. TMDS eth1 sender | B. SK eth1 sender | 판정 |
|---|---|---|---|
| running kernel | `6.18.13-ti-00778-gc21449208550-dirty` | `6.18.13-gc21449208550` | 다름 |

하지만 이 차이는 root cause가 아니었다.

추가 실험:

```text
SK를 U-Boot에서 직접
  /boot/Image-6.18.13-ti-00778-gc21449208550-dirty
  + SK DTB
  + 기존 rootfs
로 수동 부팅한 뒤 재시험했다.
```

결과:

- SK dirty-kernel sender도 여전히 `MACMergeFragCountTx = 0`

따라서 다음 가설은 기각된다.

```text
TMDS와 SK의 kernel image provenance 차이 때문에 fragment가 갈린다.
```

## 2. Datapath 단계별 비교

| 단계 | A. TMDS success | B. SK failure | 판정 |
|---|---|---|---|
| skb priority | UDP5002 -> prio2, UDP5003 -> prio3 | 동일 | 동일 |
| tc filter hit | 증가 | 증가 | 동일 |
| mqprio mode | `dcb` | `dcb` | 동일 |
| `fp` bitmap | `P P P E` | `P P P E` | 동일 |
| TX queue count | `4` | `4` | 동일 |
| qdisc class packet/byte | TC2/TC3 증가 | TC2/TC3 증가 | 동일 |
| Linux TX queue 선택 | q2/q3 | q2/q3 | 동일 |
| TX DMA channel 선택 | `common->tx_chns[q_idx]` | 동일 | 동일 |
| slave-port `tx_pri2/3` | 증가 | 증가 | 동일 |
| `TX_PRI_MAP` | `0x00003210` | `0x00003210` | 동일 |
| preemptible mask | `0x07` | `0x07` | 동일 |
| `IET_CTRL` force-mode | `0x00070105` | `0x00070105` | 동일 |
| TX active | `on` | `on` | 동일 |
| `MACMergeFragCountTx` | 증가 | `0` | 다름 |
| `iet_tx_frag` | 증가 | `0` | 다름 |
| qdisc requeues | 존재 | `0` | 다름 |

최초로 명확하게 달라지는 software-visible 지점은 다음이다.

```text
traffic run 이후 sender-side runtime queue/FIFO behavior
```

## 3. Queue -> DMA channel -> CPSW FIFO mapping

현재 kernel source 기준 mapping은 다음과 같다.

### 3.1 mqprio -> Linux TX queue

`mqprio num_tc 4 queues 1@0 1@1 1@2 1@3` 이므로:

- TC2 -> queue2
- TC3 -> queue3

### 3.2 Linux TX queue -> DMA channel

`am65_cpsw_nuss_ndo_slave_xmit()`:

```c
q_idx = skb_get_queue_mapping(skb);
tx_chn = &common->tx_chns[q_idx];
```

즉:

- queue2 -> DMA channel 2
- queue3 -> DMA channel 3

이 경로는 board-dependent 분기가 없다.

### 3.3 DMA channel -> slave-port priority FIFO

`am65_cpsw_setup_mqprio()`는 다음을 쓴다.

```text
TX_PRI_MAP = 0x00003210
```

의미:

- queue2 -> switch priority2
- queue3 -> switch priority3

실측에서도:

- TMDS success sender: `tx_pri2`, `tx_pri3` 증가
- SK failure sender: `tx_pri2`, `tx_pri3` 증가

따라서 다음 질문의 답은 `예`다.

```text
SK에서 tx_pri2와 tx_pri3가 증가하는 것은
실제 slave-port priority FIFO까지는 동일하게 진입했다는 뜻이다.
```

즉 divergence는 queue-to-channel-to-FIFO mapping 이전이 아니다.

## 4. Register target port와 bit 해석

### 4.1 코드상 port target

`am65-cpsw-nuss.c`:

```c
port->port_id = DT port@N/reg
port->port_base = cpsw_base + 0x1000 + 0x1000 * port_id
```

즉:

- `eth0 -> port_id 1 -> 0x...22000`
- `eth1 -> port_id 2 -> 0x...23000`

### 4.2 실측 isolate

SK에서 `eth1`만 clean하게 다시 설정했을 때:

```text
before eth0: TX_PRI_MAP=0x00000000, IET_CTRL=0x00070104
before eth1: TX_PRI_MAP=0x00000000, IET_CTRL=0x00000104

after configuring eth1 only:
  eth0: TX_PRI_MAP=0x00000000, IET_CTRL=0x00070104
  eth1: TX_PRI_MAP=0x00003210, IET_CTRL=0x00070105
```

판정:

- `eth1` 설정이 `eth0` register를 덮지 않는다.
- port target 오류는 root cause가 아니다.

### 4.3 TMDS golden sender clean 상태

TMDS `eth1`에서도 clean 상태에서:

```text
before eth1: TX_PRI_MAP=0x00000000, IET_CTRL=0x00000104
after  eth1: TX_PRI_MAP=0x00003210, IET_CTRL=0x00070105
```

즉 golden success와 failing SK sender는 software-visible register state가 동일하다.

### 4.4 bit 해석

`IET_CTRL = 0x00070105`

- bit0 = `1` -> TX preemption enable
- bit2 = `1` -> verify disabled(force-mode)
- bits[23:16] = `0x07` -> TC0~TC2 preemptible

`TX_PRI_MAP = 0x00003210`

- queue0 -> prio0
- queue1 -> prio1
- queue2 -> prio2
- queue3 -> prio3

## 5. Driver 호출 흐름

### 5.1 MM 설정

`drivers/net/ethernet/ti/am65-cpsw-ethtool.c`

- `am65_cpsw_set_mm()`
  - `AM65_CPSW_PN_REG_MAX_BLKS` 변경
  - `am65_cpsw_port_iet_rx_enable()`
  - `am65_cpsw_port_iet_tx_enable()`
  - `IET_CTRL`에 `PENABLE`, `DISABLEVERIFY`, addFragSize 적용
  - `am65_cpsw_iet_commit_preemptible_tcs()` 호출

### 5.2 mqprio 설정

`drivers/net/ethernet/ti/am65-cpsw-qos.c`

- `am65_cpsw_setup_mqprio()`
  - `netdev_set_num_tc()`
  - `netdev_set_tc_queue()`
  - `writel(tx_prio_map, port->port_base + AM65_CPSW_PN_REG_TX_PRI_MAP)`
  - `am65_cpsw_iet_change_preemptible_tcs()`
  - 내부에서 `am65_cpsw_iet_commit_preemptible_tcs()` 재호출

### 5.3 link up

`drivers/net/ethernet/ti/am65-cpsw-nuss.c`

- `am65_cpsw_nuss_mac_link_up()`
  - MAC SL control set
  - ALE forward enable
  - `am65_cpsw_qos_link_up()`

`drivers/net/ethernet/ti/am65-cpsw-qos.c`

- `am65_cpsw_qos_link_up()`
  - `port->qos.link_speed` 갱신
  - `am65_cpsw_iet_link_state_update()`
  - 내부에서 `am65_cpsw_iet_commit_preemptible_tcs()`

### 5.4 actual TX

`drivers/net/ethernet/ti/am65-cpsw-nuss.c`

- `am65_cpsw_nuss_ndo_slave_xmit()`
  - `q_idx = skb_get_queue_mapping(skb)`
  - `tx_chn = &common->tx_chns[q_idx]`
  - `cppi5_desc_set_tags_ids(..., port->port_id)`
  - `k3_udma_glue_push_tx_chn()`

판정:

코드상으로도 sender path는 queue/channel 선택 이후 board-specific 분기가 보이지 않는다.
따라서 divergence는 source-level mapping 로직보다는 **runtime queue service / FIFO occupancy** 쪽이다.

## 6. 공용 자원과 port별 자원

### 공용(`am65_cpsw_common`)

- `tx_chns[]`
- `tx_ch_num`
- `usage_count`
- `iet_enabled`
- `cpsw_base`

### port별(`am65_cpsw_port`)

- `port_id`
- `port_base`
- `stat_base`
- `qos.iet.preemptible_tcs`
- `qos.link_speed`
- `slave.phy_if`

판정:

- TX channel array는 instance 공용이지만,
  isolate 시험에서는 다른 port를 down한 상태로 active sender만 사용했다.
- port-target cross-write도 없었다.

따라서 다음 가설은 기각된다.

```text
다른 CPSW port의 state가 active sender의 register를 덮어 fragment를 막는다.
```

## 7. DTB 차이

live DTB 기준 요약:

### 공통점

- 둘 다 CPSW node는 `/bus@f4000/ethernet@8000000`
- `eth1 -> port@2`
- `phy-mode = "rgmii-rxid"`
- driver는 동일 `am65-cpsw-nuss`

### 차이점

- SK `eth1`: direct MDIO, `DP83867`
- TMDS `eth1`: mdio-mux behind CPSW, `DP83869`

판정:

SK가 receiver로 정상 reassembly를 수행한다는 사실만으로 sender-side PHY/RGMII
조건을 배제할 수는 없다. 2026-07-13 시험에서 SK sender가 100 Mbps에서는 fragment를
생성하고 1 Gbps에서는 생성하지 않았으므로, SK의 1 Gbps PHY/RGMII/MAC interface
state가 최우선 확인 대상이다. verify는 force mode에서도 동일했으므로 후순위다.

## 8. 원인 우선순위 재판정

사용자가 제시한 우선순위에 대해 현재 판정은 다음과 같다.

1. SK `mqprio fp`에서 HW queue/FIFO mapping이 TMDS와 다름
   - 기각

2. SK eth1 slave-port index 또는 register 대상 오류
   - 기각

3. CPSW 공용 TX channel/IET state가 두 포트 사이에서 충돌
   - 1차 기각

4. port open/TX channel 변경 과정에서 IET mask가 유실됨
   - 기각

5. 실제 traffic overlap 부족
    - 현재 최우선 검증 대상

6. SK DP83867의 1 Gbps PHY/RGMII/MAC interface state
    - overlap을 입증한 뒤에도 실패할 때 조사

7. DTS/DTB의 SK 1 Gbps PHY timing 또는 clock 설정 차이
    - overlap을 입증한 뒤에도 실패할 때 조사

8. driver/kernel의 SK-AM64B port-specific bug
    - kernel image provenance는 기각됐지만, PHY driver 또는 MAC link-mode path는 미확인

## 9. 가장 유력한 root cause

현재 확정 가능한 root-cause 범위는 다음이다.

```text
SK CPSW sender는 TMDS golden sender와 동일한 configured state에 도달하며,
100 Mbps에서는 actual IET fragmentation도 수행한다.

1 Gbps에서 fragment counter가 0인 것은 확정됐지만, 현재 generator가 만든 실제
preemptible rate는 최대 약 409 Mbps였다. 따라서 1 Gbps IET datapath failure가 아니라
1500-byte frame의 약 12 us wire-time 내에 express packet이 도착하지 않은 결과일 수 있다.
```

이 결론을 지지하는 이유:

1. userspace 설정은 동일하다.
2. queue/channel/priority map도 동일하다.
3. register target도 동일하다.
4. same TMDS dirty kernel로 SK를 부팅해도 실패한다.
5. 1 Gbps의 기존 traffic은 actual preemptible line-rate를 입증하지 못했다.

즉 kernel image 차이는 배제됐지만, 1 Gbps failure의 최초 divergence는 아직 판정 불가다.

## 10. 2026-07-13 Link-Speed Controlled Trial

### 시험 조건

```text
sender: SK eth1 (CPSW, DP83867)
receiver: TMDS eth1 (CPSW, DP83869)
IET: force mode, pmac-enabled on, tx-enabled on, verify-enabled off,
     tx-min-frag-size 124
mqprio: TC2 preemptible, TC3 express
```

양쪽의 pause 실제 적용값은 모두 RX/TX `off`였다. SK는 EEE 미지원이고 TMDS는
EEE disabled 상태였으므로, pause/EEE는 이 시험에서의 차이가 아니었다.

### 결과

| Link mode | SK sender traffic (30 s) | SK `MACMergeFragCountTx` delta | TMDS `MACMergeFragCountRx` delta | 판정 |
|---|---:|---:|---:|---|
| 100 Mbps full, autoneg off | TC2 80M + TC3 10M | +25,130 | +25,130 | actual Qbu 성공 |
| 1 Gbps full, autoneg on | TC2 약 354M (`iperf3 -P4`) + TC3 약 86M | 0 | 0 | overlap 조건 미입증 |

추가 1 Gbps `netperf` 시험에서는 data port를 TC2/TC3로 명시적으로 분류하고 counter를
측정했다. 단일 1472-byte TC2 stream은 약 409 Mbps였고, 64-byte TC3 stream을 병행하면
TC2는 약 202 Mbps, TC3는 약 16 Mbps, `iet_tx_frag` delta는 0이었다. SK의 단일 CPU에서
userspace generator가 saturation을 만들지 못했으므로 이 결과도 IET failure 판정 근거가 아니다.

### TMDS/SK 동일 generator 비교

2026-07-13에 동일한 1 Gbps link, force-mode IET, `mqprio fp P P P E`, `netperf`
UDP data port classification(TC2: 1472-byte port 40002, TC3: 64-byte port 40003)을 적용했다.

| Sender | TC2 counter rate | TC2 packet rate | TC3 counter rate | TC3 packet rate | `iet_tx_frag` delta |
|---|---:|---:|---:|---:|---:|
| SK eth1 | 약 202 Mbps | 약 16.7 kpps | 약 16 Mbps | 약 18.3 kpps | 0 |
| TMDS eth1 | 약 418 Mbps | 약 34.4 kpps | 약 33 Mbps | 약 37.4 kpps | +509,379 |
| TMDS eth1, 두 netperf process를 CPU 0에 pin | 약 243 Mbps | 약 20.0 kpps | 약 23 Mbps | 약 25.6 kpps | 0 |

TMDS sender는 두 process를 각각 실행할 수 있는 2-core 조건에서는 SK보다 약 2배의
TC2/TC3 packet rate를 만들고 actual fragmentation을 수행했다. TMDS의 두 process를
CPU 0 하나에 pin하면 fragment가 0이 됐다. 이는 average requested rate가 아니라 sender의
실제 packet timing, burst 및 CPU scheduling/queue service가 overlap 발생을 좌우한다는
직접 증거다. 이 시험은 SK의 CPSW/IET hardware failure를 증명하지 않는다.

이 고부하 시험에서 SK receiver는 `iet_rx_frag +477,628`, `iet_rx_assembly_ok +477,627`을
기록했으나 SMD/assembly error도 증가했다. 따라서 sender fragment 발생 비교에는 유효하지만,
오류 없는 최종 validation profile로 사용하지 않는다.

100 Mbps 시험에서 TMDS receiver의 `MACMergeFrameAssOkCount`도 `+25,123`이었고,
assembly/smd error counter는 증가하지 않았다. 따라서 SK sender의 MAC Merge/IET
TX hardware path와 TMDS receiver reassembly path는 정상이다.

### 해석

```text
SK sender의 문제는 IET enable, mqprio mapping, kernel image, 또는 IET block 자체의
일반적 불능이 아니다. 동일한 SK eth1과 같은 force-mode 설정에서 100 Mbps는 actual
fragment/reassembly를 수행한다.

1 Gbps에서 공식 200M + 50M 조건과 실제 약 440M aggregate traffic은 fragment가 0이었다.
그러나 이 traffic은 1 Gbps link를 포화시키지 않았으므로 overlap 부족 가설을 배제하지 못한다.
```

`AM65_CPSW_PN_REG_FIFO_STATUS`는 FIFO occupancy를 제공하지 않는다. 이 register의
`TX_PRI_ACTIVE`와 `TX_E_MAC_ALLOW`는 상태 비트일 뿐이므로 xmit trace만으로
"FIFO overlap 부재"를 증명할 수 없다. 해당 trace는 다음 원인 규명 수단으로 채택하지
않는다.

### 다음 확인

1. kernel `pktgen` 또는 동등한 kernel-level generator를 준비해 TC2 actual rate를 850~950 Mbps로 유지한다.
2. 64~256-byte high-PPS express traffic을 TC3에 동시에 넣고 `tx_pri2_bcnt`, `tx_pri3_bcnt`, `iet_tx_frag` delta를 계산한다.
3. 위 조건에서도 fragment가 0일 때만 SK DP83867 PHY/RGMII 및 CPSW MAC link-mode register를 100 Mbps 성공 상태와 비교한다.

## 11. 수정 대상 파일/함수/설정

현재 단계에서 직접 수정 대상은 아직 확정되지 않았다.

우선 분석 대상은 다음이다.

- SK live DTB의 DP83867 PHY node와 RGMII delay/clock properties
- `drivers/net/phy/dp83867.c`의 1 Gbps-specific PHY programming
- CPSW port/MAC control 및 flow-control register의 100 Mbps/1 Gbps 비교 dump

`am65_cpsw_nuss_ndo_slave_xmit()`의 xmit trace와 `FIFO_STATUS`는 Linux descriptor
enqueue 및 priority-active 상태만 보여 주며 FIFO occupancy 또는 MAC merge preemption
시점을 증명하지 못한다. 따라서 이 가설의 우선 검증 수단으로 사용하지 않는다.
