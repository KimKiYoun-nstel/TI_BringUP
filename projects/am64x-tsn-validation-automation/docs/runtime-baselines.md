# TSN Runtime Baseline Contract

## 목적

이 문서는 물리 배선 계약과 분리된 board runtime 시작점과 종료점을 정의한다.
자동화는 임의의 기존 TSN 상태를 snapshot/restore하지 않는다. 대신 아래의
`shared-clean-v1` baseline을 검증한 뒤 기능 시험을 시작하고, 종료 후 동일 baseline으로
복귀한다.

따라서 기존 `br-tsn`, VLAN, qdisc, netns, 실행 중인 `ptp4l`을 유지해야 하는 세션에서는
이 자동화를 실행하면 안 된다.

## Shared Clean v1

### SK-AM64B

- `eth0`, `eth1`: link up, IPv4 주소 없음
- `br-tsn`: 없음
- `switch_mode=false`
- `eth0`, `eth1`: root qdisc가 기본 `mq` 계열, `clsact`/`mqprio`/`taprio`/`cbs` 없음
- `eth0`, `eth1`: MAC Merge pMAC/TX/verify disabled
- CPSW TX queue: `8`
- TSN test process: `ptp4l`, `phc2sys`, `iperf3` 없음

### TMDS64EVM

- `eth1`, `eth2`: link up, IPv4 주소 없음
- `ep1`, `ep2` network namespace: 없음
- `eth1`, `eth2`: root qdisc가 기본 `mq` 계열, `clsact`/`mqprio`/`taprio`/`cbs` 없음
- `eth1`: MAC Merge pMAC/TX/verify disabled, CPSW TX queue `8`
- TSN test process: `ptp4l`, `phc2sys`, `iperf3`, `tcpdump` 없음
- `ti-tsn-dscp-pcp-tmds.service`는 disable 또는 not-found여야 한다.

TMDS `eth2` ICSSG의 idle pMAC 표시값은 driver별 baseline 차이가 있어 shared-clean 판정
대상에서 제외한다. Qbu canonical path는 TMDS `eth1`만 사용한다.

## 기능별 시작점

모든 기능은 `shared-clean-v1`에서 시작한다. 표의 설정은 baseline이 아니라 해당 test
runner가 적용하고 종료 시 제거하는 transient state다.

| 기능 | data path | test가 추가하는 transient state |
|---|---|---|
| gPTP | SK eth1 <-> TMDS eth2 | L2/P2P `ptp4l`, `/tmp` config/log |
| DSCP/PCP | TMDS eth2 -> SK eth1 -> SK eth0 -> TMDS eth1 | SK `switch_mode=true`, `br-tsn`, VLAN 301, TMDS `ep1`/`ep2`, `mqprio`, filters |
| Qbv Phase A | SK eth0 -> TMDS eth1 | VLAN 311, hardware `taprio`, `clsact`, PCP filters, `iperf3`/capture |
| Qbu D1 | TMDS eth1 -> SK eth0 | TX queue 4, MAC Merge, `mqprio` with frame-preemption classes, IP 192.168.107.0/24 |

## 명령

```bash
# board 상태를 바꾸지 않고 baseline 확인
python3 board/tsn_validate.py baseline check

# 명시적으로 shared-clean-v1으로 전환
python3 board/tsn_validate.py baseline apply --execute

# baseline check가 통과할 때만 기능 test 실행
python3 board/tsn_validate.py run qbu --execute
```

`run --execute`는 baseline이 아닌 상태에서 자동 정리하지 않고 실패한다. test가 시작된
이후에는 성공/실패와 무관하게 `shared-clean-v1` cleanup을 수행한다.

## Persistent RootFS 전제

이 contract는 runtime state만 관리한다. Qbu test 전에 DSCP/PCP auto-apply rootfs profile이
남아 있으면 `projects/tsn_qbu`의 clean baseline overlay를 먼저 배포하고 reboot해야 한다.
자동화 runner는 persistent network file과 systemd enable state를 변경하지 않는다.
