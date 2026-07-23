# AM64x TSN 정량 검증 세션 Handoff

## 목적

이 문서는 SK-AM64B와 TMDS64EVM의 수동 TSN 정량 검증을 다음 세션에서 안전하게 재개하기 위한 현재 상태, 확정된 증거, 미완료 항목 및 주의사항을 기록한다. 이 작업은 board command runner를 추가하지 않는 수동 검증 범위다.

기준 문서:

- `projects/am64x-tsn-quant-validation/README.md`
- `projects/am64x-tsn-quant-validation/config/topology.yaml`
- `projects/am64x-tsn-quant-validation/docs/measurement-plan.md`
- `projects/am64x-tsn-quant-validation/docs/workspace-sdk-cross-check.md`

## 중단 시점의 안전 상태

- SK와 TMDS의 boot `Image`, DTB, `/lib/modules`는 변경하지 않았다.
- 마지막 중단 시점에는 두 board가 dirty kernel을 실행했지만, 2026-07-23 재개 조사에서 SK는 `6.18.13-gc21449208550`, TMDS는 `6.18.13-ti-00778-gc21449208550-dirty`를 실행 중이었다.
- `ptp4l`, `phc2sys`, `iperf3`, `netperf` 및 pktgen transfer receiver는 실행 중이지 않다. installed `hwstamp_ctl`에는 read-only query mode가 없으므로 HWTSTAMP filter의 현재 값은 재설정하지 않고 확정하지 않았다.
- failed TMDS-to-SK transfer의 partial artifact와 `198.18.2.1/30` (SK `eth1`), `198.18.2.2/30` (TMDS `eth2`) 임시 주소는 제거했다.
- TMDS management `eth0`의 `192.168.0.220/24`는 host SSH 접근을 위해 유지했다. 마지막 확인 시 host `192.168.0.246/24`와 link 1 Gbps/full, ping 및 SSH가 정상이었다.
- user 지시로 이 시점에서 작업을 중지했다. 재개 전에는 UART tail과 interface state를 읽기 전용으로 먼저 확인한다.

## 재개 조사 결과: 2026-07-23

| 항목 | SK-AM64B | TMDS64EVM |
|---|---|---|
| running kernel | `6.18.13-gc21449208550` | `6.18.13-ti-00778-gc21449208550-dirty` |
| pktgen | `/proc/net/pktgen` 없음, `modinfo pktgen` 실패 | 동일 |
| rootfs/boot media | `/dev/mmcblk1p2`, SD boot partition `mmcblk1p1` | 동일 |
| rootfs free space | 약 19 GiB | 약 20 GiB |
| USB storage | 연결된 media 없음 | 연결된 media 없음 |
| TSN data-port IPv4 | 없음 | 없음 (`eth0` management만 `192.168.0.220/24`) |

SK는 재부팅된 상태로 UART login prompt에서 다시 확인했다. boot log의 42 MiB Image load와 현재
`/boot/Image` (41 MiB)는 일치하지만, FAT partition의 `Image`는 21 MiB이며 hash도 다르다.
따라서 SK test-kernel transition에서 FAT의 `Image`만 갱신하는 것은 현재 boot path의 근거가
없다. `fw_printenv`는 두 board에서 모두 `Cannot initialize environment`로 bootcmd를 읽지
못했다.

TMDS는 rootfs `/boot/Image`와 FAT partition의 `Image`가 같은 SHA-256
`bfd8a438f933f02fed44fd66baf7f839385a9814bc6bc3df693b44b752818361`다. 다만 U-Boot
environment를 Linux에서 읽을 수 없으므로 future deployment는 actual boot source를 U-Boot
console에서 확인하거나 두 copy를 같은 verified artifact로 함께 관리해야 한다.

## 확정된 Topology 및 Driver 제약

ARP source MAC으로 확인한 직접 cable pair는 다음과 같다.

```text
SK eth0  (28:b5:e8:cc:2a:3f) <-> TMDS eth1 (70:ff:76:20:22:99)
SK eth1  (70:ff:76:1f:f2:87) <-> TMDS eth2 (70:ff:76:20:22:9a)
```

- SK `eth1`은 CPSW/CPTS `/dev/ptp0`, TMDS `eth2`는 ICSSG `/dev/ptp2`다.
- CPSW RX HWTSTAMP는 PTP event filter만 지원한다. generic UDP의 `HWTSTAMP_FILTER_ALL`/`HWTSTAMP_FILTER_SOME`은 지원하지 않는다.
- TMDS ICSSG `eth2`는 generic RX `HWTSTAMP_FILTER_ALL` 후보이다.
- 따라서 generic UDP one-way latency claim은 CPSW RX raw-HW timestamp를 전제로 하면 안 되며, P4 경로는 별도 qualification이 필요하다.

## 완료한 P0/P1 증거

### P0 Readiness

- `shared-clean-v1` baseline, port/driver/PHC/HWTSTAMP capability, cable peer MAC proof를 확인했다.

### P1 gPTP Idle

- SK `eth1` CPTS `/dev/ptp0`가 GM, TMDS `eth2` ICSSG `/dev/ptp2`가 SLAVE였다.
- steady RMS는 `1~16 ns`, max는 `2~21 ns`, path delay는 `435~437 ns`였다.

### P1 UDP Load

| Requested UDP rate | Receiver achieved | Loss | gPTP 상태 |
|---|---:|---:|---|
| 500 Mbit/s | 421 Mbit/s | 1.7% | TMDS SLAVE 유지, steady max 27 ns |
| 800 Mbit/s | 411 Mbit/s | 2.8% | TMDS SLAVE 유지, steady max 29 ns |

이 결과는 idle 및 약 42% actual load에서 gPTP stability가 유지됨을 보인다. SK의 단일 userspace generator는 약 411~421 Mbit/s에서 포화됐으므로, 80% 또는 near-line-rate condition을 수행했다고 기록하면 안 된다.

## Pktgen Test-Kernel 준비 상태

### Workspace

- Linux workspace: `workspace/ti-linux-kernel-sdk12`
- branch: `phase2-tsn-pktgen`
- baseline source commit: `c214492085504176b9c252a7175e4e60b4b442af`
- `.config`: `CONFIG_NET_PKTGEN=y` (workspace-local ignored config)
- build: `Image`, modules, DTB build와 `modules_install` 성공
- test kernel release: `6.18.13-gc21449208550`
- Image: `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/Image`
- Image SHA-256: `fc2b8861be3e8bc50742c2ddde05e68a220d5d1f1ae162221f5a780954b4e54c`
- installed module tree: `out/am64x-tsn-quant-validation/modules/lib/modules/6.18.13-gc21449208550`
- module tree size at build: 219 MiB

TMDS running `/proc/config.gz`와 workspace `.config`의 diff는
`CONFIG_NET_PKTGEN=y` 대 `# CONFIG_NET_PKTGEN is not set` 한 항목뿐이다. pktgen은 module이
아닌 built-in Image feature이므로 module tree에 `pktgen.ko`는 없다. workspace source tracked
diff는 없고, topic branch는 baseline commit `c21449208`을 가리킨다.

현재 실행 중인 dirty kernel과 release/ABI/provenance가 다르므로, 새 Image만 또는 새 module만 current board에 부분 deploy하면 안 된다. pktgen을 채택하려면 backup/rollback을 포함한 full test-kernel transition이 필요하다. 기존 dirty Image의 source diff/provenance는 repo에 없으므로 matching pktgen module만 만드는 우회도 허용하지 않는다.

Host-side compressed modules archive는 `/tmp/opencode/`에 임시로 만들었으나 현재 존재하지 않는다. 재개 시 module tree로부터 archive를 다시 생성하고 checksum을 새로 기록한다.

workspace `k3-am642-evm.dtb`의 SHA-256은 TMDS deployed DTB와 동일한
`b3eba6883bf47bbb91e2725a98b6bf42c3b91c6bd93f1e0bc627734842f65cbc`다. 반면 workspace
`k3-am642-sk.dtb`는 current SK DTB와 hash가 다르다. TMDS-only pktgen transition은 DTB를
바꾸지 않아도 되지만, SK에는 workspace DTB를 generic pktgen deployment의 일부로 쓰면 안 된다.

## Transfer 결과와 Blocker

1. host에서 TMDS management SSH/SCP는 복구됐다.
2. host에서 TMDS `/tmp/tsn-pktgen-stage/`로 Image와 compressed module archive staging은 성공했고 checksum도 확인했다.
3. TMDS `eth2`에서 SK `eth1`으로 temporary `198.18.2.0/30` 주소를 사용해 SSH/SCP를 시험했다.
4. SCP Image copy는 SK에 `9,031,680` bytes만 기록한 채 stalled했다.
5. direct Python TCP stream도 120초 후 SK에 `2,626,672` bytes만 기록해 full artifact transfer 용도로 사용할 수 없다고 판정했다.
6. sender/receiver를 종료하고 partial file 및 temporary addresses를 제거했다.

이 문제는 direct data link의 UDP `iperf3` throughput과 별개로 관찰됐다. 원인은 아직 분리하지 않았으므로, 다음 세션에서 원인 미확정 상태로 동일 large-file transfer를 반복하지 않는다.

현재 host `192.168.0.246/24`에서 TMDS `192.168.0.220/24` management SSH와 ping은 정상이다.
SK에는 host management transfer path가 없고 USB storage도 연결돼 있지 않다. 따라서 현재
transport 정보만으로는 SK transition을 진행하지 않는다.

## TMDS pktgen 전환 시도와 복구: 2026-07-23

TMDS-only pktgen transition을 실제로 시도했으나, test kernel은 채택하지 않았다.

- 배포 전 current dirty kernel의 `/boot/Image`, FAT `Image`, EVM DTB 및 module tree를
  `/boot/tsn-pktgen-rollback-20260723/current-kernel-and-modules.tar.gz`로 backup했다.
  archive SHA-256은
  `3d16902d32e893954cb8dc515d363df0591f229e786388092f80d6538e087663`이다.
- test Image, EVM DTB, compressed matching modules archive의 host와 TMDS staging SHA-256을
  모두 대조한 뒤 deploy했다. test Image는
  `fc2b8861be3e8bc50742c2ddde05e68a220d5d1f1ae162221f5a780954b4e54c`이고 matching
  module tree는 219 MiB였다.
- UART에서 U-Boot가 test Image를 실행했고, kernel은
  `pktgen: Packet Generator for packet performance testing. Version: 2.75`까지 출력했다.
  그러나 `Waiting for root device PARTUUID=076c4a2a-02...` 이후 rootfs mount/login에
  도달하지 못했다. 이는 기존 TMDS hardware 또는 original dirty kernel의 boot failure가
  아니라 test-kernel transition failure다.
- FAT `Image`만 original versioned Image로 복원해도 test kernel이 다시 boot했다. 이 경로는
  rootfs `/boot/Image`도 effective kernel source로 사용하므로, 두 copy를 함께 원복해야 했다.
  U-Boot `ext4write`는 rootfs feature `0x2000`을 지원하지 않아 직접 복원할 수 없었다.
- U-Boot에서 original
  `/boot/Image-6.18.13-ti-00778-gc21449208550-dirty`와 EVM DTB를 RAM에 올려 1회
  `booti`로 수동 boot한 뒤, Linux SSH로 `/boot/Image` symlink를 original versioned Image로
  되돌리고 `6.18.13-gc21449208550` test module tree를 제거했다.
- 마지막 U-Boot default reboot 후 TMDS는
  `6.18.13-ti-00778-gc21449208550-dirty`로 정상 boot했고 management ping/SSH가 복구됐다.
  `/boot/Image`와 FAT `Image`는 모두 original SHA-256
  `bfd8a438f933f02fed44fd66baf7f839385a9814bc6bc3df693b44b752818361`이며,
  `/proc/net/pktgen`은 없다.

따라서 current test Image가 rootfs device를 발견하지 못하는 원인을 별도로 분리하기 전에는
동일 artifact를 다시 deploy하지 않는다. 이 제한은 **pktgen test-kernel 경로**에만 해당한다.
현재 kernel Image를 유지한 P1 high-rate trafgen 경로는 아래의 별도 결과를 따른다.

## Current Kernel 병렬 Generator 후보 결과: 2026-07-23

kernel Image를 바꾸지 않는 대안으로 TMDS two-core 병렬 `iperf3` UDP를 시험했으나, 이
topology에서 high-rate P1 generator로 채택할 수 없었다.

- path: TMDS `eth2` sender -> SK `eth1` receiver
- temporary IPv4: `198.18.2.2/30` -> `198.18.2.1/30`, 시험 종료 후 제거
- traffic: 1472-byte UDP 4 flow, 각 225 Mbit/s request, 30 s, UDP port `5201`~`5204`
- sender CPU placement: TMDS CPU `0, 1, 0, 1` (`taskset`)
- aggregate sender actual rate: `793.13 Mbit/s`
- aggregate receiver achieved rate: `10.74 Mbit/s`
- receiver loss: `1,892,724 / 1,920,132` datagram (`98.57%`)

TMDS sender만 보면 2-core 병렬 userspace traffic이 약 793 Mbit/s까지 request를 처리할 수
있었지만, SK receiver가 이 packet-rate를 수신하지 못했다. 따라서 이 방식은 80% 또는
near-line-rate의 error-free P1 load profile이 아니다. 시험 process, remote JSON output,
temporary IPv4는 모두 제거했으며 board kernel Image는 변경하지 않았다.

현재 installed userspace 도구는 `iperf3`, `netperf`, `taskset`, `chrt`뿐이고 `trafgen`,
`tcpreplay`, `mausezahn`, `nping`은 없다. 다음 high-rate 후보는 별도 userspace packet
generator를 재현 가능하게 도입하거나, external traffic generator/receiver를 사용하는
방법이다. 어느 경우에도 sender achieved rate뿐 아니라 SK receiver achieved rate와 loss를
P1 pass 조건으로 함께 확인해야 한다.

## trafgen Userspace Generator 도입 및 P1 결과: 2026-07-23

`trafgen`은 kernel Image를 바꾸지 않는 AF_PACKET TX_RING 기반 userspace generator다.
일반 socket send loop와 달리 mmap ring과 batching을 사용하지만, pktgen처럼 kernel built-in
thread가 아니라 user process로 동작한다. 따라서 pktgen과의 성능 우열은 AM64x actual
sender/receiver counter로 판정한다.

- upstream source: `https://github.com/netsniff-ng/netsniff-ng.git`
- evaluated commit: `1af7ae33e3e8178ab5c649c3a52838d4375c4228`
- build: read-only SDK `linux-devkit` cross compiler/sysroot를 사용해 temporary source tree에서
  `PKG_CONFIG=pkg-config ./configure --disable-libnl && make trafgen`을 수행했다.
  external SDK source, toolchain, sysroot에는 쓰기 작업을 하지 않았다.
- TMDS temporary binary: `/tmp/trafgen`
- local project archive: `artifacts/trafgen/trafgen-0.6.9-arm64-git-1af7ae3`
  (Git 제외 local artifact, TMDS binary와 동일 SHA-256)
- binary SHA-256: `4756132114e64a85cd55c6df7fd5d2cea07cbf8c9bbbb5003d2551192e4863b3`
- binary는 glibc만 dynamic dependency로 가지며 TMDS에서 `trafgen 0.6.9+` 실행을 확인했다.

### Generator qualification

TMDS `eth2`에서 SK `eth1` MAC (`70:ff:76:1f:f2:87`)으로 1514-byte unknown EtherType
raw frame을 송신했다. SK application receiver를 두지 않고 SK netdev RX packet/byte counter와
trafgen TX output을 대응했다.

- 1-packet smoke test: TMDS TX 1 frame과 SK RX counter +1을 확인했다.
- 10 s 2-CPU unlimited test: TMDS TX `811,249` frame / `1,228,230,986` byte, SK RX delta가
  정확히 일치했다.
- P1 traffic의 frame counter/byte counter도 sender/receiver에서 일치했다. 따라서 SK
  userspace UDP receiver가 병목이었던 4-flow iperf3 trial과 달리 driver-level raw-frame
  receiver accounting은 high-rate load를 보존한다.

raw unknown EtherType traffic은 P1 gPTP background-load stress에만 사용한다. PCP/qdisc/Qbv/Qbu
classification 또는 latency packet pairing용 traffic으로 해석하지 않는다. 이후 P2/P3/P4에서
trafgen을 사용하려면 packet format, queue mapping 및 `--qdisc-path` 여부를 case별로 별도
qualification해야 한다.

### P1 high-rate gPTP 결과

모든 run은 SK `eth1` CPTS가 GM, TMDS `eth2` ICSSG가 SLAVE인 L2/P2P hardware-timestamp
`ptp4l` 설정에서 수행했고, 종료 후 양쪽 `ptp4l` 및 HWTSTAMP TX/RX를 off로 복귀했다.

| Case | Traffic | Receiver accounting | gPTP 판정 |
|---|---|---|---|
| near-line 2 CPU | unlimited TX, 2 CPU | `7,378,955,910` byte / 약 `984.0 Mbit/s`, SK RX delta 일치 | 실패. `SLAVE -> FAULTY` 반복, peer-delay TX timestamp failure 발생 |
| near-line 1 CPU | unlimited TX, CPU1 only | `7,377,956,670` byte / 약 `984.0 Mbit/s`, SK RX delta 일치 | 실패. 약 50 s 후 `SLAVE -> FAULTY`, peer-delay TX timestamp failure 발생 |
| 80% rate mode | `-b 800Mbit`, CPU1 only, 60 s | `6,000,072,840` byte / 약 `800.1 Mbit/s`, SK RX delta 일치 | 통과. TMDS `SLAVE` 유지, steady RMS `1~19 ns`, max `1~23 ns`; path delay는 일시 `454 ns` 후 `437~440 ns` 회복 |

P1은 아직 전체 PASS/FAIL 하나로 판정하는 시험이 아니다. 이 프로젝트의 P1 정의는 idle, 50%,
80%, near-line-rate background, CPU load, link flap, `ptp4l` restart를 순서대로 수행하고 각 run의
offset mean/stddev/p99/p99.9/max, path delay, servo frequency, sync loss 및 recovery time을
수집하는 것이다. CPU/load-flap/restart case와 반복 run은 아직 수행하지 않았다.

현재 80% subcase의 operational PASS 조건은 다음 네 가지였다.

1. direct SK `eth1`-TMDS `eth2` path에서 gPTP가 수렴 후 TMDS `SLAVE`를 유지한다.
2. 60 s 동안 `SLAVE -> FAULTY`, sync loss, peer-delay TX timestamp timeout이 없다.
3. requested `800 Mbit/s`와 sender achieved rate를 기록하고, SK netdev RX counter delta가
   sender frame/byte accounting과 일치해 receiver drop/application bottleneck이 없음을 보인다.
4. RMS, max, path delay를 raw `ptp4l` log에서 기록한다.

따라서 **P1의 80% gPTP background-load subcase는 PASS**다. 반면 near-line-rate subcase는
명시적으로 FAIL이며, P1 전체 matrix는 아직 incomplete다. P1에는 아직 board-specific numeric
offset/percentile budget 또는 rate tolerance가 문서로 확정되지 않았으므로, 이번 PASS는 위
operational condition을 만족했다는 범위로만 사용한다.

이번 결과로 P1에 다음 두 사실이 확정됐다.

1. current kernel Image를 유지한 userspace trafgen으로 80% actual load를 재현할 수 있다.
2. 약 984 Mbit/s near-line-rate raw background load에서는 ICSSG gPTP peer-delay TX timestamp
   failure와 `SLAVE -> FAULTY`가 반복된다.

TMDS `/tmp/trafgen` binary는 후속 manual P1 run을 위해 남겼다. PTP config/log와 traffic
process, temporary IPv4는 제거했다.

## 재개 판단과 다음 순서

현재 user는 작업 중지를 지시했으며, pktgen test-kernel deployment scope 선택은 보류 상태다.
P1 80% repeat은 current Image와 `/tmp/trafgen`으로 재실행할 수 있다. pktgen 자체를 재검토할
경우에만 먼저 다음 둘 중 하나를 명시적으로 선택한다.

1. 두 board를 full test-kernel transition한다. SK로 artifact를 전달할 USB/SD, TFTP/HTTP 또는 검증된 다른 transport가 필요하다.
2. P1 high-rate만 위해 TMDS `eth2`를 pktgen sender로 test-kernel transition하고, SK `eth1`은 current clean kernel receiver로 유지한다. 이 선택은 2026-07-23 live deployment에서 test kernel rootfs boot failure로 중단됐다. 원인 분리와 non-live boot qualification 전에는 재시도하지 않는다.

어느 경우에도 다음 순서를 따른다.

1. `uart_tail`로 SK/TMDS shell prompt와 예상 밖 boot/runtime output을 확인한다.
2. `ip -br addr`, `ps`, HWTSTAMP state를 read-only 확인해 temporary state가 남지 않았는지 확인한다.
3. 선택한 board의 current `/boot` Image/DTB와 `/lib/modules/$(uname -r)`를 checksum 포함 backup한다.
4. workspace Image와 matching module tree/archive의 checksum을 재생성해 기록한다.
5. Image, DTB, matching modules를 함께 deploy하고 `depmod` 후 reboot한다.
6. UART boot log와 `uname -r`, `/proc/net/pktgen`, `modinfo`를 확인한다.
7. rollback path를 확인한 뒤에만 TMDS `eth2 ->` SK `eth1` P1 high-rate gPTP case를 실행한다.
8. request rate뿐 아니라 receiver achieved rate, loss, gPTP RMS/max/path delay를 함께 기록한다.

## 금지 및 주의사항

- external SDK 원본, live SD/OSPI 및 workspace 밖 source는 수정하지 않는다.
- current dirty kernel에 `pktgen.ko` 또는 modules만 deploy하지 않는다.
- UART로 Image/module archive를 전송하지 않는다.
- prior P1 results를 80%/near-line-rate 증거로 해석하지 않는다.
- P2/P3/P4로 넘어가기 전에 P1 high-rate generator capability와 timestamp qualification을 분리해 완료한다. high-rate generator capability의 80% subcase는 trafgen으로 완료했지만, timestamp qualification과 P1 전체 matrix는 별도 미완료다.

## 관련 기록

- `docs/workspace-sdk-cross-check.md`: source 교차 분석, P0/P1 원자료 요약 및 단계별 계획
- `docs/measurement-plan.md`: qualification gate, data contract, 중단 기준
- `projects/am64x-tsn-validation-automation/docs/runtime-baselines.md`: `shared-clean-v1`
- `projects/tsn_qbu/docs/PROVENANCE.md`: historical dirty Image source provenance 부재 근거
