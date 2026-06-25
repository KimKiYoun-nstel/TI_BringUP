# AM64x gPTP Lab Board Matrix

## 구성

| Board ID | Display Name | SSH IP | Control IF | Direct gPTP IF | L2 연결 IF | Current Role |
|---|---|---|---|---|---|---|
| `sk-am64b` | TI SK-AM64B | `192.168.0.110` | `eth0` | `eth1` | `eth0` | direct gPTP GM candidate |
| `tmds64evm` | TI TMDS64EVM | `192.168.0.220` | `eth0` | `eth2` | `eth0`, `eth1` | direct gPTP slave candidate |

## 연결 관계

```text
Host
  |- SSH -> SK-AM64B eth0 (192.168.0.110)
  `- SSH -> TMDS64EVM eth0 (192.168.0.220)

SK-AM64B eth1 <------------------> TMDS64EVM eth2
           direct L2 gPTP / P2P / hardware timestamp

Local L2 switch
  |- TMDS64EVM eth0 (control path 포함)
  `- TMDS64EVM eth1
```

## 실험 메모

- control port는 `SK eth0`, `TMDS eth0`로 유지한다.
- direct gPTP는 `SK eth1 <-> TMDS eth2`를 canonical 경로로 사용한다.
- local L2 switch 경유에서는 `0x88f7` frame 송수신과 BMCA는 확인했지만 stable `SLAVE`는 형성되지 않았다.
- TMDS64EVM은 실험 시작 전에 `ip link set eth2 up` 여부를 확인한다.
