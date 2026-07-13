# Qbu Validation Evidence Ledger

## 판정 규칙

Qbu actual execution은 traffic 전후의 hardware counter delta로 판정한다.

| 위치 | 필수 증거 |
|---|---|
| sender | `MACMergeFragCountTx` 또는 `iet_tx_frag` delta > 0 |
| receiver | `MACMergeFragCountRx` 및 `MACMergeFrameAssOkCount` 또는 `iet_rx_assembly_ok` delta > 0 |

`ethtool --set-mm` 성공, `TX active`, verify state, `mqprio`, filter hit는 필수 설정 확인
증거지만 standalone pass evidence가 아니다.

## Certificate A: TMDS CPSW Sender -> SK CPSW Receiver

### D1

```text
sender:   TMDS eth1
receiver: SK eth0
link:     1 Gbps direct CPSW <-> CPSW
traffic:  TC2/UDP5002 200M, 1472 bytes, 30 s
          TC3/UDP5003 50M, 1472 bytes, 30 s
```

| Counter | Delta |
|---|---:|
| TMDS `MACMergeFragCountTx` | +3329 |
| TMDS `iet_tx_frag` | +3329 |
| SK `MACMergeFragCountRx` | +3329 |
| SK `MACMergeFrameAssOkCount` | +3328 |
| SK `iet_rx_assembly_ok` | +3328 |

결과: PASS. SK receiver local verify는 `FAILED`였지만 actual fragment/reassembly가 발생했다.

### Rewired Pair C

```text
sender:   TMDS eth1
receiver: SK eth1
link:     1 Gbps direct CPSW <-> CPSW
traffic:  D1과 동일
```

| Counter | Delta |
|---|---:|
| TMDS `MACMergeFragCountTx` | +9710 |
| TMDS `iet_tx_frag` | +9710 |
| SK `MACMergeFragCountRx` | +9710 |
| SK `MACMergeFrameAssOkCount` | +9710 |
| SK `iet_rx_assembly_ok` | +9710 |

결과: PASS. D1 success는 단일 receiver port 우연이 아니라 TMDS eth1 sender에서 재현됐다.

## Certificate B: SK CPSW Sender -> TMDS CPSW Receiver

```text
sender:   SK eth1
receiver: TMDS eth1
link:     100 Mbps/full duplex, autoneg off
traffic:  TC2/UDP5002 80M, 1472 bytes, 30 s
          TC3/UDP5003 10M, 1472 bytes, 30 s
mode:     force mode, verify-enabled off
```

| Counter | Delta |
|---|---:|
| SK `MACMergeFragCountTx` | +25130 |
| SK `iet_tx_frag` | +25130 |
| TMDS `MACMergeFragCountRx` | +25130 |
| TMDS `MACMergeFrameAssOkCount` | +25123 |
| TMDS `iet_rx_assembly_ok` | +25123 |

결과: PASS. SK sender의 CPSW MAC Merge/IET TX path는 actual Qbu를 수행한다.

## Negative/Diagnostic Evidence

이 결과들은 Qbu failure certificate가 아니라 traffic overlap 조건을 해석하기 위한 진단이다.

| Sender condition | TC2 actual rate | TC3 actual rate | `iet_tx_frag` delta |
|---|---:|---:|---:|
| SK eth1, single-CPU netperf | 약 202 Mbps | 약 16 Mbps | 0 |
| TMDS eth1, two-core netperf | 약 418 Mbps | 약 33 Mbps | +509379 |
| TMDS eth1, both netperf processes pinned to CPU 0 | 약 243 Mbps | 약 23 Mbps | 0 |

TMDS single-CPU pin result은 SK 1 Gbps counter 0을 hardware/spec failure로 해석할 수 없음을
보여준다. current userspace generator가 만든 packet timing/burst가 actual preemption trigger를
만들었는지를 먼저 입증해야 한다.

## 증적 한계

이 ledger는 UART에서 확인한 curated counter delta를 보존한다. raw before/after command output
bundle은 historical run에서 별도 파일로 수집되지 않았다. 다음 certificate run부터는
`REPRODUCTION.md`의 Evidence Archive 규칙대로 raw output을 함께 저장해야 한다.

## Source Records

- `docs/history/2026-07-09_direction_first_d1_d2_result.md`
- `docs/history/2026-07-09_rewired_pair_c_result.md`
- `docs/history/sk_cpsw_tx_fragmentation_root_cause.md`
