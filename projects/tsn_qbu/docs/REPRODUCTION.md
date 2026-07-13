# Qbu Reproduction Procedure

## 범위

이 절차는 clean baseline에서 이미 검증된 actual Qbu certificate를 다시 확인하기 위한
절차다. canonical path는 다음과 같다.

```text
TMDS eth1 sender (CPSW) -> SK eth1 receiver (CPSW), 1 Gbps
```

이 path는 TMDS sender fragment와 SK receiver reassembly가 두 번 확인됐다.
SK sender 1 Gbps는 별도 미판정 항목이며 이 certificate의 pass target이 아니다.

## 사전 조건

1. 물리 배선이 `TMDS eth1 <-> SK eth1`인지 link down/up 시험으로 확인한다.
2. kernel/DTB hash가 [PROVENANCE.md](PROVENANCE.md)와 일치하는지 확인한다.
3. rootfs baseline script를 적용하고 reboot한다.
4. `eth1` 이외의 같은 CPSW instance port를 down해 TX channel 변경이 가능하게 한다.
5. 두 보드의 data port가 1 Gbps/full duplex인지 확인한다.

## Clean Baseline 적용

각 overlay를 rootfs에 배치한 후 target에서 root로 실행한다.

```bash
sh /usr/local/sbin/qbu-clean-baseline-sk.sh
sh /usr/local/sbin/qbu-clean-baseline-tmds.sh
reboot
```

TMDS control port `eth0`은 이 절차에서 변경하지 않는다. SK는 UART로 제어한다.

## Receiver: SK eth1

```bash
ip addr flush dev eth1
ip link set eth0 down
ip link set eth1 down
ethtool -L eth1 tx 4
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
ethtool --set-mm eth1 pmac-enabled on tx-enabled on verify-enabled on verify-time 10 tx-min-frag-size 124
ip link set eth1 up
sleep 5
ip addr add 192.168.107.20/24 dev eth1
iperf3 -s -i30 -p5002 &
iperf3 -s -i30 -p5003 &
```

historical certificate에서 SK receiver local verify는 `FAILED`, `TX active`는 off였지만
reassembly가 발생했다. 그러므로 receiver local verify/TX active는 pass criterion이 아니다.

## Sender: TMDS eth1

```bash
ip addr flush dev eth1
ip link set eth0 down
ip link set eth1 down
ethtool -L eth1 tx 4
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
ethtool --set-mm eth1 pmac-enabled on tx-enabled on verify-enabled on verify-time 10 tx-min-frag-size 124
ip link set eth1 up
sleep 5
ip addr add 192.168.107.30/24 dev eth1

tc qdisc replace dev eth1 handle 100: root mqprio \
  num_tc 4 map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 \
  queues 1@0 1@1 1@2 1@3 hw 1 mode dcb fp P P P E
tc qdisc replace dev eth1 clsact
tc filter add dev eth1 egress protocol ip prio 1 u32 \
  match ip dport 5002 0xffff action skbedit priority 2
tc filter add dev eth1 egress protocol ip prio 2 u32 \
  match ip dport 5003 0xffff action skbedit priority 3
```

## Evidence Window

traffic 직전 양쪽에서 다음을 저장한다.

```bash
ethtool --include-statistics --show-mm eth1
ethtool -S eth1
tc -s qdisc show dev eth1
tc -s filter show dev eth1 egress
```

TMDS sender에서 두 process를 CPU pin 없이 동시에 실행한다.

```bash
iperf3 -c 192.168.107.20 -u -b200M -l1472 -t30 -i30 -p5002 &
iperf3 -c 192.168.107.20 -u -b50M -l1472 -t30 -i30 -p5003 &
wait
```

traffic 직후 동일한 evidence를 다시 저장한다.

## Pass/Fail

absolute counter가 아니라 같은 30-second window의 delta로 판정한다.

pass:

- TMDS sender `MACMergeFragCountTx` 또는 `iet_tx_frag` delta > 0
- SK receiver `MACMergeFragCountRx` 및 `MACMergeFrameAssOkCount` 또는
  `iet_rx_assembly_ok` delta > 0
- TMDS sender `Verification status: SUCCEEDED` 및 `TX active: on`
- sender TC2/TC3 filter 및 priority counter가 모두 증가
- receiver assembly/SMD error가 success counter보다 지배적으로 증가하지 않음

fail 또는 invalid:

- Image/DTB hash가 provenance와 다름
- TX channel이 4가 아님
- TMDS sender `TX active: on`이 아님
- traffic 또는 TC2/TC3 filter counter가 증가하지 않음
- sender/receiver fragment delta가 0

## Evidence Archive

각 run에 아래를 `projects/tsn_qbu/logs/YYYY-MM-DD_<path>_result.md`로 저장한다.

- kernel release, Image/DTB SHA-256, boot ID
- physical port mapping
- before/after `show-mm`, `ethtool -S`, qdisc/filter output
- `iperf3` sender/receiver output
- counter delta 표와 pass/fail 판정

기존 certificate는 [VALIDATION_STATUS.md](VALIDATION_STATUS.md)와
`history/2026-07-09_direction_first_d1_d2_result.md`,
`history/2026-07-09_rewired_pair_c_result.md`에 보관돼 있다.
