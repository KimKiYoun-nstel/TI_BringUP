# Workspace TI SDK 교차 분석과 수동 검증 순서

## 목적과 기준

이 문서는 다음 두 가이드를 현재 repo의 기존 증적과 **workspace source만** 대조해,
수동 정량 검증을 어떤 순서로 진행할지 정한다.

- `.agents/AM64x_TSN_정량_검증_가이드.md`
- `.agents/AM64x_TSN_정량_검증_TI_SDK_활용_추가_가이드.md`

분석 기준 source는 다음 local workspace다.

- Linux: `workspace/ti-linux-kernel-sdk12` (`base-clean`)
- MCU+: `workspace/mcu_plus_sdk_am64x_12_00_00_27` (`phase2-tsn-c-case`)

외부 SDK 원본의 파일 존재 여부나 다른 board의 throughput/latency 수치는 이 문서의
근거로 사용하지 않는다. 모든 시험은 수동으로 수행하며, 이 프로젝트는 board command
runner를 만들지 않는다.

## 최종 분석 결론

정량 검증의 진행 순서는 확정할 수 있다. 우선순위는 다음과 같다.

1. 현재 Linux timestamp 경로의 packet type별 한계를 직접 확인한다.
2. gPTP 안정성을 traffic/load 조건별 수치로 수집한다.
3. Qbv는 RX timestamp 기반 gate conformance와 burst/gap을 먼저 정량화한다.
4. Qbu는 이미 증명된 100 Mbps actual fragmentation 조건을 수동 재현해 counter와 loss를 정량화한다.
5. Qbu one-way tail latency는 receiver MAC block과 timestamp filter 조건을 충족하는 경로를 확정한 뒤 수행한다.
6. CBS는 generic `tc cbs` hardware offload가 아니라 CPSW `tx_maxrate` HW rate limiter를 별도 정량화한다.
7. Qbv+Qbu 복합 A/B와 MCU+ reference 시험은 앞 단계의 측정 경로가 성립한 뒤 진행한다.

이 순서는 기능 범위를 축소하는 것이 아니다. 각 단계에서 다음 단계의 timestamp,
traffic contention, queue, PHC 조건을 실제 수치로 확인해 정량 결과의 원인을 분리하는
순서다.

## Workspace source와 기존 실험의 교차 판정

| 항목 | workspace source 확인 | 기존 실험 증적 | 정량 검증에서의 판정 |
|---|---|---|---|
| CPSW EST/Qbv | `TC_SETUP_QDISC_TAPRIO` 및 hardware schedule 설정 구현 | SK `eth0 ->` TMDS `eth1`에서 `taprio flags 0x2`, 500 us schedule 확인 | 즉시 수동 gate conformance 시험 대상으로 사용 |
| CPSW TX HWTSTAMP | `HWTSTAMP_TX_ON` 지원. timestamp control은 `ETH_P_1588` L2 type을 설정 | generic UDP raw-HW TX app timestamp는 직접 확보하지 못함 | PTP event와 generic UDP를 분리해 interface HWTSTAMP 설정 포함 수동 재시험 |
| CPSW RX HWTSTAMP | PTP V1/V2 event filter만 수용, `HWTSTAMP_FILTER_ALL/SOME` 거절 | generic UDP RX raw-HW 시험 미수행 | 일반 UDP RX-HW를 전제하지 않음; PTP event 측정 경로 또는 다른 receiver를 선정 |
| ICSSG RX HWTSTAMP | `HWTSTAMP_FILTER_ALL`을 수용하고 get path도 ALL 반환 | TMDS `eth2`의 packet-level 수집은 미시험 | generic packet RX-HW 수집 후보. CPSW sender와의 PHC 동기 및 physical pair를 먼저 확인 |
| gPTP | CPTS/PHC 및 Linux `ptp4l` 기반 | SK `eth1`-TMDS `eth2`에서 TMDS SLAVE, delay 439~440 ns 관찰 | load별 offset/dispersion/recovery 수집을 먼저 수행 |
| Qbu/IET | standard ethtool MAC Merge API 및 counter 구현 | TMDS sender 1 Gbps 및 SK sender 100 Mbps에서 actual fragment/reassembly 확인 | counter/loss 정량은 즉시 가능; latency A/B는 측정 경로 확정 후 수행 |
| CPSW generic CBS HW offload | `setup_tc`는 taprio/mqprio만 처리 | `tc cbs ... offload 1` 실패, software CBS 적용 성공 | `tc cbs offload 1`을 HW Qav 시험으로 재사용하지 않음 |
| CPSW HW rate limiter | `ndo_set_tx_maxrate`와 queue rate programming 구현 | 정량 시험 없음 | CBS/Qav와 구분한 rate-accuracy 수동 시험 대상으로 사용 |
| MCU+ CPSW TSN EST | `am64x-evm` 공식 문서/예제와 modulo 판정 source 확인 | 실행 기록 없음 | Linux 결과의 분석 기준 및 별도 TMDS reference 시험 |
| MCU+ ICSSG TAS/gPTP | TMDS EVM R5F source/문서 확인 | 실행 기록 없음 | Linux 검증과 혼합하지 않는 후속 reference 시험 |

### 근거 source

- CPSW HWTSTAMP filter/control: `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-nuss.c:2196-2284`
- ICSSG HWTSTAMP filter: `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/icssg/icssg_common.c:1568-1616`
- CPSW EST/mqprio와 rate limiter: `workspace/ti-linux-kernel-sdk12/drivers/net/ethernet/ti/am65-cpsw-qos.c:1244-1339`
- MCU+ EST modulo 판정: `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/est_cpsw_app/est_init.c:594-622`
- MCU+ EST 실행 및 good/bad packet 기준: `workspace/mcu_plus_sdk_am64x_12_00_00_27/docs/api_guide_am64x/EXAMPLES_ENET_CPSW_TSN_EST.html:283-350`
- Qbv existing evidence: `projects/am64x-tsn-validation-automation/docs/2026-07-14_first-automated-validation.md`
- Qbu 100 Mbps certificate: `projects/tsn_qbu/logs/2026-07-13_validation_evidence_ledger.md:56-75`
- CBS software-only evidence: `projects/tsn_qbv/docs/phase2-cbs-shaping.md`

## Timestamp 설계의 결정 사항

### CPSW receiver의 일반 UDP 제약

현재 Linux CPSW driver는 TX hardware timestamp enable은 지원하지만 RX filter로
PTP V1/V2 event만 수용한다. 일반 UDP에 해당하는 `HWTSTAMP_FILTER_ALL` 또는
`HWTSTAMP_FILTER_SOME` 요청은 source에서 `-EOPNOTSUPP`로 거절한다. TX control에도
`ETH_P_1588` L2 type 설정이 포함되므로 generic UDP TX raw-HW timestamp 역시 source
advertisement만으로 가능하다고 가정하지 않고 직접 확인한다.

따라서 CPSW receiver에서 일반 UDP express packet의 RX raw-HW timestamp를 얻는 것을
정량 계획의 전제로 두면 안 된다. 이것은 보드 hardware 불능이 아니라 **현재 Linux CPSW
driver API의 알려진 packet filter 제약**이다.

해결 경로는 시험 전에 하나를 명시적으로 선택한다.

1. Qbv gate conformance는 PTP event timestamp가 가능한 official-style measurement frame으로 수행한다.
2. 일반 UDP Qbu tail latency는 `HWTSTAMP_FILTER_ALL`을 수용하는 ICSSG receiver path에서 측정한다.
3. CPSW receiver가 반드시 필요한 application flow는 외부 hardware timestamp 계측을 추가한다.

첫 번째 경로에서 가이드가 언급한 `plget`은 현재 workspace에 source나 binary가 없다.
따라서 아직 ready tool이 아니다. 사용할 경우 source revision, build 방법, binary hash를
workspace-managed asset로 확정한 뒤에만 측정기로 채택한다. 이 확인 전에는 `plget` 결과를
계획에 넣지 않는다.

### PHC와 one-way latency

동일 보드 안의 동일 PHC가 아니면 다음 값을 그대로 latency로 사용하지 않는다.

```text
RX_HWTS - TX_HWTS
```

서로 다른 board/PHC인 path는 측정과 동시에 gPTP offset과 분산을 수집해 clock offset의
잔차가 기대하는 Qbv/Qbu 개선량보다 작은지 판단한다. 이 조건은 결과를 제한하는 것이 아니라
packet timing 변화와 clock drift를 구분하기 위한 측정 조건이다.

## 수동 단계별 시험 계획

### P0: topology와 timestamp capability 기록

목적은 실험 시작 전 physical path와 driver capability를 확정하는 것이다. 기존 기록에는
배선 변경 이력이 있으므로 과거 interface 이름만으로 receiver MAC block을 가정하지 않는다.

각 candidate path에서 수동으로 다음을 보존한다.

- cable peer MAC proof, carrier, speed, duplex, driver, firmware
- `ethtool -T`, `ethtool -l`, `ethtool -S`, `ethtool --show-mm`
- `/sys/class/net/<if>/device/ptp` PHC mapping
- current `SIOCGHWTSTAMP` result after the requested TX/RX filter configuration
- qdisc, queue count, MAC Merge state, CPU governor/affinity

판정:

- CPSW RX candidate는 requested filter가 PTP event로 normalize되는지 기록하고, TX는 PTP event와 generic UDP 각각의 raw-HW 수신 결과를 분리해 기록한다.
- ICSSG RX candidate는 `HWTSTAMP_FILTER_ALL`이 실제로 설정/조회되는지 기록한다.
- candidate의 link speed와 MAC block이 다르면 별도 case로 유지한다.

### P1: gPTP 안정성 정량화

path는 먼저 SK `eth1`-TMDS `eth2` direct gPTP link를 사용한다. 이미 lock 증적이 있어
출발점으로 적합하지만, 현재 439 ns path delay 한 번만으로 안정성이 확정된 것은 아니다.

동일 설정에서 idle, 50%, 80%, near-line-rate background, CPU load, link flap, `ptp4l`
restart를 차례로 수행한다. 각 run은 `ptp4l` raw log로 offset mean/stddev/p99/p99.9/max,
path delay, servo frequency, sync loss, recovery time을 수집한다.

이 단계의 산출물은 각 traffic condition의 PHC residual offset bound다. P2/P3 one-way
calculation은 해당 bound가 동시에 기록된 run에서만 수행한다.

### P0 실행 결과: 2026-07-15

P0.1/P0.2는 UART에서 수동으로 수행했다. 임시 ARP address는 physical pair 확인 직후
두 board에서 모두 제거했고, 다시 IPv4 address, custom qdisc, `ptp4l`/`phc2sys`/`iperf3`/
`tcpdump` process가 없는 것을 확인했다.

| Endpoint | MAC / driver / PHC | timestamp capability | queue |
|---|---|---|---|
| SK `eth0` | `28:b5:e8:cc:2a:3f`, CPSW, provider 0 | TX hardware, RX PTP event filter | TX 8 |
| SK `eth1` | `70:ff:76:1f:f2:87`, CPSW, provider 0 | TX hardware, RX PTP event filter | TX 8 |
| TMDS `eth1` | `70:ff:76:20:22:99`, CPSW, provider 0 | TX hardware, RX PTP event filter | TX 8 |
| TMDS `eth2` | `70:ff:76:20:22:9a`, ICSSG, provider 2 | TX hardware, RX `all` filter | TX 4 |

ARP source-MAC reply로 확인한 current physical mapping은 다음과 같다.

```text
SK eth0 (28:b5:e8:cc:2a:3f) <-> TMDS eth1 (70:ff:76:20:22:99)
SK eth1 (70:ff:76:1f:f2:87) <-> TMDS eth2 (70:ff:76:20:22:9a)
```

`hwstamp_ctl`는 timestamp mode를 설정하는 도구이며 read-only current-config option은 제공하지
않는다. 따라서 P1에서 `ptp4l`이 hardware timestamp configuration을 명시적으로 적용한 결과와
종료 후 cleanup state를 함께 기록한다.

### P1 idle baseline 실행 결과: 2026-07-15

P0에서 확인한 direct gPTP path에서 background traffic 없이 L2/P2P hardware timestamp
`ptp4l`을 수동 실행했다.

```text
SK eth1 (CPTS /dev/ptp0): grand master
TMDS eth2 (ICSSG /dev/ptp2): SLAVE
```

TMDS는 `MASTER -> UNCALIBRATED -> SLAVE`로 전이했다. 수렴 후 log의 최근 summary는
RMS `1~16 ns`, max `2~21 ns`, path delay `435~437 ns`였다. 초기 servo convergence의
매우 큰 RMS 값은 steady-state sample에 포함하지 않는다. 이 첫 run은 gPTP lock과 idle
offset scale의 증적이며, load별 p99/p99.9/max 통계는 P1의 후속 raw log에서 별도로
계산한다.

`ptp4l`은 종료 명령에 job-control PID가 아닌 child PID가 남을 수 있었다. 이후의 모든
P1 run은 shell job PID가 아니라 `pgrep -x ptp4l`로 actual process 종료를 확인한다.
이번 run 종료 후 SK `eth1`과 TMDS `eth2` 모두 `hwstamp_ctl -r 0 -t 0`으로 TX/RX
timestamp를 off로 복귀했고, `pgrep -x ptp4l`는 빈 결과를 반환했다.

### P1 50% 요청 load 실행 결과: 2026-07-15

SK `eth1 ->` TMDS `eth2`에 임시 IPv4를 부여하고, `iperf3` UDP 500 Mbit/s 요청,
1472 byte payload, 60 s를 gPTP와 병행했다. receiver 기준 actual throughput은
`421 Mbit/s`, loss는 `36,627 / 2,181,610` datagram (`1.7%`)이었다. 따라서 이 run은
"50% 요청 load"이며, actual link load는 약 42%로 기록한다.

TMDS `eth2`는 traffic 중에도 `SLAVE`를 유지했다. servo 수렴 후 summary의 RMS는
대체로 `2~24 ns`, max는 `2~27 ns`, path delay는 `435~438 ns`였다. sync loss나
`tx timestamp timeout`은 관찰하지 않았다.

이 run은 gPTP stability 관찰에는 유효하지만, traffic generator가 요청값보다 낮은
actual rate를 만들었으므로 후속 case는 request rate뿐 아니라 receiver achieved rate와
loss를 항상 함께 기록한다. 종료 후 `ptp4l`, `iperf3`, 임시 IPv4 address를 제거하고
SK `eth1`/TMDS `eth2` HWTSTAMP를 off로 복귀했다.

### P1 800 Mbit/s 요청 load 실행 결과: 2026-07-15

동일 path, packet size, duration에서 UDP request rate만 `800 Mbit/s`로 바꿨다. receiver
actual throughput은 오히려 `411 Mbit/s`, loss는 `61,102 / 2,154,404` datagram (`2.8%`)이었다.
즉 현재 단일 SK userspace `iperf3` sender의 achieved throughput은 약 411~421 Mbit/s에
포화되며, 800 Mbit/s 요청이 80% link-load case를 만들지 못했다.

TMDS `eth2`는 계속 `SLAVE`였고, servo 수렴 후 RMS `1~22 ns`, max `1~29 ns`, path delay
`435~438 ns`였다. sync loss와 `tx timestamp timeout`은 관찰되지 않았다.

따라서 현재까지 idle 및 약 42% actual UDP load에서의 gPTP stability는 확인됐지만,
80%와 near-line-rate condition은 아직 **미수행**이다. 다음 작업은 rate argument를 높이는
것이 아니라 packet generator capability를 정량화하고, 필요하면 kernel `pktgen` 또는
병렬 generator로 actual target rate를 만든 뒤 같은 P1 case를 재실행하는 것이다.

### P1 high-rate generator 조사 결과: 2026-07-15

현재 board와 workspace 기준으로 다음을 확인했다.

| 항목 | SK-AM64B | TMDS64EVM | 판단 |
|---|---:|---:|---|
| online CPU | 1 | 2 | SK single-process userspace sender가 약 411~421 Mbit/s에 포화된 관찰과 일치 |
| `netperf` / `taskset` | 설치됨 | 설치됨 | 병렬 userspace 시험은 가능하지만 final near-line-rate 보장은 없음 |
| `/proc/net/pktgen` | 없음 | 없음 | running image에 pktgen 없음 |
| `modinfo pktgen` | module 없음 | module 없음 | module load로 해결 불가 |
| workspace `CONFIG_NET_PKTGEN` | 비활성 | 동일 kernel config 기준 | source config/build/deploy가 필요 |

기존 Qbu evidence에서도 TMDS의 two-core `netperf` TC2/TC3 aggregate는 약 451 Mbit/s였고,
receiver SMD/assembly error가 증가했다. 따라서 이를 80%/near-line-rate의 error-free
background profile로 재사용하지 않는다.

P1의 80%와 near-line-rate case를 수행하려면 다음 중 하나를 먼저 채택해야 한다.

1. Linux workspace topic branch에서 `CONFIG_NET_PKTGEN`을 enable하고, build/deploy 후
   kernel-level generator로 actual 850~950 Mbit/s를 확인한다.
2. pktgen과 동등한 line-rate generator를 별도 도입하되, source/version, CPU affinity,
   achieved rate, receiver drop를 measurement asset로 관리한다.

이 문단의 결론은 2026-07-15 시점 기준이다. 2026-07-23에는 current Image를 유지한
trafgen qualification으로 80% actual-load case를 수행했으며, 결과와 near-line-rate failure는
`session-handoff-2026-07-23.md`의 `trafgen Userspace Generator 도입 및 P1 결과`를 따른다.

### pktgen build/deploy provenance 판정: 2026-07-15

`phase2-tsn-pktgen` workspace branch에서 `CONFIG_NET_PKTGEN=y`를 적용해 `Image`, modules,
DTB build는 성공했다. 생성 kernel release는 `6.18.13-gc21449208550`이다.

그러나 현재 SK와 TMDS는 모두 `6.18.13-ti-00778-gc21449208550-dirty`를 실행한다. 기존
Qbu provenance 문서도 historical dirty Image의 source diff가 repo에 없다고 기록한다.
따라서 built-in pktgen Image나 matching module을 current dirty Image에 부분 deploy하면
kernel release와 module ABI/provenance 불일치가 생길 수 있다.

이 결과는 build failure가 아니라 deploy safety 판단이다. pktgen을 채택하려면 다음 중 하나를
명시적으로 선택해야 한다.

1. workspace clean source를 기준으로 새 Image와 matching modules를 두 board에 함께 deploy하고,
   기존 `/boot` Image/DTB 및 `/lib/modules`를 backup하는 reproducible test-kernel transition을 수행한다.
2. current dirty Image를 유지하고 high-rate pktgen phase는 보류한다.
3. current dirty Image와 정확히 대응하는 source/config/module provenance를 확보한 뒤 그 기준에서 pktgen을 build한다.

선택 전에는 새 kernel artifact를 board에 deploy하지 않는다.

### pktgen test-kernel staging 및 transfer readiness: 2026-07-15

selected `phase2-tsn-pktgen` branch의 build artifact는 다음과 같다.

```text
Image SHA-256:
fc2b8861be3e8bc50742c2ddde05e68a220d5d1f1ae162221f5a780954b4e54c

module release:
6.18.13-gc21449208550

installed module tree:
out/am64x-tsn-quant-validation/modules/lib/modules/6.18.13-gc21449208550

module tree size:
219 MiB
```

TMDS management SSH endpoint `192.168.0.220:22`는 host에서 `No route to host`로
접속할 수 없었다. 따라서 42 MiB kernel Image와 219 MiB module tree를 UART input으로
전송하지 않는다. full test-kernel transition의 다음 선행조건은 다음 중 하나다.

1. host에서 TMDS management network로 SSH/SCP 가능한 route 복구
2. user-approved USB/SD media deploy path 준비
3. 별도 host-side artifact transfer service(TFTP/HTTP 등)와 board reachability 확인

이 transfer precondition이 충족되기 전까지 current dirty Image를 유지하며, P1 high-rate
case는 시작하지 않는다.

### Management transfer path 상태: 2026-07-15

Host는 `192.168.0.246/24`이며 `192.168.0.220` route는 host `eth0`에 존재한다. UART에서
확인한 TMDS management `eth0`는 처음에는 admin-down/no-address였고, `192.168.0.220/24`를
부여해 admin-up으로 전환했다. 그러나 PHY는 계속 `Link detected: no`/`NO-CARRIER`다.

따라서 SSH/SCP blocker는 host routing이 아니라 TMDS management RJ45의 물리 link 부재다.
TMDS `eth0`을 host management network에 연결해 carrier가 올라온 뒤에만 Image/module transfer
readiness를 다시 확인한다.

### pktgen staging 후속 상태: 2026-07-23

이후 TMDS `eth0` management link는 host `192.168.0.246/24`와 TMDS `192.168.0.220/24` 사이에서 1 Gbps/full로 복구됐고 SSH/SCP가 가능해졌다. host에서 TMDS로 Image와 module archive staging 및 checksum 확인도 완료했다.

그러나 TMDS `eth2`와 SK `eth1`의 temporary `198.18.2.0/30` direct path에서 SK로 large artifact를 전달하는 SCP와 direct Python TCP stream은 stalled 또는 비정상 저속이었다. partial artifact와 temporary address는 정리했으며 boot Image와 modules는 변경하지 않았다. 이 상태와 재개 절차는 `session-handoff-2026-07-23.md`를 기준으로 한다.

### P2: Qbv gate conformance

기준 path는 기능 동작이 확인된 SK `eth0(CPSW) -> TMDS eth1(CPSW)`다. 이 path에서는
hardware `taprio` ON schedule 안에서 TC0 background가 자기 allocation을 초과한 backlog를
만들고도 TC2 critical traffic이 지정 window에 release되는지를 확인한다. all-open control은
gate effect sanity 확인에만 사용하며 latency-improvement 비교로 해석하지 않는다.

수집값:

- configured/operational schedule, base-time, cycle-time, queue/class counter
- critical TX raw-HW phase: `(tx_timestamp - base_time) mod cycle_time`
- expected window 내/외 packet count와 ratio
- phase p95/p99/max, window miss count와 ratio
- TC0 queue drop와 source offered/TMDS achieved rate

MCU+ EST source의 good/bad 판정식은 Linux raw sample의 분석 기준으로 사용한다.
즉 time slot이 class의 expected window 안이면 good, 밖이면 bad로 집계한다. MCU+ example의
`<= 1%` bad ratio는 첫 reference 기준이며, board-specific pass/fail budget은 결과를 본 뒤
별도로 정한다.

P2 시작 전에는 receiver timestamp frame type을 명시한다. CPSW RX filter 제약 때문에
일반 UDP capture를 RX raw-HW 측정값으로 표기하지 않는다. `plget`은 workspace에 없으므로
provenance가 확정되기 전에는 실행 대상이 아니다.

### P3: Qbu actual fragmentation 정량화

SK CPSW sender 100 Mbps certificate가 이미 있다.

```text
SK eth1 sender -> TMDS eth1 receiver
80 Mbps preemptible UDP + 10 Mbps express UDP
1472 byte, 30 s, force mode
TX fragment +25130, receiver assembly OK +25123
```

다만 이 certificate의 physical pair는 현재 active topology와 다를 수 있다. P3에서는
해당 pair를 먼저 cable peer proof로 재확정하거나, 현재 배선에서 같은 CPSW-to-CPSW
조건을 만들고 새 certificate를 작성한다.

IET off/on 각각에서 다음을 같은 time window에 기록한다.

- `MACMergeFragCountTx/Rx`, `MACMergeFrameAssOkCount`, assembly/SMD error
- express와 preemptible flow의 sent/received/lost packet
- actual offered/achieved rate, PCP/TC/queue counter, CPU load
- link speed, verify/force mode, minimum fragment size

이 단계는 Qbu가 실제로 fragment/reassemble했는지와 loss/error가 없는지를 정량화한다.
fragment가 0인 run은 Qbu latency 비교가 아니라 traffic overlap 또는 classification의
원인 분석 run으로 보존한다.

### P4: Qbu tail latency A/B

P4는 P3에서 actual fragmentation이 반복 확인된 동일 path에서 수행한다. 비교는 IET off와
IET on이며, express packet의 sequence, TX timestamp, RX timestamp, PCP, length를 raw data로
대응한다.

현재 CPSW-to-CPSW path에서 일반 UDP RX raw-HW를 기대할 수 없으므로 P4 시작 조건은 다음
둘 중 하나다.

1. SK CPSW sender와 TMDS ICSSG receiver를 연결한 100 Mbps path에서 P3 수준의 actual
   fragmentation을 새로 증명하고, sender generic UDP TX raw-HW와 ICSSG
   `HWTSTAMP_FILTER_ALL` RX raw-HW를 각각 직접 확인한 뒤 사용한다.
2. CPSW receiver path를 유지해야 한다면 external hardware timestamp measurement를 추가한다.

어느 경로든 gPTP offset bound와 packet pairing을 같은 run에 보존한 뒤 p50/p95/p99/p99.9/max,
loss, outlier count, IET off/on delta를 계산한다. P4는 현재 미시험이며 hardware 불능으로
판정된 항목이 아니다.

### P5: CPSW rate limiter 정량화

기존 `tc cbs ... offload 1`은 CPSW hardware offload 설정 실패가 확인됐다. 따라서 이
단계의 목표는 generic CBS/Qav 성공 재주장이 아니라 CPSW queue rate limiter의 정확도다.

`mqprio` queue mapping과 `tx_maxrate` HW rate limiter를 사용해 configured rate보다 높은
offered load를 주고, queue별 throughput, rate error, drop, 다른 class throughput, 장시간
stability를 기록한다. driver는 rate limiter enable을 TX queue high-to-low 순서로 요구하므로
적용 순서도 run record에 남긴다.

### P6: Qbv + Qbu 복합 A/B

P2와 P4의 timestamp/traffic method가 같은 path에서 성립한 뒤 다음 네 case를 수행한다.

```text
Qbv off / Qbu off
Qbv on  / Qbu off
Qbv off / Qbu on
Qbv on  / Qbu on
```

각 case는 critical latency distribution, gate violation, fragment/reassembly, gPTP offset,
packet loss, best-effort throughput을 같은 data contract로 비교한다.

### P7: TMDS MCU+ reference 시험

MCU+ CPSW TSN EST, CPSW gPTP, ICSSG TAS/gPTP는 TMDS64EVM (`am64x-evm`)에서 별도
reference test로 수행한다. 이는 Linux board state를 변경하지 않는 독립 작업이며,
Linux Qbv/Qbu 결과와 하나의 benchmark 표에 혼합하지 않는다.

MCU+ TSN EST listener의 host-based RX timestamp는 local API 문서의 errata `i2401` 경고가
있으므로 production claim 근거가 아니라 EST modulo/good-bad 판정 reference로 사용한다.
물리 PHC absolute phase accuracy가 필요해지면 P7 이후 SYNC_OUT과 oscilloscope를 별도
계측으로 추가한다.

## 현 시점의 실행 순서

### 2026-07-15 UART read-only readiness 확인

P0 시작 전 UART로 `shared-clean-v1` 상태를 읽기 전용 확인했다.

| Board | 관찰 상태 | 판정 |
|---|---|---|
| SK-AM64B | `eth0`/`eth1` link up, IPv4 없음, custom qdisc 없음, MAC Merge pMAC/TX/verify off, TX queue 8, bridge/netns/test process 없음 | P0 시작 가능 |
| TMDS64EVM | `eth1`/`eth2` link up, IPv4 없음, custom qdisc 없음, `eth1` MAC Merge off, TSN service disabled, test process 없음 | P0 시작 가능 |

TMDS `eth2`의 idle pMAC 표시는 기존 `shared-clean-v1` contract가 driver별 baseline 차이로
판정 대상에서 제외한 값이다. 따라서 readiness failure가 아니다. 이번 확인은 link-up과
runtime cleanup만 확인했으며, 현재 cable peer MAC mapping과 HWTSTAMP filter state는 P0에서
새로 기록해야 한다.

다음 직접 작업은 P0과 P1이다.

1. 현재 케이블의 peer MAC proof로 path와 CPSW/ICSSG receiver를 확정한다.
2. CPSW와 ICSSG 각각에 requested/returned HWTSTAMP filter를 수동 확인한다.
3. 같은 physical link에서 gPTP idle/load log를 수집해 PHC offset bound를 만든다.
4. P2의 timestamp frame type과 `plget` source provenance 여부를 결정한다.
5. P3의 100 Mbps Qbu certificate를 current cable pair에서 새로 수집한다.
6. P3 결과와 receiver HWTSTAMP capability에 따라 P4의 CPSW-ICSSG 또는 external timestamp 경로를 선택한다.

이 순서를 끝내면 Qbv, Qbu, CBS, MCU+ reference의 측정 방법과 결과 해석 경계가 모두
명확해지며, 이후 정량 시험은 임의의 traffic run이 아니라 정의된 A/B matrix로 진행할 수 있다.
