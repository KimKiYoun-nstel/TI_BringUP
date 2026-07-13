# 2026-07-09 Direction-First D1/D2 Result

## 목적

sender direction 중심 전략으로 actual Qbu dataplane을 다시 확인했다.

이번 시험의 1차 질문은 다음 하나다.

```text
Verification status가 SUCCEEDED인 sender port에서
MACMergeFragCountTx가 실제로 증가하는가?
```

## 시험 방향

| Test ID | Sender | Receiver | Sender verify baseline |
|---|---|---|---|
| D1 | TMDS `eth1` | SK `eth0` | SUCCEEDED |
| D2 | SK `eth1` | TMDS `eth2` | SUCCEEDED |

공통 적용 조건:

- plain `ethX`, no VLAN, no netns
- `ethtool -L <ifname> tx 4`
- sender `mqprio num_tc 4 ... mode dcb ... fp P P P E`
- sender egress filter
  - UDP `5002` -> `skb priority 2` -> preemptible
  - UDP `5003` -> `skb priority 3` -> express
- traffic
  - UDP `5002`: `200M`, `len 1472`, `30s`
  - UDP `5003`: `50M`, `len 1472`, `30s`

## D1: TMDS `eth1` -> SK `eth0`

### traffic 전 MM 상태

- sender TMDS `eth1`
  - `Verification status: SUCCEEDED`
  - `TX active: on`
- receiver SK `eth0`
  - `Verification status: FAILED`
  - `TX active: off`

### sender 결과

TMDS `eth1`:

- `MACMergeFragCountTx = 3329`
- `iet_tx_frag = 3329`
- `MACMergeHoldCount = 0`
- `iet_tx_hold = 0`
- `tx_pri2 = 510037`
- `tx_pri3 = 127417`

즉 sender fragmentation이 실제로 발생했다.

### receiver 결과

SK `eth0`:

- `MACMergeFragCountRx = 3329`
- `MACMergeFrameAssOkCount = 3328`
- `iet_rx_assembly_ok = 3328`
- `iet_rx_frag = 3328`
- `MACMergeFrameAssErrorCount = 1`
- `MACMergeFrameSmdErrorCount = 27`

즉 receiver reassembly도 실제로 관측되었다.

### D1 해석

가장 중요한 점:

```text
receiver local verify status가 FAILED여도
sender fragmentation / receiver reassembly는 실제로 발생할 수 있다.
```

따라서 다음 등식은 성립하지 않는다.

```text
receiver verify FAILED => actual Qbu dataplane 불가
```

## D2: SK `eth1` -> TMDS `eth2`

### traffic 전 MM 상태

- sender SK `eth1`
  - `Verification status: SUCCEEDED`
  - `TX active: on`
- receiver TMDS `eth2`
  - `Verification status: FAILED`
  - `TX active: off`

### sender 결과

SK `eth1`:

- `MACMergeFragCountTx = 0`
- `iet_tx_frag = 0`
- `MACMergeHoldCount = 0`
- `iet_tx_hold = 0`
- `tx_pri2 = 509539`
- `tx_pri3 = 127512`

즉 sender traffic classification과 queue separation은 반영되었지만,
sender fragmentation은 발생하지 않았다.

### receiver 결과

TMDS `eth2`:

- `MACMergeFragCountRx = 0`
- `MACMergeFrameAssOkCount = 0`
- receiver iperf traffic 자체는 정상 수신

즉 actual reassembly도 관측되지 않았다.

### D2 해석

가장 중요한 점:

```text
sender local verify status가 SUCCEEDED여도
actual sender fragmentation은 자동으로 보장되지 않는다.
```

따라서 다음 등식도 성립하지 않는다.

```text
sender verify SUCCEEDED => MACMergeFragCountTx 증가
```

## 최종 정리

이번 direction-first 재시험으로 다음이 확정되었다.

1. D1(`TMDS eth1` -> `SK eth0`)에서는 actual Qbu dataplane이 동작했다.
2. D1에서는 receiver SK `eth0`의 local verify가 `FAILED`였지만,
   sender fragmentation과 receiver reassembly는 모두 관측되었다.
3. D2(`SK eth1` -> `TMDS eth2`)에서는 sender SK `eth1`의 local verify가 `SUCCEEDED`였지만,
   sender fragmentation은 `0`이었다.

즉 현재 AM64x Qbu/IET 문제는 단순히 `verify가 되느냐/안 되느냐`만으로 설명할 수 없다.
지금 더 정확한 표현은 다음과 같다.

```text
MAC Verify는 link-local handshake 상태를 보여준다.
하지만 actual Qbu dataplane trigger는 direction / MAC type / peer 조합에 따라 별도로 달라진다.
```

## 현재 의미

이번 결과로 Pair A official-style sender 방향 결과를 다시 해석할 수 있다.

- 기존 Pair A official-style (`SK eth0` sender)에서 fragment가 0이었던 것은
  AM64x 전체에서 Qbu dataplane이 죽어 있다는 증거가 아니다.
- 동일한 물리 pair를 반대 방향(`TMDS eth1` sender)으로 바꾸면
  actual fragment/reassembly가 나온다.

따라서 현재 핵심 문제는 다음처럼 좁혀진다.

```text
왜 TMDS CPSW sender -> SK CPSW receiver 방향(D1)에서는 Qbu dataplane이 동작하는데,
SK CPSW sender -> TMDS CPSW 또는 ICSSG receiver 방향에서는 동일한 traffic/mqprio 구조에서도
fragmentation이 나타나지 않는가?
```
