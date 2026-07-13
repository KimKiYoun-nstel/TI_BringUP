# AM64x CPSW Qbu/IET 검증 가이드

> 이 문서는 TI official-style 설정 reference다. 문서 안의 `Pair A: SK eth0 <-> TMDS eth1`
> 표기는 배선 재확인 전의 historical topology이므로 현재 보드에 그대로 적용하지 않는다.
> current clean base, physical mapping, runtime procedure는 `docs/CLEAN_BASE_CONTRACT.md`와
> `docs/REPRODUCTION.md`를 따른다.

> 목적: TI Processor SDK Linux의 공식 CPSW IET(Frame Preemption) 테스트 절차를 근거로, SK-AM64B와 TMDS64EVM에서 Qbu가 실제 MAC dataplane에서 fragment/reassembly까지 수행되는지 검증한다.

---

## 1. 이 문서의 위치

이 작업은 AM64x 보드 bring-up 흐름에서 **Ethernet TSN dataplane 기능 검증 단계**에 해당한다.

현재까지 확인된 상태는 다음과 같다.

- gPTP, VLAN/PCP/DSCP, Qbv 관련 사전 실험을 진행했다.
- Qbu baseline을 위해 이전 TSN 자동 설정을 제거했다.
- Pair A 기준으로 `ethtool --set-mm` 수용, `TX active: on`, `mqprio` offload, CPSW register 수준의 IET arm, priority 6/7 dataplane separation까지 확인했다.
- 하지만 `MACMergeFragCountTx`, `MACMergeFragCountRx`, `MACMergeFrameAssOkCount`가 증가하지 않아 실제 fragment/reassembly는 아직 증명되지 않았다.

따라서 다음 검증은 **사용자 정의 실험 조건을 줄이고, TI 공식 예제에 최대한 가까운 최소 조건으로 재현**하는 것을 목표로 한다.

---

## 2. 공식 근거

TI Processor SDK Linux 문서는 CPSW TSN 기능으로 다음을 설명한다.

- PTP / 802.1AS
- EST / 802.1Qbv
- CBS / 802.1Qav
- IET / 802.3br / 802.1Qbu

TI 문서에서 IET는 **Frame Preemption** 기능으로 설명되며, preemptible queue에서 frame이 전송 중일 때 higher priority express queue frame이 있으면 MAC Merge layer가 preemptible frame을 fragment로 나누고 express frame을 먼저 송신한 뒤, 수신 측에서 fragment를 reassembly하는 구조로 설명된다.

공식 문서 기준 IET 검증 성공 증거는 다음 counter 증가다.

- 송신 측
  - `MACMergeFragCountTx`
- 수신 측
  - `MACMergeFragCountRx`
  - `MACMergeFrameAssOkCount`
- 오류 counter
  - `MACMergeFrameAssErrorCount`
  - `MACMergeFrameSmdErrorCount`
  - 위 오류 counter가 지배적으로 증가하지 않아야 한다.

참조 문서:

- TI Processor SDK Linux AM64x - TSN with CPSW
  https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/latest/exports/docs/linux/Foundational_Components/Kernel/Kernel_Drivers/Network/CPSW-TSN.html
- TI Processor SDK Linux AM64x - CPSW IET
  https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/12_00_00_07_04/exports/docs/linux/Foundational_Components/Kernel/Kernel_Drivers/Network/CPSW-IET.html
- TI Processor SDK Linux AM64x - CPSW Ethernet
  https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/latest/exports/docs/linux/Foundational_Components/Kernel/Kernel_Drivers/Network/CPSW-Ethernet.html

주의: TI 문서의 실제 예제 로그는 SK-AM64B와 TMDS64EVM 조합 그대로가 아니라 AM625-SK, J7 계열 보드 예시가 섞여 있다. 따라서 이 문서는 **AM64x Processor SDK Linux의 CPSW IET 공식 절차를 SK-AM64B/TMDS64EVM Pair A에 맞게 축소 적용하는 검증 가이드**다.

---

## 3. 핵심 판단 기준

이 검증에서 구분해야 할 상태는 세 가지다.

| 상태 | 의미 | 판정 기준 |
|---|---|---|
| Control plane accepted | Linux driver가 MM/Qbu 설정을 수용 | `ethtool --show-mm`에서 `pMAC enabled`, `TX enabled` 확인 |
| Dataplane armed | CPSW MAC/register 수준에서 preemption 조건이 설정 | `TX active: on`, register dump에서 IET enable/preemptible mask 확인 |
| Actual Qbu execution | 실제 MAC Merge fragment/reassembly 발생 | `MACMergeFragCountTx/Rx`, `MACMergeFrameAssOkCount` 증가 |

현재까지는 앞의 두 단계는 확인되었고, 마지막 단계가 미확인 상태다.

---

## 4. 권장 시험 토폴로지

### 4.1 1차 canonical pair

```text
SK-AM64B eth0  <------ direct cable ------>  TMDS64EVM eth1
CPSW                                      CPSW
Sender 후보                              Receiver 후보
```

이 pair를 먼저 쓰는 이유:

- 양쪽 모두 CPSW 경로다.
- ICSSG의 `pMAC always enabled` 같은 구현 차이를 배제할 수 있다.
- Qbu 최소 조건을 가장 단순하게 해석할 수 있다.

### 4.2 2차 비교 pair

```text
SK-AM64B eth1  <------ direct cable ------>  TMDS64EVM eth2
CPSW                                      ICSSG
```

이 pair는 CPSW와 ICSSG 구현 차이를 비교하기 위한 보조 실험이다.

---

## 5. 공식 예제에 맞춘 최소 조건

기존 실험에서는 VLAN, netns, 8TC identity-map, `fp E E E E E E P E` 등을 사용했다. 하지만 TI 공식 예제 재현에서는 변수를 줄여야 한다.

이번 최소 조건은 다음과 같다.

| 항목 | 값 |
|---|---|
| topology | Pair A: SK eth0 ↔ TMDS eth1 |
| mode | MAC mode, direct link |
| VLAN | 사용하지 않음 |
| netns | 가능하면 사용하지 않음 |
| IP | interface에 직접 부여 |
| TX queue | 4 |
| mqprio | `num_tc 4`, `map 0 1 2 3`, `fp P P P E` |
| preemptible traffic | UDP dport 5002, priority 2, 200M, len 1472 |
| express traffic | UDP dport 5003, priority 3, 50M, len 1472 |
| MM 설정 | `pmac-enabled on`, `tx-enabled on`, `tx-min-frag-size 124` |
| verify | 1차는 `verify-enabled on`, 실패 시 force mode `verify-enabled off` |

중요한 차이:

- TI 공식 예제는 **highest priority queue를 express queue로 둔다**.
- 4 TX queue 기준으로 `Q3 = express`, `Q0~Q2 = preemptible` 구조다.
- 따라서 우선 `fp P P P E`로 재현해야 한다.

---

## 6. 사전 확인 명령

양쪽 보드에서 대상 interface를 확인한다.

### SK

```bash
ip -br link
ethtool -i eth0
ethtool -T eth0
ethtool -l eth0
ethtool --show-priv-flags eth0
ethtool --show-mm eth0
ethtool --include-statistics --show-mm eth0
```

### TMDS

```bash
ip -br link
ethtool -i eth1
ethtool -T eth1
ethtool -l eth1
ethtool --show-priv-flags eth1
ethtool --show-mm eth1
ethtool --include-statistics --show-mm eth1
```

확인할 것:

- SK eth0 driver가 `am65-cpsw-nuss`인지
- TMDS eth1도 CPSW인지
- `p0-rx-ptype-rrobin` flag를 볼 수 있는지
- `ethtool --show-mm`이 동작하는지
- MM counter가 읽히는지

---

## 7. Baseline 초기화

아래 명령은 기존 qdisc, IP, MM 상태를 최대한 단순화하기 위한 것이다.

### SK eth0

```bash
ip addr flush dev eth0
ip link set eth0 down

tc qdisc del dev eth0 root 2>/dev/null || true
tc qdisc del dev eth0 clsact 2>/dev/null || true

ethtool --set-mm eth0 pmac-enabled off tx-enabled off verify-enabled off 2>/dev/null || true
```

### TMDS eth1

```bash
ip addr flush dev eth1
ip link set eth1 down

tc qdisc del dev eth1 root 2>/dev/null || true
tc qdisc del dev eth1 clsact 2>/dev/null || true

ethtool --set-mm eth1 pmac-enabled off tx-enabled off verify-enabled off 2>/dev/null || true
```

---

## 8. Receiver 설정: TMDS eth1

먼저 receiver를 설정한다.

```bash
ip link set eth1 down

ethtool -L eth1 tx 4
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off

ethtool --set-mm eth1 \
  pmac-enabled on \
  tx-enabled on \
  verify-enabled on \
  verify-time 10 \
  tx-min-frag-size 124

ip link set eth1 up
sleep 5

ip addr add 192.168.100.30/24 dev eth1
```

상태 확인:

```bash
ethtool --show-mm eth1
ethtool --include-statistics --show-mm eth1
ethtool --show-priv-flags eth1 | grep p0-rx-ptype-rrobin
```

기대 상태:

```text
pMAC enabled: on
TX enabled: on
TX active: on
Verification status: SUCCEEDED
```

만약 `Verification status`가 성공하지 않으면 force mode로 전환한다.

```bash
ip link set eth1 down

ethtool --set-mm eth1 \
  pmac-enabled on \
  tx-enabled on \
  verify-enabled off \
  tx-min-frag-size 124

ip link set eth1 up
sleep 5
ip addr add 192.168.100.30/24 dev eth1 2>/dev/null || true

ethtool --show-mm eth1
```

---

## 9. Sender 설정: SK eth0

```bash
ip link set eth0 down

ethtool -L eth0 tx 4
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off

ethtool --set-mm eth0 \
  pmac-enabled on \
  tx-enabled on \
  verify-enabled on \
  verify-time 10 \
  tx-min-frag-size 124

ip link set eth0 up
sleep 5

ip addr add 192.168.100.20/24 dev eth0
```

verify가 실패하면 receiver와 동일하게 force mode로 전환한다.

```bash
ip link set eth0 down

ethtool --set-mm eth0 \
  pmac-enabled on \
  tx-enabled on \
  verify-enabled off \
  tx-min-frag-size 124

ip link set eth0 up
sleep 5
ip addr add 192.168.100.20/24 dev eth0 2>/dev/null || true
```

---

## 10. Sender mqprio 설정

TI 공식 예제에 맞춰 4TC, highest TC express 구조로 설정한다.

```bash
tc qdisc replace dev eth0 handle 100: parent root mqprio \
  num_tc 4 \
  map 0 1 2 3 \
  queues 1@0 1@1 1@2 1@3 \
  hw 1 \
  mode dcb \
  fp P P P E
```

확인:

```bash
tc -g class show dev eth0
tc qdisc show dev eth0
```

해석:

```text
TC0, TC1, TC2 = Preemptible
TC3           = Express
```

---

## 11. Sender traffic classification 설정

UDP destination port 기준으로 preemptible/express traffic을 분리한다.

```bash
tc qdisc add dev eth0 clsact

# UDP 5002 -> priority 2 -> TC2 -> preemptible
tc filter add dev eth0 egress protocol ip prio 1 u32 \
  match ip dport 5002 0xffff \
  action skbedit priority 2

# UDP 5003 -> priority 3 -> TC3 -> express
tc filter add dev eth0 egress protocol ip prio 1 u32 \
  match ip dport 5003 0xffff \
  action skbedit priority 3
```

filter hit 확인:

```bash
tc -s filter show dev eth0 egress
```

---

## 12. Connectivity 확인

### TMDS receiver

```bash
ping -c 3 192.168.100.20
```

### SK sender

```bash
ping -c 3 192.168.100.30
```

---

## 13. Traffic 실행

### TMDS receiver

```bash
iperf3 -s -i30 -p5002 &
iperf3 -s -i30 -p5003 &
```

### SK sender

```bash
iperf3 -c 192.168.100.30 -u -b200M -l1472 -t30 -i30 -p5002 &
iperf3 -c 192.168.100.30 -u -b50M  -l1472 -t30 -i30 -p5003 &
wait
```

의도:

- UDP 5002: 큰 preemptible traffic을 지속적으로 발생
- UDP 5003: express traffic을 동시에 발생
- preemptible frame 전송 중 express frame이 들어와야 fragment가 발생할 수 있다.

---

## 14. 결과 확인

### Sender: SK eth0

```bash
ethtool --include-statistics --show-mm eth0
ethtool -S eth0 | grep -E 'iet|MACMerge|tx_pri|Tx|frag|hold'
tc -s filter show dev eth0 egress
```

성공 기대값:

```text
MACMergeFragCountTx > 0
MACMergeHoldCount   may be 0 or >0
```

추가로 TI driver statistic 이름에 따라 다음 값이 보일 수 있다.

```text
iet_tx_frag > 0
iet_tx_hold may be 0 or >0
```

### Receiver: TMDS eth1

```bash
ethtool --include-statistics --show-mm eth1
ethtool -S eth1 | grep -E 'iet|MACMerge|rx|assembly|smd|frag'
```

성공 기대값:

```text
MACMergeFragCountRx      > 0
MACMergeFrameAssOkCount  > 0
MACMergeFrameAssErrorCount not increasing dominantly
MACMergeFrameSmdErrorCount not increasing dominantly
```

추가로 driver statistic 이름에 따라 다음 값이 보일 수 있다.

```text
iet_rx_assembly_ok > 0
assembly_err       not increasing dominantly
smd_err            not increasing dominantly
```

---

## 15. Pass / Fail 판정

### PASS

아래 조건을 모두 만족하면 Qbu actual execution을 확인했다고 판단한다.

```text
Sender:
  MACMergeFragCountTx 증가

Receiver:
  MACMergeFragCountRx 증가
  MACMergeFrameAssOkCount 증가

Error:
  MACMergeFrameAssErrorCount, MACMergeFrameSmdErrorCount가 지배적으로 증가하지 않음
```

### PARTIAL PASS

아래 상태는 control plane과 dataplane arm까지 성공한 상태지만 actual Qbu execution 증거는 아니다.

```text
pMAC enabled: on
TX enabled: on
TX active: on
mqprio hw 1 accepted
filter hit 증가
priority tx counter 증가
CPSW IET register enable 확인
fragment/reassembly counter는 0
```

### FAIL / NOT OBSERVED

아래 상태면 Qbu actual execution은 관찰되지 않은 것으로 기록한다.

```text
MACMergeFragCountTx = 0
MACMergeFragCountRx = 0
MACMergeFrameAssOkCount = 0
```

이 경우 설정 수용과 실제 MAC dataplane 실행은 분리해서 기록해야 한다.

---

## 16. 결과 기록 템플릿

```md
# Pair A Qbu Official-Style Reproduction Result

## Date

## Boards
- SK-AM64B:
- TMDS64EVM:

## SDK / Kernel
- SK uname:
- TMDS uname:
- ethtool version:
- iproute2 version:

## Topology
SK eth0 <-> TMDS eth1

## Mode
- MAC mode
- VLAN: none
- netns: none
- TX queues: 4
- mqprio: fp P P P E
- verify mode: on / off

## Pre-run state
### SK eth0
```text
paste ethtool --show-mm eth0
```

### TMDS eth1
```text
paste ethtool --show-mm eth1
```

## Traffic
- preemptible: UDP 5002, priority 2, 200M, len 1472
- express: UDP 5003, priority 3, 50M, len 1472

## Sender result
```text
paste ethtool --include-statistics --show-mm eth0
paste ethtool -S eth0 grep result
```

## Receiver result
```text
paste ethtool --include-statistics --show-mm eth1
paste ethtool -S eth1 grep result
```

## Decision
- Control plane accepted: yes/no
- Dataplane armed: yes/no
- Actual Qbu execution observed: yes/no

## Notes
```

---

## 17. 결과가 계속 0일 때 확인할 것

공식 예제 조건으로도 fragment/reassembly counter가 0이면 아래 순서로 좁힌다.

### 17.1 verify mode 변경

- `verify-enabled on`에서 실패하면 `verify-enabled off` force mode로 재시험한다.
- force mode에서 `TX active: on`이 되는지 확인한다.

### 17.2 방향 swap

```text
TMDS eth1 sender -> SK eth0 receiver
```

동일한 4TC / `fp P P P E` 조건으로 반대 방향을 수행한다.

### 17.3 Pair B 비교

```text
SK eth1 CPSW -> TMDS eth2 ICSSG
```

동일 traffic 조건에서 ICSSG 쪽 `iet_*` 또는 `MACMerge*` counter가 증가하는지 확인한다.

### 17.4 설정 순서 재확인

TI 문서 기준 IET/FPE 설정은 port open 시점과 관련이 있다. 따라서 아래 순서를 엄격히 지킨다.

```text
interface down
ethtool -L tx 4
p0-rx-ptype-rrobin off
ethtool --set-mm ...
interface up
mqprio 설정
filter 설정
traffic 실행
```

### 17.5 8TC/custom fp bitmap 사용 금지

공식 재현이 목적이면 아래와 같은 custom bitmap은 사용하지 않는다.

```text
fp E E E E E E P E
```

공식 최소 조건은 먼저 아래로 고정한다.

```text
fp P P P E
```

---

## 18. TI E2E 문의용 요약

공식 예제 조건에서도 counter가 0이면 아래 요약으로 문의한다.

```text
We are testing AM64x CPSW3G IET/FPE on SK-AM64B and TMDS64EVM.

Topology:
  SK-AM64B eth0 CPSW <-> TMDS64EVM eth1 CPSW

Official-style setup:
  ethtool -L ethX tx 4
  p0-rx-ptype-rrobin off
  ethtool --set-mm pmac-enabled on tx-enabled on verify-enabled on/off tx-min-frag-size 124
  mqprio num_tc 4 map 0 1 2 3 queues 1@0 1@1 1@2 1@3 hw 1 mode dcb fp P P P E
  UDP 5002 -> skb priority 2, 200M, len 1472
  UDP 5003 -> skb priority 3, 50M, len 1472

Observed:
  ethtool --show-mm reports pMAC enabled on, TX enabled on, TX active on.
  mqprio offload is accepted.
  tc filter hit counters increase.
  CPSW priority counters show traffic separation.
  CPSW IET registers indicate enable/preemptible mask committed.

But:
  MACMergeFragCountTx remains 0.
  MACMergeFragCountRx remains 0.
  MACMergeFrameAssOkCount remains 0.

Questions:
  Is actual IET/FPE dataplane supported and validated on AM64x CPSW3G in this SDK/kernel version?
  Are there additional requirements beyond ethtool --set-mm and mqprio fp P/P/P/E?
  Is IET supported on AM64x CPSW3G MAC mode with external PHY links?
  Are there known limitations where TX active becomes on but fragment counters remain zero?
```

---

## 19. 최종 정리

이 가이드의 핵심은 다음이다.

```text
1. Qbu/IET 검증은 단순히 ethtool 설정 수용 여부를 보는 것이 아니다.
2. 실제 성공 기준은 MAC Merge fragment/reassembly counter 증가다.
3. 현재 custom 실험 조건은 변수가 많으므로 TI 공식 예제와 같은 4TX queue / fp P P P E / plain ethX 조건으로 재시험해야 한다.
4. 이 조건에서도 counter가 0이면 AM64x CPSW3G SDK/driver/dataplane limitation 가능성을 TI에 확인할 근거가 충분하다.
```
