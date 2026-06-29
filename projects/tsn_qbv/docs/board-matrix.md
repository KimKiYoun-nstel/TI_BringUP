# Qbv Board Matrix

## 보드 역할

| 보드 | 포트 | 역할 | 비고 |
|---|---|---|---|
| TMDS64EVM | `eth0` | control | `192.168.0.220/24` 유지 |
| TMDS64EVM | `eth1` | CPSW data/test port | direct pair에서 receiver/sender 모두 가능 |
| TMDS64EVM | `eth2` | ICSSG data/test port | direct pair에서 receiver/sender 모두 가능 |
| SK-AM64B | `eth1` | CPSW data/test port | switchdev member 또는 direct pair 포트 |
| SK-AM64B | `eth0` | CPSW data/test port | switchdev member 또는 direct pair 포트 |
| SK-AM64B | `br-tsn` | control bridge | control IP `10.50.0.2/24` |

추가 설명:

- SK-AM64B는 control Ethernet 포트가 없고, 위험 runtime 변경과 boot/runtime 관찰 기준은 항상 UART다.
- TMDS64EVM는 `eth0`가 control 포트이며, `eth1`, `eth2`는 실험 대상 data/test 포트다.

## Switchdev Topology

```text
TMDS ep2 / eth2 / ICSSG sender
  -> SK eth1 / CPSW ingress
  -> SK br-tsn / CPSW switchdev
  -> SK eth0 / CPSW egress
  -> TMDS ep1 / eth1 / receiver
```

## 공통 전제

- SK 제어는 위험 runtime 변경 시 UART 기준
- TMDS 제어는 SSH 기준
- Pair 1 기본 VLAN/IP는 `301`, `10.31.0.x/24`
- Pair 2 기본 VLAN/IP는 `311`, `10.33.0.x/24`
- `10.301.0.x/24` 표기는 사용하지 않음

## Endpoint Topology

우회 경로에서는 switchdev bridge를 쓰지 않고 direct endpoint path를 사용한다.

```text
Pair 1 / ICSSG direct:
  Path A: SK eth1 (CPSW sender) -> TMDS eth2 (ICSSG receiver)
  Path B: TMDS eth2 (ICSSG sender) -> SK eth1 (CPSW receiver)

Pair 2 / CPSW direct:
  Path C: SK eth0 (CPSW sender) -> TMDS eth1 (CPSW receiver)
  Path D: TMDS eth1 (CPSW sender) -> SK eth0 (CPSW receiver)
```

Phase A에서 사용한 VLAN / IP:

- `301`: Pair 1 baseline / coexistence (`10.31.0.1/24`, `10.31.0.2/24`)
- `311`: Pair 2 baseline / coexistence (`10.33.0.1/24`, `10.33.0.2/24`)
- `302`: 초기 A3 software taprio 단일 `p7` 검증 (`10.32.0.1/24`, `10.32.0.2/24`)
