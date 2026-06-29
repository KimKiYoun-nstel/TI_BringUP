# Phase A Replay Guide

## 목적

Phase A endpoint egress Qbv closeout 결과를 현재 포트 조합으로 다시 재시험할 수 있도록,
현재 유지할 helper/script와 최소 실행 절차를 정리한다.

이 문서는 `docs/phaseA-endpoint-egress-qbv.md`의 재시험용 companion guide다.

주의:

- 아래 helper는 repo에 관리되는 canonical command template다.
- target board 안에 이 repo path가 그대로 존재한다고 가정하지 않는다.
- 따라서 아래 예시의 `<helper-path>`는 target 쪽 helper 위치 또는 pasted command block에 맞게 해석한다.

## 기준 스크립트

- `board/prepare_endpoint_target.sh`
- `board/apply_taprio.sh`
- `board/write_gptp_cfg.sh`

이 세 스크립트만 유지 기준으로 본다.

기존 `setup_phaseA_*` 스크립트는 초기 Phase A 진행 흔적이며, 새로운 canonical replay 기준은 아니다.

## 공통 원칙

- SK 제어는 항상 UART 기준
- TMDS 제어는 항상 `ssh root@192.168.0.220`
- 각 run 전 `ethX.Y`의 `169.254.x.x` drift 여부를 반드시 다시 확인
- hardware `taprio` pass 기준:
  - `tc -s qdisc show dev <iface>`에 `flags 0x2`
- software `taprio` pass 기준:
  - `tc -s qdisc show dev <iface>`에 `clockid TAI`
- egress Qbv pass 기준:
  - sender iperf 또는 filter counter 증가
  - receiver iperf success
  - receiver wire capture에서 intended PCP (`p7`, `p6`) 확인
- gPTP coexistence success 기준:
  - concurrent traffic 중 `SLAVE` 수렴 또는 유지
  - `FAULTY`, `timed out while polling for tx timestamp`, `send peer delay request failed` 없음

## Scenario 1. SK eth0 -> TMDS eth1

### SK UART command template

```bash
ROLE=sender VLAN_ID=311 LOCAL_CIDR=10.33.0.1/24 \
SET_TX_QUEUES=3 DISABLE_RROBIN=yes SET_VLAN_EGRESS_MAP=yes ADD_FILTERS=yes \
bash <helper-path>/prepare_endpoint_target.sh eth0
```

HW:

```bash
TAPRIO_MODE=hw SCHED_ENTRIES='05 250000;03 250000' \
bash <helper-path>/apply_taprio.sh eth0
```

SW:

```bash
TAPRIO_MODE=sw SCHED_ENTRIES='05 250000;03 250000' \
bash <helper-path>/apply_taprio.sh eth0
```

gPTP cfg:

```bash
bash <helper-path>/write_gptp_cfg.sh /tmp/gptp-pair2.cfg
ptp4l -i eth0 -f /tmp/gptp-pair2.cfg -m
```

### TMDS SSH command template

```bash
ROLE=receiver VLAN_ID=311 LOCAL_CIDR=10.33.0.2/24 \
STOP_IPERF=yes \
bash <helper-path>/prepare_endpoint_target.sh eth1
```

gPTP cfg:

```bash
bash <helper-path>/write_gptp_cfg.sh /tmp/gptp-pair2.cfg
ptp4l -i eth1 -f /tmp/gptp-pair2.cfg -m
```

## Scenario 2. SK eth1 -> TMDS eth2

### SK UART command template

```bash
ROLE=sender VLAN_ID=301 LOCAL_CIDR=10.31.0.1/24 \
SET_TX_QUEUES=3 DISABLE_RROBIN=yes SET_VLAN_EGRESS_MAP=yes ADD_FILTERS=yes \
bash <helper-path>/prepare_endpoint_target.sh eth1
```

HW:

```bash
TAPRIO_MODE=hw SCHED_ENTRIES='05 250000;03 250000' \
bash <helper-path>/apply_taprio.sh eth1
```

SW:

```bash
MAP_SPEC='0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0' \
TAPRIO_MODE=sw SCHED_ENTRIES='05 250000;03 250000' \
bash <helper-path>/apply_taprio.sh eth1
```

### TMDS SSH command template

```bash
ROLE=receiver VLAN_ID=301 LOCAL_CIDR=10.31.0.2/24 \
STOP_IPERF=yes \
bash <helper-path>/prepare_endpoint_target.sh eth2
```

### 예상 판정

- HW egress: success
- SW+gPTP coexistence: success
- HW+gPTP coexistence: unstable / partial

## Scenario 3. TMDS eth2 -> SK eth1

### SK UART command template

```bash
ROLE=receiver VLAN_ID=301 LOCAL_CIDR=10.31.0.1/24 \
STOP_IPERF=yes \
bash <helper-path>/prepare_endpoint_target.sh eth1
```

### TMDS SSH command template

```bash
ROLE=sender VLAN_ID=301 LOCAL_CIDR=10.31.0.2/24 \
SET_TX_QUEUES=3 SET_VLAN_EGRESS_MAP=yes ADD_FILTERS=yes \
bash <helper-path>/prepare_endpoint_target.sh eth2
```

HW:

```bash
TAPRIO_MODE=hw SCHED_ENTRIES='05 500000;03 500000' \
bash <helper-path>/apply_taprio.sh eth2
```

SW:

```bash
TAPRIO_MODE=sw SCHED_ENTRIES='05 500000;03 500000' \
bash <helper-path>/apply_taprio.sh eth2
```

### 예상 판정

- HW egress: success
- SW+gPTP coexistence: success
- HW+gPTP coexistence: fail (`tx timestamp timeout`)

## Traffic Commands

sender 쪽에서 공통으로 사용:

```bash
iperf3 -c <peer-ip> -u -b 20M -t 8 -p 5001
iperf3 -c <peer-ip> -u -b 20M -t 8 -p 5002
```

## Capture / Evidence

- receiver wire capture:

```bash
tcpdump -i <iface> -e -tttt -vvv -n 'vlan and udp'
```

- gPTP evidence:
  - `MASTER -> UNCALIBRATED -> SLAVE`
  - 또는 `FAULTY`, `timed out while polling for tx timestamp`, `send peer delay request failed`

이 가이드의 결과 판단은 반드시 `docs/phaseA-endpoint-egress-qbv.md`의 matrix와 비교한다.
