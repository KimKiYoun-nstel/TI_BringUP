# 2026-07-09 Rewired Pair C Result

## 목적

사용자가 physical direct wiring을 다음처럼 변경한 뒤,
실제 링크 매핑을 재확인하고 `TMDS eth1 -> SK eth1` 방향 actual Qbu dataplane을 다시 확인했다.

새 배선 가정:

```text
TMDS eth1 <-> SK eth1
TMDS eth2 <-> SK eth0
```

## 1. 실제 링크 매핑 확인

링크 up 상태에서 SK 쪽 포트를 하나씩 down 하여 TMDS 쪽 반응을 확인했다.

확인 결과:

1. `SK eth0 down` 시 `TMDS eth2`만 link down
2. `SK eth1 down` 시 `TMDS eth1`만 link down

따라서 실제 배선은 다음과 같이 확인되었다.

```text
SK eth0 <-> TMDS eth2
SK eth1 <-> TMDS eth1
```

## 2. Pair C baseline

Pair C:

```text
TMDS eth1 <-> SK eth1
```

clean verify-on 기준으로 baseline을 맞췄다.

- 양쪽 `tx 4`
- `p0-rx-ptype-rrobin off`
- `verify-enabled on`
- `tx-min-frag-size 124`

baseline 결과:

- SK `eth1`
  - `Verification status: FAILED`
  - `TX active: off`
- TMDS `eth1`
  - `Verification status: SUCCEEDED`
  - `TX active: on`

즉 이전 D1 패턴과 동일하게,
`TMDS eth1`를 sender로 actual dataplane을 볼 수 있는 조건이 형성되었다.

## 3. Actual Qbu 시험

direction:

```text
sender   = TMDS eth1
receiver = SK eth1
```

조건:

- plain interface, no VLAN, no netns
- sender mqprio `num_tc 4 ... mode dcb ... fp P P P E`
- sender filter
  - UDP `5002` -> `skb priority 2`
  - UDP `5003` -> `skb priority 3`
- traffic
  - UDP `5002`: `200M`, `1472`, `30s`
  - UDP `5003`: `50M`, `1472`, `30s`

주의:

- TMDS `eth1` sender의 `MACMergeFragCountTx`는 이전 시험 누적값 `3329`에서 시작했다.
- 따라서 이번 판정은 absolute value가 아니라 delta 기준으로 봐야 한다.

## 4. 결과

### 4.1 sender TMDS `eth1`

traffic 전:

- `MACMergeFragCountTx = 3329`

traffic 후:

- `MACMergeFragCountTx = 13039`
- `iet_tx_frag = 13039`

delta:

- `MACMergeFragCountTx += 9710`
- `iet_tx_frag += 9710`

또한 sender traffic 분류는 정상 반영되었다.

- `tx_pri2 = 1020017`
- `tx_pri3 = 254812`

즉 sender fragmentation이 다시 실제로 발생했다.

### 4.2 receiver SK `eth1`

- `Verification status: FAILED`
- `MACMergeFragCountRx = 9710`
- `MACMergeFrameAssOkCount = 9710`
- `iet_rx_assembly_ok = 9710`
- `iet_rx_frag = 9710`
- `MACMergeFrameAssErrorCount = 0`
- `MACMergeFrameSmdErrorCount = 90`

즉 receiver reassembly도 실제로 관측되었다.

## 5. 해석

이번 재시험으로 다음이 확인되었다.

1. 새 배선에서도 `TMDS eth1 -> SK eth1` 방향 actual Qbu dataplane이 동작한다.
2. receiver SK `eth1`의 local verify status가 `FAILED`여도,
   actual fragment/reassembly는 발생할 수 있다.
3. 이전 `TMDS eth1 -> SK eth0` 성공은 우연이 아니라,
   `TMDS eth1` sender 방향에서 실제 dataplane이 반복 재현된 것이다.

즉 현재까지의 strongest fact는 다음과 같다.

```text
TMDS eth1를 sender로 한 CPSW -> SK CPSW 방향에서는
actual Qbu fragmentation / reassembly가 재현된다.
```

반대로 여전히 남는 핵심 질문은 다음이다.

```text
왜 SK CPSW sender 방향에서는 verify SUCCEEDED가 나와도
actual fragmentation이 0으로 남는가?
```
