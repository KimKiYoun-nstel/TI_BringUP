# Qbu Clean Runtime Baseline

## 목적

이 기록은 historical Qbu test state를 제거한 뒤 canonical CPSW pair의 live runtime state를
고정한다. 이 상태는 actual-Qbu test 전 idle starting point다.

## Reset Applied

- SK `eth0`/`eth1`, TMDS `eth1`/`eth2` test IP 제거
- root/clsact qdisc 제거
- SK/TMDS CPSW `eth1` TX channel을 8로 복원
- SK/TMDS CPSW `eth1` MAC Merge를 `pmac-enabled off`, `tx-enabled off`,
  `verify-enabled off`, `tx-min-frag-size 60`으로 복원
- test traffic process 종료

## Observed State

| Item | SK eth1 | TMDS eth1 |
|---|---|---|
| link | up, 1 Gbps/full | up, 1 Gbps/full |
| IPv4 | none | none |
| TX channel | 8 | 8 |
| root qdisc | `mq` + 8 `pfifo_fast` | `mq` + 8 `pfifo_fast` |
| pMAC | off | off |
| TX enabled/active | off/off | off/off |
| verify | disabled | disabled |
| `p0-rx-ptype-rrobin` | off | off |

TMDS `eth2` is the comparative ICSSG port and remains down with no IP. Its driver reports
`pMAC enabled: on`, `TX enabled: off`; this is not part of the canonical CPSW baseline.

## Provenance Caveat

이 runtime baseline은 current dirty Image에서 수집됐다. clean source rebuild baseline이
아니며, kernel/DTB source reproducibility 상태는 `docs/PROVENANCE.md`를 따른다.
