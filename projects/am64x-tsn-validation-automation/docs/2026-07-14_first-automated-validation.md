# 2026-07-14 첫 UART 자동 TSN 검증

## 범위

새 automation runner로 아래 두 data cable의 physical pair proof, `shared-clean-v1`
baseline, gPTP, DSCP/PCP, Qbv Phase A, Qbu D1을 순차 실행했다.

```text
SK eth0 <-> TMDS eth1
SK eth1 <-> TMDS eth2
```

모든 board 제어는 `sk`, `tmds` UART daemon을 사용했다. TMDS SSH/management Ethernet은
사용하지 않았다.

## 최종 결과

| 기능 | final run | 판정 | 핵심 증거 |
|---|---|---|---|
| physical preflight | 각 final run | PASS | 양 direct pair 1 Gbps/full 및 ARP source-MAC pair proof |
| shared-clean-v1 | `baseline apply --execute` | PASS | bridge/netns/IP/custom qdisc 없음, SK switch_mode false, relevant MM disabled |
| gPTP | `20260714-175221-gptp` | PASS | TMDS eth2 `UNCALIBRATED -> SLAVE`, delay `439~440 ns` |
| DSCP/PCP | `20260714-180551-dscp-pcp` | PASS | TMDS eth1 capture: VLAN 301 PCP 7, PCP 6 |
| Qbv Phase A | `20260714-181331-qbv` | PASS | SK eth0 taprio `flags 0x2`, 500 us cycle, TMDS eth1 PCP 7/6 capture |
| Qbu D1 | `20260714-181830-qbu` | PASS | TMDS eth1 TX active/verify success, fragment `+2591`, SK eth0 reassembly `+2591` |

run별 raw command response, pcap decode, before/after counter는
`projects/am64x-tsn-validation-automation/logs/<run-id>/`에 로컬 보관된다.

## 기능별 증거

### gPTP

경로는 `SK eth1(CPSW) <-> TMDS eth2(ICSSG)`다.

TMDS `ptp4l` log에서 다음이 관측됐다.

```text
MASTER to UNCALIBRATED on RS_SLAVE
UNCALIBRATED to SLAVE on MASTER_CLOCK_SELECTED
delay 440 -> 439 ns
```

이 run은 direct L2/P2P hardware timestamp 동기화만 판정한다. `phc2sys` system-clock
discipline과 switch-forwarded gPTP는 범위에 포함하지 않는다.

### DSCP/PCP

경로는 `TMDS eth2 -> SK eth1 -> SK switchdev -> SK eth0 -> TMDS eth1`이다.

final receiver capture:

```text
vlan 301, p 7 ... 10.31.0.1 > 10.31.0.2.5001
vlan 301, p 6 ... 10.31.0.1 > 10.31.0.2.5002
```

SK local tcpdump는 offloaded forwarding에서 판정 기준으로 사용하지 않았다.

### Qbv

경로는 `SK eth0(CPSW) -> TMDS eth1(CPSW)`다. 적용 schedule은 TI reference minimum
hardware EST schedule이다.

```text
flags 0x2
cycle-time 500000
0x4 / 125000 ns
0x2 / 125000 ns
0x1 / 250000 ns
```

TMDS receiver capture에서 VLAN 311 PCP 7 (`UDP/5001`)과 PCP 6 (`UDP/5002`)를 각각
확인했다. 이 결과는 Phase A hardware egress capability 판정이며, closed-gate timing
strong proof 또는 hardware taprio와 gPTP coexistence 시험은 포함하지 않는다.

### Qbu

경로는 `TMDS eth1(CPSW sender) -> SK eth0(CPSW receiver)` D1 path다.

TMDS sender의 MAC Merge 상태:

```text
TX active: on
Verification status: SUCCEEDED
MACMergeFragCountTx delta: +2591
```

SK receiver reassembly delta:

```text
MACMergeFrameAssOkCount delta: +2591
```

동일 30-second window counter delta를 사용했으므로 control-plane 수용만이 아니라
actual fragment/reassembly dataplane을 판정했다.

## runner 보정 이력

초기 실행에서 확인되어 code에 반영한 항목이다.

1. data port는 admin-up만으로 충분하지 않다. PHY carrier settle 전 taprio를 적용하면
   `Device failed to setup taprio offload`가 발생했다. Qbv sender는 link-up 후 5초를
   기다린다.
2. VLAN device는 networkd link-local address로 drift할 수 있다. Qbv runner는 VLAN up 후
   settle하고 test IP를 flush/re-add한다.
3. PCP wire 판정은 VLAN subinterface가 아니라 parent device pcap을 사용한다. VLAN device는
   outer tag를 제거하므로 `vlan` BPF filter로는 0 packet이 될 수 있다.
4. UART에 full tcpdump text를 출력하면 daemon buffer가 포화된다. pcap을 board `/tmp`에
   저장한 뒤 UDP port별 한 packet만 decode해 UART로 수집한다.
5. UART console input에는 긴 base64 line을 보내면 overrun이 생길 수 있다. target script는
   384-byte base64 chunk로 전송한다.
6. UART request success는 board shell command success를 의미하지 않는다. 모든 target script는
   `__TSN_REMOTE_STATUS` marker를 반환하고 nonzero status는 runner failure로 처리한다.
7. Qbu MAC Merge는 link-up 후 verify settle 시간이 필요하다. sender/receiver 모두 8초를
   기다리고, sender `TX active: on`과 `Verification status: SUCCEEDED`를 pass 조건에 포함한다.

## 종료 상태

각 final run의 `restored_baseline`은 `shared-clean-v1` check를 통과했다. 따라서 final
state는 test bridge/VLAN/netns/qdisc/MAC Merge가 남지 않은 defined runtime baseline이다.
