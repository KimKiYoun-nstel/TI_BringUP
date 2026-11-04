# P3 Qbu/IET Combined Condition Endurance Plan

## 목적

Timing variance A/B에서 유일하게 300 s x 3 loss-free였던 sender combined condition을 independent
boot session에서 endurance로 확인한다. 이 검증은 rate envelope을 다시 측정하거나 production profile을
즉시 채택하는 작업이 아니다.

## Independent Boot Preflight

| Board | Boot ID | CPU online | 비고 |
|---|---|---|---|
| SK | `02b6264d-7032-4c1b-9cb7-6df5528f5600` | `0` | UART boot log에서 CPU1 online 실패 재확인 |
| TMDS | `5269e612-0108-4e10-975b-7e5dbecd37d1` | `0-1` | management `eth0` DHCP address `192.168.0.56` |

두 board는 `eth1` 1 Gbps/full, test IP 없음, MAC Merge off, default `mq/pfifo_fast`, legacy
DSCP/PCP service inactive 상태에서 시작한다. TMDS `eth1`는 reboot 후 admin down이므로 preflight에서
명시적으로 up해 1 Gbps/full을 확인했다.

## Fixed Traffic Condition

| 항목 | 값 |
|---|---|
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| Preemptible | UDP 5002, 50 Mbit/s, 1472 B, TMDS CPU0 |
| Express | UDP 5003, 50 Mbit/s, 1472 B, TMDS CPU1 |
| Generator pacing | iperf3 `--pacing-timer 100` us |
| On endurance | 300 s x 10, 3000 aggregate seconds |
| Off control | 동일 offered rate, 30 s x 1 |


각 on run은 아래를 모두 만족해야 한다. 하나라도 만족하지 못하면 `campaign-record.json`과 raw artifact를
보존하고 campaign을 즉시 중단한다.

- Qbu classification `active`
- preemptible와 express lost packet 0
- receiver assembly/SMD error 0
- measurement validity, link/peer/MM/filter/hardware class-hit gates 통과


target `snapshot-before/after`는 기존 MM/counter/qdisc/filter/load evidence와 함께 다음을 보존한다.

- CPU online topology
- CPSW `tx2`, `tx3`, `rx0` IRQ counter
- `NET_RX`, `NET_TX` softirq counter
- sender client affinity와 generator configuration

이는 combined condition 결과가 IRQ/softirq placement 변화와 동반되는지 후속 분석하기 위한 evidence이며,
이번 campaign에서 IRQ affinity를 변경하지 않는다.


TMDS management address는 DHCP로 reboot마다 달라질 수 있다. 이번 session은
`P3_TMDS_SSH_HOST=192.168.0.56`을 사용하며 runner manifest에 실제 host를 기록한다. board control과
stage는 UART-only이고, SSH는 cleanup 후 raw artifact collection에만 사용한다. TMDS `eth0` recovery
race는 host-side 총 90-second retry bound 안에서 처리한다.
