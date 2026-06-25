# AM64x TSN DSCP PCP Lab Board Matrix

## 목표 토폴로지

| Board | Port | Intended Role | Expected Controller | Expected PHC |
|---|---|---|---|---|
| TMDS64EVM | eth0 | control | CPSW | `/dev/ptp0` |
| TMDS64EVM | eth1 | endpoint A | CPSW | `/dev/ptp0` |
| TMDS64EVM | eth2 | endpoint B | ICSSG | `/dev/ptp2` |
| SK-AM64B | eth0 | switch candidate A | CPSW | `/dev/ptp0` |
| SK-AM64B | eth1 | switch candidate B | CPSW | `/dev/ptp0` |

## 현재 상태

| Board | Port | Current State | Driver | PHC | Notes |
|---|---|---|---|---|---|
| TMDS64EVM | eth0 | `192.168.0.220/24`, link up | `am65-cpsw-nuss` | `/dev/ptp0` | office/control 유지 |
| TMDS64EVM | eth1 | `10.50.0.1/24`, link up | `am65-cpsw-nuss` | `/dev/ptp0` | SK bridge control/test port |
| TMDS64EVM | eth2 | no IP, link up | `icssg-prueth` | `/dev/ptp2` | endpoint B / capture 후보 |
| SK-AM64B | eth0 | `master br-tsn`, link up | `am65-cpsw-nuss` | `/dev/ptp0` | TMDS eth1 peer |
| SK-AM64B | eth1 | `master br-tsn`, link up | `am65-cpsw-nuss` | `/dev/ptp0` | TMDS eth2 peer |
| SK-AM64B | br-tsn | `10.50.0.2/24`, up | Linux bridge | n/a | switch candidate bridge |

## 현재 토폴로지

- Host/control: `TMDS eth0` 경유
- SK 접근: `Host -> TMDS eth0 -> TMDS eth1 -> SK br-tsn` 경유
- direct links:
  - `TMDS eth1 <-> SK eth0`
  - `TMDS eth2 <-> SK eth1`
