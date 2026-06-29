# Phase 0 Baseline

## 목적

`tsn_dscp_pcp`에서 성공한 PCP preservation baseline을 `tsn_qbv` 프로젝트 기준으로 재현하고 고정한다.

## 준비 자산

- `../board/setup_sk_switchdev_base.sh`
- `../board/setup_tmds_netns_endpoints.sh`
- `../board/cleanup.sh`

## 성공 조건

```text
TMDS eth2 sender: vlan 301, p7/p6
TMDS eth1 receiver: vlan 301, p7/p6
```

## 실행 시 기록할 것

- `bridge -d vlan show`
- `bridge link`
- `devlink dev param show platform/8000000.ethernet`
- `ethtool --show-priv-flags eth0`
- `ethtool --show-priv-flags eth1`
- `tc -s qdisc show dev eth0`
- `tc -s qdisc show dev eth1`
- TMDS sender / receiver capture 로그

## 현재 상태

- 완료

## 이번 재현 결과

### SK baseline 확인

- `switch_mode=true`
- `br-tsn=10.50.0.2/24`
- `eth0`, `eth1` 모두 `br-tsn` slave + `forwarding`
- `bridge vlan`에서 `301` tagged membership 유지
- `p0-rx-ptype-rrobin=off`
- `mqprio ... hw 1 mode channel` on `eth0`, `eth1`

### TMDS endpoint 확인

- `ep1 eth1.301 = 10.31.0.2/24`
- `ep2 eth2.301 = 10.31.0.1/24`
- `eth2.301` egress filter hit 증가:
  - `priority 7`: `1313 pkt`
  - `priority 6`: `1311 pkt`

### Wire capture 증거

sender `ep2/eth2`, UDP `5001`:

```text
vlan 301, p 7
10.31.0.1.47718 > 10.31.0.2.5001
```

receiver `ep1/eth1`, UDP `5001`:

```text
vlan 301, p 7
10.31.0.1.47718 > 10.31.0.2.5001
```

sender `ep2/eth2`, UDP `5002`:

```text
vlan 301, p 6
10.31.0.1.44254 > 10.31.0.2.5002
```

receiver `ep1/eth1`, UDP `5002`:

```text
vlan 301, p 6
10.31.0.1.44254 > 10.31.0.2.5002
```

### iperf3 요약

- UDP `5001`, `5 Mbits/sec`, `3 sec`: receiver loss `0/1296 (0%)`
- UDP `5002`, `5 Mbits/sec`, `2 sec`: receiver loss `0/864 (0%)`

## 판정

Phase 0 baseline은 `tsn_qbv` 프로젝트 기준으로 다시 재현되었다.

즉 현재 시점에서 `TMDS eth2(ICSSG) -> SK CPSW switchdev -> TMDS eth1` 경로의 PCP preservation이 다시 확인되었고,
이제 Phase 1 `mqprio` 기반 queue/class 연결 검증으로 진행할 수 있다.
