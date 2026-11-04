# P3 Qbu/IET Reboot Readiness

## 범위

두 target board reboot 후 다음 P3 원인분리 측정을 시작하기 전에 UART에서 확인한
runtime readiness record다. 이 확인에서는 Qbu traffic, test IP, MAC Merge enable, mqprio를
적용하지 않았다.

## Boot Identity

| Board | Kernel | Boot ID |
|---|---|---|
| SK | `6.18.13-gc21449208550` | `1bb6c464-71e7-4ba6-a587-31e0969235a0` |
| TMDS | `6.18.13-ti-00778-gc21449208550-dirty` | `827f1bab-71a9-44e6-9306-bb85595058ac` |

UART boot log에서 Linux remoteproc/driver initialization과 root login prompt를 확인했다.
`logs/runtime_log`의 이전 `br-tsn` forwarding 기록은 reboot 전 누적 runtime evidence이며,
reboot 후 live `ip -d link show type bridge`에서 P3 data port를 포함한 `br-tsn`은 없고
`docker0`만 존재했다.

## P3 Clean-Idle 확인

양 board canonical `eth1`에서 다음을 확인했다.

| 항목 | SK | TMDS |
|---|---|---|
| Test IPv4 address | 없음 | 없음 |
| MAC Merge pMAC/TX/TX active | off/off/off | off/off/off |
| Root qdisc | `mq` + `pfifo_fast` | `mq` + `pfifo_fast` |
| Link | 1 Gbps/full | 1 Gbps/full |

reboot 직후 TMDS `eth1`는 admin down이었으나, test IP/QoS 변경 없이 `ip link set dev eth1 up` 후
5초 안에 1 Gbps/full link가 복구됐다. P3 endpoint setup은 target `eth1`을 명시적으로 up하므로
measurement run에서 같은 동작을 보장한다.

reboot reset의 정상 값은 TX channel 8과 `p0-rx-ptype-rrobin: on`이다. 이는 P3 persistent
baseline failure가 아니며 endpoint setup이 measurement 동안 `tx 4`와 `rrobin off`를 명시 적용한다.

## Persistent Policy

- SK `ti-tsn-dscp-pcp-sk.service`: not-found/inactive
- TMDS `ti-tsn-dscp-pcp-tmds.service`: disabled/inactive
- legacy bridge network files: `.qbu-disabled`
- SK `09-eth0-l2only.network`, `11-eth1-l2only.network` 존재
- TMDS `11-eth1-l2only.network`, `12-eth2-l2only.network` 존재

따라서 legacy TSN network policy가 P3 runtime configuration을 자동으로 덮어쓸 상태는 아니다.

## Harness 준비

현재 `tools/p3_qbu_endpoint_run.sh`를 UART 512-byte chunk stage로 SK와 TMDS `/tmp/p3-qbu-tools/`에
배치했고 target-side SHA-256 verification을 통과했다. board control과 stage는 UART-only다.
raw artifact는 traffic 종료 및 runtime cleanup 뒤에만 bounded SSH bulk transfer로 회수한다.

## 판정

두 board는 다음 P3 CPU affinity/generator burst 원인분리 run을 시작할 수 있는 상태다.
다음 run 전 추가 reboot, legacy service 변경, persistent rootfs 변경은 필요하지 않다.
