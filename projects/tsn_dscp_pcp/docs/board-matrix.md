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

## 최신 검증된 Test B 역할

아래는 `PCP preservation`을 실제로 확인한 최신 시험 역할이다.

| Board | Port | Latest Validated Role | Notes |
|---|---|---|---|
| TMDS64EVM | eth2 | ICSSG sender | `ep2`, `eth2.301`, `dport 5001 -> p7`, `dport 5002 -> p6` |
| SK-AM64B | eth1 | CPSW ingress | `br-tsn` slave, `switch_mode=true`, `vlan_filtering=1` |
| SK-AM64B | eth0 | CPSW egress | `br-tsn` slave, `switch_mode=true`, `vlan_filtering=1` |
| TMDS64EVM | eth1 | final receiver | `ep1`, `eth1.301`, final wire에서 `p7/p6` 확인 |

## 재시험 시 기억할 점

- baseline control 환경은 여전히 `TMDS eth0` + `Host -> TMDS -> SK` 구조다.
- Test B 검증 상태는 baseline bridge control 상태와 별개의 **runtime switchdev/QoS test state**다.
- TMDS 쪽 VLAN device를 다시 만들면 `eth2.301 egress-qos-map`을 반드시 다시 넣어야 한다.
- SK local `tcpdump -i eth0`, `tcpdump -i eth1`는 switchdev hardware offload 상태에서 `0 packets captured`가 나올 수 있다.
