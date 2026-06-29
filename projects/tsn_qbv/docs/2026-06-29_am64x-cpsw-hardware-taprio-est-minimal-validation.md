# AM64x CPSW Hardware Taprio EST Minimal Validation

> Evidence-only note: current canonical summary is `docs/phaseA-endpoint-egress-qbv.md`.

## 1. Purpose

- `SK-AM64B` CPSW `eth1`에서 `flags 2` 기반 hardware `taprio` offload가 실제로 적용되는지 재검증한다.
- 이전 `No fetch RAM`이 driver capability 부재가 아니라, 긴 interval/schedule 또는 prerequisite 불일치 때문인지 분리한다.
- TI 공식 CPSW EST 예제와 같은 `125 us / 125 us / 250 us` schedule로 최소 동작 여부를 확인한다.

## 2. TI Reference Found

### local repo / SDK tree

- local kernel tree에서는 user-facing CPSW EST 사용 문서를 찾지 못했다.
- 확인된 local 근거는 다음이다.
  - driver source: `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-qos.c`
  - driver header: `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-qos.h`
  - kernel config: `workspace/ti-linux-kernel-sdk12/.config`
- local source에서 직접 확인한 핵심 조건:
  - `p0-rx-ptype-rrobin`가 `on`이면 `taprio`는 `p0-rx-ptype-rrobin flag conflicts with taprio qdisc`로 거부된다.
  - `cycle_time_extension`은 지원하지 않는다.
  - fetch RAM은 2-buffer 기준 buffer당 `64` command만 사용 가능하다.
  - driver comment와 TI 문서 설명상 2-buffer 구성에서는 max cycle time이 대략 `~8 ms` 수준이다.

### TI official reference

- TI Processor SDK Linux AM64X 문서 `CPSW-EST` 페이지를 확인했다.
- 문서 핵심 예제:

```bash
ip link set dev eth0 down
ethtool -L eth0 tx 3
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ip link set dev eth0 up

tc qdisc replace dev eth0 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0000 \
  sched-entry S 4 125000 \
  sched-entry S 2 125000 \
  sched-entry S 1 250000 \
  flags 2
```

- 이번 `SK eth1` 시험 command는 interface 이름만 다르고 본질적으로 동일하다.

## 3. Test Topology

- sender: `SK eth1 (CPSW hardware taprio)`
- receiver: `TMDS eth2`
- VLAN: `301`
- IP:
  - `SK eth1.301 = 10.31.0.1/24`
  - `TMDS eth2.301 = 10.31.0.2/24`

## 4. Prerequisite State

- switch_mode: `false`
- `eth1` TX queues: `3`
- `p0-rx-ptype-rrobin`: `off`
- kernel config:
  - `CONFIG_NET_SCH_TAPRIO=m`
  - `CONFIG_TI_K3_AM65_CPSW_NUSS=y`
  - `CONFIG_TI_K3_AM65_CPSW_SWITCHDEV=y`
  - `CONFIG_TI_AM65_CPSW_QOS=y`
- taprio module: `modprobe sch_taprio` 후 apply 진행
- link:
  - initial check에서는 `Link detected: no`
  - TMDS `eth2`를 다시 올린 뒤 `SK eth1` / `TMDS eth2` 모두 `1000Mb/s Full` / `Link detected: yes`
- 주의사항:
  - `eth1.301`, `eth2.301`가 다시 `169.254.x.x` link-local로 drift하는 현상이 재발했다.
  - 첫 traffic 실패는 offload failure가 아니라 이 IP drift 때문이었다.

## 5. Hardware Taprio Apply Result

- command:

```bash
tc qdisc replace dev eth1 parent root handle 100 taprio \
  num_tc 3 \
  map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 \
  queues 1@0 1@1 1@2 \
  base-time 0 \
  sched-entry S 04 125000 \
  sched-entry S 02 125000 \
  sched-entry S 01 250000 \
  flags 2
```

- result: 성공 (`RC=0`)
- `tc -s qdisc show dev eth1`:
  - `flags 0x2`
  - `cycle-time 500000`
  - `index 0 cmd S gatemask 0x4 interval 125000`
  - `index 1 cmd S gatemask 0x2 interval 125000`
  - `index 2 cmd S gatemask 0x1 interval 250000`
- dmesg:
  - 이번 run에서는 `Device failed to setup taprio offload` 없음
  - 이번 run에서는 `No fetch RAM` 없음
  - 과거 실패 이력으로만 `net eth1: No fetch RAM`가 남아 있음

## 6. Schedule Variants

| Variant | num_tc | queues | cycle | result | dmesg |
|---|---:|---|---:|---|---|
| TI reference minimal | 3 | `1@0 1@1 1@2` | `500000 ns` | success | no new `No fetch RAM` |
| 2-entry fallback | 2 | not run | not run | not needed | not run |
| 1-entry always-open | 1 | not run | not run | not needed | not run |

## 7. Traffic Result

- SK egress filter:
  - UDP `5001` -> `skbedit priority 7`
  - UDP `5002` -> `skbedit priority 6`
- sender result:
  - `5001`: `20.0 Mbits/sec`, receiver `20.0 Mbits/sec`, loss `0/8634`
  - `5002`: `20.0 Mbits/sec`, receiver `20.0 Mbits/sec`, loss `0/8634`
- filter counters:
  - priority `7` rule: `12866130 bytes / 8649 pkt`
  - priority `6` rule: `12866128 bytes / 8649 pkt`
- taprio qdisc stats:
  - root taprio는 `flags 0x2` 유지
  - parent `100:1` queue에서 `25735166 bytes / 17320 pkt` 진행 확인
- TMDS wire capture:
  - saved log: `projects/tsn_qbv/logs/2026-06-29_est_hw_taprio_eth2.txt`
  - `p7` packets: `8635`
  - `p6` packets: `8635`
  - `p0` reply packets: `2`
  - sample lines:
    - `vlan 301, p 7` at `10.31.0.1.43202 > 10.31.0.2.5001`
    - `vlan 301, p 6` at `10.31.0.1.39382 > 10.31.0.2.5002`
- packet grouping:
  - tcpdump text에서도 `p7` 구간과 `p6` 구간이 각각 연속 burst로 나타났다.
  - 다만 이번 run은 `tcpdump` text capture만으로 정밀한 `500 us` intra-cycle gap을 판정하기보다, offload accept와 PCP preservation 확인에 우선 초점을 두었다.

## 8. Source-Based Interpretation

- `am65_est_cmd_ns_to_cnt()`는 1G link에서 interval을 fetch count로 바꾼다.
- `AM65_CPSW_FETCH_CNT_MAX`는 14-bit count max인 `16383`이다.
- `125000 ns` interval은 대략 `15625` count라 entry당 `2` command가 필요하다.
- `250000 ns` interval은 대략 `31250` count라 entry당 `2` command가 필요하다.
- 따라서 이번 3-entry schedule은 총 `6` command 수준이라 buffer당 `64` command 제한 안에 들어간다.
- 반대로 과거 `50 ms` interval은 entry당 대략 `6250000` count, 즉 entry 하나만으로도 수백 command가 필요하므로 `No fetch RAM`이 자연스럽다.
- 따라서 이전 `No fetch RAM`은 hardware EST 미지원보다, 긴 schedule이 fetch RAM budget을 넘긴 결과로 해석하는 편이 타당하다.

## 9. Decision

- Case A

```text
AM64x CPSW endpoint hardware EST/taprio offload는 가능하다.
이번 SK-AM64B eth1 run에서 TI reference와 동일한 500 us cycle schedule이 flags 2로 성공했고,
wire capture에서도 vlan 301, p 7 / p 6가 유지되었다.
이전 No fetch RAM은 긴 50 ms급 interval이 fetch RAM budget을 초과한 영향이 더 크다.
```

## 10. Next Action

1. 같은 `flags 2` 상태에서 `p7`/`p6` 동시 송신을 걸고 wire burst pattern을 더 정밀하게 계측한다.
2. 필요하면 TI 문서의 `guard band` variant를 `eth1`에 그대로 옮겨 `spill over` 감소 여부를 본다.
3. gPTP coexistence는 우선 `switch_mode=false` direct endpoint 경로에서만 다시 붙인다.
4. test 전에는 항상 `eth1.301` / `eth2.301`의 `169.254.x.x` drift 여부를 먼저 확인한다.
