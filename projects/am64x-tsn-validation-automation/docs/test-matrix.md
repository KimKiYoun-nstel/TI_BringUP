# TSN 자동 검증 매트릭스

## 공통 preflight

모든 test는 아래를 통과해야 한다.

1. UART daemon `sk`, `tmds`가 shell prompt에 응답한다.
2. `SK eth0`, `SK eth1`, `TMDS eth1`, `TMDS eth2`가 1 Gbps/full carrier다.
3. ARP probe로 다음 매핑이 관측된다.
   - SK `eth0` source MAC -> TMDS `eth1`
   - SK `eth1` source MAC -> TMDS `eth2`
4. 필요한 driver와 userspace binary가 존재한다.

carrier만으로 상대 포트를 판단하지 않는다. probe evidence가 없는 run은 invalid다.

## 기능별 기준

| 기능 | path | pass evidence | 제외 범위 |
|---|---|---|---|
| gPTP | SK eth1 -> TMDS eth2 | TMDS `UNCALIBRATED -> SLAVE`, stable delay/RMS 출력 | `phc2sys` wall-clock discipline, switch forwarding |
| DSCP/PCP | TMDS eth2 -> SK eth1 -> SK eth0 -> TMDS eth1 | receiver capture에 VLAN 301 PCP 7 및 6 | SK local tcpdump visibility |
| Qbv Phase A | SK eth0 -> TMDS eth1 | `taprio flags 0x2`, VLAN 311 PCP 7 및 6 capture | timing strong proof, switch-mode Qbv |
| Qbu D1 | TMDS eth1 -> SK eth0 | sender fragment delta > 0, receiver reassembly delta > 0 | SK 1 Gbps sender, ICSSG comparative path |

## Evidence archive

각 run 디렉터리는 최소한 다음을 포함한다.

- `preflight-*`: port state, ARP pair proof
- `command-*.json`: UART command response 원문
- `*-capture.txt`, `*-ptp.log`, `*-stats-before.txt`, `*-stats-after.txt`
- `result.json`: feature, pass/fail, parsed evidence, timestamp

UART daemon 전체 log의 기준은 계속 `logs/runtime_log`다. run archive는 해당
검증에서 추출한 command-level evidence다.
