# AM64x TSN 검증 종합 정리

작성일: 2026-10-27. 대상: 현재 작업 트리의 `projects/` 문서, 시험 도구, 로컬 결과 artifact.
보드 연결 없이 수행한 기록 검토이며 신규 실보드 시험 결과는 아니다. 확인된 시험 기록은
2026년 6월부터 8월 11일까지다. 부팅 흐름상 주 대상은 **Linux 부팅 후 Ethernet/QoS/PTP
동작 검증**이고, C Case만 U-Boot 자원 할당 → Linux DT ownership → R5F remoteproc까지 포함한다.

2026-11-04 장비 이전에서는 사용자 결정에 따라 TSN raw artifact/log를 전송하지 않는다.
아래 raw 경로는 원본 장비에서 검토한 증적의 provenance이며 새 장비의 파일 존재를 뜻하지 않는다.
검증 결론과 한계는 이 문서 및 프로젝트의 추적 문서로 전달한다.

## 1. 핵심 결론

1. **CPSW endpoint 경로는 PCP 송출, 직접 연결 gPTP, HW Qbv gate 제어, 실제 Qbu
   분할·재조립까지 확인했다.** 다만 각각의 시험 조건과 송신 방향이 다르다.
2. **CPSW switchdev의 PCP 보존은 확인했지만 시간 동기화까지 통합된 TSN switch는 완성하지 못했다.**
3. **Linux ICSSG endpoint는 gPTP와 단독 HW taprio egress가 동작했다.** 그러나 시험한
   same-port HW taprio + gPTP 조합은 불안정/실패였고, near-line 부하에서도 gPTP 오류가 있었다.
4. **Qbv의 가장 강한 증거는 P2 CPSW→CPSW 5 × 300초 window 검증**이다. lower-class backlog
   중 150만 critical packet의 TX raw-HW phase가 지정 window 안에 있었다.
5. **Qbu activation 성공은 무손실·지연 개선 보증과 다르다.** 최신 5 × 300초 무손실 표본도
   있지만, 이전 반복·독립 reboot에서 loss/SMD 오류가 있었고 production profile은 확정되지 않았다.
6. 일반 application packet의 **one-way latency 개선, hard real-time deadline, TSN 표준 전체
   적합성**은 이 기록으로 보증하지 않는다.

## 2. Ethernet 장치와 시험 배선

### 2.1 무엇을 구분해야 하는가

`eth0/eth1/eth2`는 Linux interface 이름이다. TSN 결과를 비교할 때는 그 뒤의
**Ethernet subsystem(MAC/스위치), driver, firmware, PHC, 운용 모드**를 함께 봐야 한다.
외부 PHY 또는 RJ45 포트 번호만으로 기능 차이를 설명할 수 없다.

| 시험 이미지의 보드/포트 | Ethernet subsystem / driver | PHC | 시험상 역할 |
|---|---|---|---|
| SK `eth0`, `eth1` | CPSW3G / `am65-cpsw-nuss` | 두 포트가 `/dev/ptp0` CPTS 공유 | endpoint 또는 switchdev 2포트 forwarding |
| TMDS `eth0`, `eth1` | CPSW3G / `am65-cpsw-nuss` | `/dev/ptp0` | eth0 관리, eth1 시험; 설정 변경 시 같은 CPSW instance 영향 고려 |
| TMDS `eth2` | ICSSG / `icssg-prueth` | `/dev/ptp2`, ICSS IEP | Linux endpoint, CPSW와 비교 |
| C Case의 TMDS ICSSG dual-port | MCU+ firmware / R5F 소유 | firmware 시간축 | Linux Ethernet ownership을 해제한 gPTP bridge 이식 시험 |

위 매핑은 일반 시험 이미지 기준이다. C Case dualmac overlay에서는 포트 매핑/ownership이
달라지므로 기존 `eth1=CPSW` 가정을 그대로 적용하지 않는다. PHC 번호도 해당 이미지의 관측값이다.
근거: [DSCP/PCP 포트 표][dscp], [C Case review][ccase].

### 2.2 기록에 등장하는 배선은 하나가 아니다

| 시험군 | 배선/방향 | 의미 |
|---|---|---|
| 초기 gPTP | SK eth1 ↔ TMDS eth1 | CPSW↔CPSW PHC 및 system clock 시험 |
| gPTP canonical, P1 | SK eth1 ↔ TMDS eth2 | CPSW↔ICSSG, P1 부하는 TMDS→SK |
| DSCP/PCP switch, Qbv Phase A, 7/14 자동화 | SK eth0 ↔ TMDS eth1 + SK eth1 ↔ TMDS eth2 | 두 direct pair 또는 SK switchdev 경유 |
| P2 formal Qbv | SK eth0 → TMDS eth1 | CPSW→CPSW, same-port gPTP |
| Qbu canonical/P3 | TMDS eth1 → SK eth1 | CPSW→CPSW, 1 Gbps/full |
| C Case | SK eth0 → TMDS ICSSG port1/port2 → SK eth1 | R5F gPTP bridge 후보 |

따라서 프로젝트 README의 “현재 배선”은 그 시험 당시의 기준이다. P3 문서 일부의 P2와
“동일 cable” 표현보다 P2 runner/결과의 `SK eth0`와 P3 결과의 `SK eth1`을 구분해 읽는다.
자동화는 carrier만 보지 않고 ARP source MAC으로 실제 peer pair를 확인했다.

## 3. 시험과 TSN feature의 대응

| 시험 | 검증하려던 feature/질문 | 사용 방법 | 도달한 증거 수준 |
|---|---|---|---|
| gPTP direct / P1 | 공통 시간축, 802.1AS 관련 동기화 및 부하 안정성 | L2/P2P HW timestamp `ptp4l`, state/offset/delay, trafgen 부하 | direct 동기화·조건부 부하 안정성 |
| DSCP/PCP | QoS 분류 정보의 주입/보존 | VLAN, egress map, skbedit, receiver pcap | DSCP/PCP 보존; DSCP 자동 우선처리는 미입증 |
| mqprio | priority→TC/queue 연결 | class counter, TX_PRI_MAP, 분리 traffic | local TX class mapping; switch offload 내부 관측 제한 |
| CBS | 802.1Qav credit-based shaping | HW/SW cbs 적용 비교, 두 flow rate 비교 | software shaping 확인, HW offload reject |
| Qbv Phase A/B | 802.1Qbv time-aware egress와 gPTP 공존 | taprio, traffic/capture, cycle/burst 관찰 | 기능 수용/egress, 일부 timing; 초기 strong proof 부족 |
| Qbv P2-Q0/Q3 | 실제 gate enforcement 및 class window isolation | PTP 형식 probe raw-HW TX/RX, background backlog | closed-gate 지연 및 반복 window service |
| Qbu 및 P3 | 802.1Qbu/802.3br MAC Merge preemption | MM 설정, express/preemptible 동시 부하, fragment/reassembly delta | 실제 activation, workload별 loss/error 운용 범위 |
| C Case | ICSSG time-aware gPTP bridge 이식 | resource ownership, remoteproc, wire capture, firmware trace | bring-up 성공, donor-equivalent gPTP bridge 실패 |

`ptp4l SLAVE`나 Linux 설정 수용은 해당 기능의 제한된 증거이며 IEEE 표준 전체 적합성 인증은 아니다.
DSCP는 IP QoS 필드, PCP는 VLAN 우선순위이며 그 자체가 시간 보장 기능은 아니다.

## 4. 시간 동기화: gPTP와 P1

### 4.1 Direct, 일반 L2 switch, 외부 pulse

공통 설정은 `network_transport L2`, `delay_mechanism P2P`, `time_stamping hardware`,
`twoStepFlag 1`이다. `tcpdump ether proto 0x88f7`와 `ptp4l` 상태·RMS·path delay를 확인했다.

| 시험 | 관측 결과 | 확인 가능 범위/제약 |
|---|---|---|
| 초기 CPSW↔CPSW direct | TMDS SLAVE, delay 약 426~427 ns, RMS 수 ns 수준으로 수렴 | PHC 간 동기화 성립; application latency 값 아님 |
| CPSW↔ICSSG direct | stable SLAVE, delay 약 438~440 ns | heterogeneous endpoint 동기화 성립 |
| `phc2sys` | MASTER PHC epoch 보정 후 TMDS system clock offset 약 -0.21 ms | 당시 system clock 보정 성공; ns 수준 system-clock accuracy 증명 아님 |
| 일반 local L2 switch 경유 2×3 port 조합 | PTP frame/BMCA 관찰, 모두 UNCALIBRATED, stable SLAVE 미확보 | 일반 forwarding/BMCA만으로 P2P 동기화 성립하지 않음; 모든 switch의 불능으로 일반화 불가 |
| PHC perout/PPS | SK perout 2/PPS 1, TMDS ICSSG perout 1/PPS 1 및 ioctl 확인 | scope 기반 동시 pulse 측정 미완료; SK pinmux ECAP0, TMDS probe point 확인 필요 |

근거: [gPTP 결과][gptp]. `ptp4l`의 path delay와 servo RMS는 독립 계측기로 측정한
종단간 시간 오차가 아니다. SK 두 CPSW 포트는 PHC를 공유하므로 독립 clock pair로 볼 수 없다.

### 4.2 P1 high-load: ICSSG TX 중 gPTP 유지 여부

- TMDS eth2(ICSSG) → SK eth1(CPSW), 1 Gbps/full; SK GM, TMDS slave.
- TMDS `trafgen`으로 1514-byte unknown EtherType `0x88b5` frame 송신, run당 60초.
- sender actual rate와 SK RX delta, 양 보드 PTP log를 대조했다.

| Achieved rate | 결과 |
|---|---|
| 약 800.1 Mbps | 채택 PASS: SLAVE 유지, timeout/FAULTY/sync loss 없음; steady RMS 1~19 ns, max 1~23 ns |
| 850.1 / 900.2 / 953.9 Mbps | 각 단일 run 안정 관찰 |
| 960.8~971.4 Mbps | 5회 중 2회 announce timeout, SLAVE→MASTER; unstable |
| 약 984 Mbps unlimited | Pdelay TX timestamp polling timeout, FAULTY 반복 |

CPU 분리 및 `ptp4l SCHED_FIFO 50`만으로 near-line 실패가 해결되지 않았다. process restart 후
약 7.2초, 5초 link flap 후 link-up 기준 약 15.1초에 SLAVE로 복귀했다.

**확인한 것:** 해당 kernel/firmware의 800 Mbps·60초 gPTP 안정 조건과 near-line 운용 문제.
**확인하지 못한 것:** ICSSG 하드웨어 최대 성능, 정확한 실패 임계값, 일반 UDP 무손실,
Qbv/Qbu 적용에 따른 개선. unknown EtherType RX drop은 application delivery 판정 지표가 아니다.
고부하 iperf3는 SK receiver 병목(약 793 Mbps 송신, 10.74 Mbps 수신, 98.57% loss) 때문에
P1 부하원에서 제외했다. pktgen test-kernel의 rootfs PARTUUID 부팅 실패도 TSN 기능 실패와 구분한다.
근거: [P1 결과][p1].

## 5. DSCP/PCP, queue mapping, CBS

### 5.1 구성과 방법

```text
TMDS ep2 / eth2.301 (ICSSG)
  → SK eth1 → br-tsn / CPSW switchdev → SK eth0
  → TMDS ep1 / eth1.301 (CPSW)
```

두 namespace로 endpoint를 분리하고 VLAN 301, UDP 5001/5002에 priority 7/6을 주었다.
VLAN egress map과 `tc skbedit priority`를 적용한 뒤 최종 receiver **parent interface**에서
PCP를 읽었다. VLAN subinterface capture는 outer tag를 제거하므로 wire PCP 판정에 부적합하다.

### 5.2 결과와 의미

- 초기 IP DS/TOS byte `0x00/0x28/0x88/0xb8` 보존 확인. 이 값은 6-bit DSCP 번호 자체가
  아니라 기록의 byte 표현이다. DSCP-only 혼잡 우선순위 효과는 미입증이다.
- 초기 CPSW PCP=0 문제는 `RX_REMAP_VLAN` patch 누락이 아니었다. SDK source에 이미 있었다.
- `p0-rx-ptype-rrobin off` + `mqprio hw 1 mode channel` + VLAN egress map + skbedit 후
  CPSW direct p7/p6 송출 및 ICSSG→SK switchdev→CPSW receiver p7/p6 보존을 확인했다.
- mqprio candidate map으로 local control path의 p7→class100:3, p6→100:2, p0→100:1과
  TX_PRI_MAP register 변경을 확인했다. **wire PCP, skb priority, TC 번호는 동일 개념이 아니다.**
- CBS HW offload는 reject됐다. software CBS에서는 p7 10 Mbps→약 1 Mbps shaping,
  background p0 20 Mbps 유지가 관찰됐다. 이를 hardware CBS 지원 완료로 표현하지 않는다.
- SK local tcpdump가 0 packet인 현상은 switchdev hardware-offloaded forwarding의 관측 한계다.
  같은 이유로 host qdisc counter만으로 forwarded packet의 queue 경로를 단정하지 않는다.

근거: [DSCP/PCP 결과][dscp], [Qbv 단계별 결과][qbv-results].

## 6. Qbv: 기능 확인에서 실제 gate 정량 검증까지

### 6.1 Phase A endpoint 비교

bridge/switch 모드에서 분리한 `switch_mode=false` direct path에서 SW/HW taprio를 적용하고,
filter 증가·iperf 수신·PCP capture를 확인했다. HW는 `flags 0x2`, SW는 `clockid TAI`로 구분했다.

| 송신 → 수신 | SW/HW egress | SW + gPTP | HW + gPTP |
|---|---|---|---|
| SK eth0 CPSW → TMDS eth1 CPSW | 둘 다 성공 | 성공 | 성공, reference path |
| SK eth1 CPSW → TMDS eth2 ICSSG | 둘 다 성공 | 성공 | partial/unstable, PTP 상태 재천이 |
| TMDS eth2 ICSSG → SK eth1 CPSW | 둘 다 성공 | 성공 | 실패, TX timestamp timeout/FAULTY |

CPSW minimum reference는 500 µs cycle(125/125/250 µs), ICSSG sender는 관측된 minimum
cycle 제약으로 1 ms와 TX=3을 사용했다. CPSW→CPSW safe schedule에서는 20 Mbps traffic,
loss 0과 SLAVE 수렴을 함께 확인했다. reverse TMDS CPSW sender는 당시 eth0 관리 유지
제약으로 Phase A 범위에서 제외됐다. 이것은 후속 Qbu 방향 검증과 모순되지 않는다.

Phase B는 500 µs/8 ms cycle의 burst 및 처리율 제한을 관측했지만 schedule inversion과
future base-time phase shift의 strong proof는 확보하지 못했다. 후속 P2 성공을 Phase B의
모든 미완료 항목 완료로 소급하지 않는다. 근거: [Phase A][phasea], [Phase B 요약][qbv-results].

### 6.2 P2-Q0: 실제 gate가 packet을 막는가

generic UDP RX raw-HW filter 제약을 피하기 위해 **PTPv2 L2 Sync 형식의 시험 packet**을 썼다.
이는 동기화용 gPTP와 구분되는 domain 127, 128 B, VLAN 311 probe다.

- 초기 raw frame PCP 7 + SO_PRIORITY=3에서는 child qdisc hit가 있어도 closed gate를 통과했다.
- 같은 frame에서 wire PCP만 2로 바꾼 뒤 실제 gate 제어를 확인했다.
- 500 µs cycle: `0x6 125 µs → 0x3 375 µs`; TC1 gPTP always-open, TC2 probe만 선택 개방.
- closed phase 200 µs 송신: TX/RX 각 100/100 raw-HW, 다음 open까지 300.370 µs 대기,
  TX phase 0.370 µs, RX phase 0.792~0.794 µs.
- open phase 시험은 대체로 즉시 송출했지만 scheduler miss 1개는 다음 cycle까지 대기했다.

**의미:** taprio 설정 수용/queue hit만으로 gate enforcement를 주장할 수 없으며,
검증된 raw PCP/priority 조합이 필요하다. 근거: [P2-Q0][p2q0].

### 6.3 P2-Q3 formal: lower-class backlog 중 window isolation

SK eth0→TMDS eth1 CPSW direct, 1 ms cycle을 사용했다.

| Class | Gate/window | 부하 |
|---|---|---|
| TC2 | 0x4 / 첫 500 µs | PCP 2, SO_PRIORITY 3 probe, 1 ms period, 예정 window 450 µs 전 enqueue |
| TC1 | 0x2 / 다음 250 µs | same-port gPTP, socket priority 2 |
| TC0 | 0x1 / 마지막 250 µs | default priority UDP, iperf3 request 500 Mbps |

검증은 raw-HW count, TX gate phase, 예정 release 대비 TX 차이 p99, background rate,
TC0 PFIFO drop, 종료 gPTP state를 함께 사용했다.

| 항목 | 5 × 300초 결과 |
|---|---|
| TX/RX raw-HW count | run당 각 300,000; 전체 각 1,500,000 |
| critical TX phase | 전 sample TC2 500 µs window 내; p99 9.426 µs, run별 max 240.042~448.146 µs |
| 예정 release 대비 TX 차이 p99 | 9.426~10.642 µs |
| TC0 sender / receiver | 274.359~280.795 / 242.297~243.291 Mbps |
| TC0 queue drop | 합계 4,503,840 packet |
| 종료 TMDS gPTP | 5회 모두 SLAVE |

**채택 판정:** 실행된 validity gate 기준 5회 PASS. 250 Mbps allocation을 초과한 TC0 backlog
아래에서도 critical class의 scheduled TX window service가 확인됐다.

**해석상 주의와 문서/구현 차이:**

- `critical_release_p99_ns`는 `TX timestamp - planned_phc_ns`이다. enqueue부터의 전체
  대기 시간이나 `RX - TX` one-way latency가 아니다.
- 계획서 prose는 source rate가 allocation의 110% 초과라고 하지만 코드의 gate는
  **250 Mbps 초과**다. run-02의 274.359 Mbps는 275 Mbps에 미달한다. 따라서 “모든 run이
  110% 조건 충족”은 부정확하다. backlog/window 결과는 유효하되 엄격한 110% 계획 충족과 구분한다.
- formal summary는 TX phase와 RX raw-HW **개수**를 판정한다. 그 자체로 모든 RX phase,
  packet별 latency pairing 분석 완료 또는 연속 gPTP 안정성을 증명하지 않는다.
- modulo phase와 p99 통과만으로 모든 packet의 target cycle deadline/zero-miss를 보증하지 않는다.
- 물리 1 Gbps 포화 시험이나 all-open 대비 latency improvement 시험이 아니다.
- run-03은 traffic 종료 후 UART route 단절로 수집 실패했으나 SSH로 artifact를 회수해 재판정했다.

근거: [P2 formal 기록][p2q3], [판정 코드][p2-code], [원본 집계][p2-artifact].

## 7. Qbu/IET: actual activation과 무손실 조건

### 7.1 기본 방법과 방향 차이

같은 CPSW instance의 두 port를 down한 뒤 TX=4로 바꾸고 QoS prerequisite를 적용했다.
MAC Merge pMAC/TX/verify를 설정하고 `mqprio ... fp P P P E`로 TC2 preemptible,
TC3 express를 지정했다. 대표 부하는 UDP 1472 B, TC2 200 Mbps + TC3 50 Mbps, 동시 30초다.

실제 preemption 증거는 **동일 traffic window의 sender fragment 증가와 receiver
fragment/reassembly 증가**다. MM enabled, verify success, class hit만으로는 충분하지 않다.

| 방향/조건 | 실제 결과 | 판정 |
|---|---|---|
| TMDS eth1 → SK eth0, 1 Gbps | historical TX +3,329 / assembly +3,328; 7/14 자동화 +2,591/+2,591 | actual Qbu 확인 |
| TMDS eth1 → SK eth1, 1 Gbps | historical +9,710/+9,710, 후속 P3 반복 | canonical actual Qbu 경로 |
| SK CPSW sender, 100 Mbps | TX/RX fragment +25,130, assembly OK +25,123 | SK IET TX path 동작 확인; 완전 무손실 주장은 아님 |
| SK CPSW sender, 1 Gbps | 시험한 userspace 부하에서는 fragment 0 | 충분한 overlap 미입증, HW failure로 판정 불가 |
| ICSSG sender | actual fragmentation 검증 미수행 | 지원 불가 판정도 불가 |

같은 netperf 계열에서 TMDS 2-core는 fragment +509,379였지만 두 generator를 CPU0에
pin하면 0이었다. SK는 당시 1 CPU 조건이다. 평균 bitrate뿐 아니라 preemptible frame 전송
도중 express packet이 도착하는 **시간적 overlap**이 중요하다.
초기 SK verify failure는 별도 미해결 문제이며 force-mode actual 성공과 구분한다.
근거: [Qbu canonical status][qbu], [자동화 결과][auto].

### 7.2 P3 traffic-conditioned 운용 범위

TMDS eth1→SK eth1 CPSW 1 Gbps에서 IET-off negative control, IET-on traffic sweep,
duration 확대, CPU affinity/pacing, RX buffer, fragment size A/B를 수행했다.
`active`는 activation 및 관측 loss/error 0, `degraded`는 activation과 loss/error 동반이다.
`valid:true`는 측정 성립이지 무손실 production PASS가 아니다.

| 단계 | 조건/반복 | 결과와 해석 |
|---|---|---|
| 초기 operational | on 5 profile × 3회, 각 30초 | 모두 activation 관찰; 50M/50M만 세 run 모두 active, 나머지 degraded |
| boundary | 50M/50M 60초 × 3 | active; 75M 혼재, 100M 이상 degraded |
| candidate | 50M/50M 300초 × 3 | active 2/degraded 1, express loss 2 발생; 55~70M fine sweep도 비단조적 loss |
| timing variance | CPU split + 100 µs pacing 결합, 300초 × 3 | 3회 무손실·무오류; 각 조치 단독은 실패 |
| 독립 reboot endurance | 결합 조건, 계획 on 10회 | 첫 300초에 preemptible loss 10으로 중단; fragment/assembly 각 +1,005,769, MM error 0 |
| RX buffer A/B | 229,376 B → 1 MiB | UDP RcvbufErrors 및 preemptible loss 제거 표본 확보; express loss/SMD 0/2/4 잔존 |
| fragment/pacing A/B | fragment 124/188/252 B, pacing 100/10 µs | 188은 후보이나 loss 잔존; 10 µs, 252 B, 낮은 20M preemptible도 해결책 아님 |
| 8/5 telemetry | 188 B, CPU split, 100 µs, 300초 × 3 | active 3회, loss/error 0 |
| 8/11 09:35 follow-up | 동일 계열 300초 × 5 | active 2/degraded 3; express loss 25/9/18, SMD 22/9/16 동반 |
| 8/11 10:50 correlation | 50M/50M, 1472 B, 188 B fragment, CPU0/1 split, 100 µs pacing, rmem 1 MiB, 300초 × 5 | **active 5회, 양 flow loss 0, assembly/SMD error 0**; activation 5/5 |

마지막 correlation 결과는 상태 문서의 “다음 diagnostic run”보다 뒤에 완료된 **로컬 artifact**다.
`campaign-status.json`은 completed/6 runs(control 1 + on 5), summary는 valid=true다.
sender fragment rate는 run별 7.5~384.057/s, median 55.02/s로 가변적이다.
09:35 원본 집계에는 preemptible loss max 3, assembly error max 0.01/s도 있어 express/SMD만의
문제로 축약하지 않는다.

**확인된 원인과 남은 가설:**

- receiver UDP socket overflow는 일부 preemptible loss의 직접 원인이다. 1 MiB buffer A/B가 근거다.
- 다른 표본의 express loss는 SMD error와 동반되며, buffer만 키워서는 해결되지 않았다.
- CPU placement/pacing에 따른 결과 차이는 관찰됐지만 driver/firmware/PHY 중 최종 root cause는 미확정이다.
- 최초 telemetry의 CPU0 column-only IRQ 집계와 서로 다른 wall-clock epoch 문제를 보정해
  CPU 합계 및 endpoint별 elapsed-time을 사용했다. 마지막 run에는 error가 없으므로 그 표본만으로
  IRQ service와 error의 인과관계를 증명할 수 없다.
- off control은 fragment/reassembly 0의 negative control로 유효하지만 대량 traffic loss가 있는
  `control-degraded`가 반복되어 on/off throughput·latency 개선 비교의 baseline으로 쓰지 않는다.
- 최신 1,500초 무손실 표본은 중요한 성공 증거지만 기존 실패를 삭제하지 않는다. 독립 reboot,
  반복성, 허용 loss/error, 교란 부하를 포함한 production acceptance는 여전히 미확정이다.

근거: [P3 상태/이력][p3-status], [operational][p3-op], [candidate][p3-candidate],
[endurance][p3-endurance], [loss 위치 분리][p3-loss], [09:35 집계][p3-followup],
[10:50 최신 집계][p3-correlation]. 이 시험군은 express one-way latency A/B를 수행한 것이 아니다.

## 8. TSN switch/bridge로서의 한계

### 8.1 Linux CPSW switchdev

PCP-preserving L2 forwarding은 성공했다. 그러나 재부팅 후 상태 분리에서 bridge-only는
gPTP를 통과하고 `bridge + switch_mode`부터 stable SLAVE가 깨졌다. mqprio-only 추가 여부보다
switch_mode와 관련된 blocker로 좁혔지만 최종 수정 완료 기록은 없다.
**endpoint Qbv 성공을 time-aware switch 성공으로 확대할 수 없다.** [Qbv 결과][qbv-results]

### 8.2 MCU+ ICSSG R5F C Case

Linux ICSSG driver를 그대로 쓰는 경로와 별개의 firmware 이식 시험이다.
ICSSG dual-port 확인, Linux ownership 분리 DT overlay, U-Boot ICSSG1 PKTDMA RM 공유,
remoteproc-ready firmware를 통해 `EnetUdma_openRxCh` blocker를 해결하고 task-entry까지 성공했다.

최종 fresh-start에서는 downstream slave가 self-GM으로 끝났다. firmware trace는
`port1/2 asCap=0`, `port2 across=0 neigh=0 compat2011=1`, `gptp_ascross` 0 hits였고,
downstream Sync/Follow_Up/Announce가 성립하지 않았다.
`compat2011=1`은 초기값일 수 있어 Pdelay completion 성공 증거가 아니다.

**판정:** remoteproc bring-up/ownership 해결 성공, donor `gptp_icssg_switch`와 동일 기능의
gPTP bridge 이식 실패. ICSSG silicon의 TSN 불능 증거가 아니라 해당 Linux remoteproc port의
미완성이다. SK 양 endpoint가 같은 PHC를 쓰는 계측 제약도 있다.
근거: [C Case review][ccase], [최종 기능 검증][ccase-final].

## 9. 장치별로 최종적으로 말할 수 있는 것

| 장치/모드 | 확인된 사항 | 남은 한계/문제 |
|---|---|---|
| CPSW Linux endpoint | HW timestamp gPTP, PCP 송출, HW Qbv; CPSW→CPSW P2 window isolation | generic UDP RX raw-HW 제약; 모든 방향/traffic에 동일 결론 불가 |
| TMDS CPSW sender Qbu | 1 Gbps actual fragmentation 반복, 최신 5×300초 무손실 표본 | 앞선 loss/SMD 및 reboot 실패, production 무손실/latency 개선 미확정 |
| SK CPSW sender Qbu | 100 Mbps actual preemption | 1 Gbps userspace overlap 미입증; 당시 단일 CPU 조건 |
| CPSW switchdev | DSCP/PCP 보존 forwarding | gPTP 통합 blocker, host capture/queue 관측 제한, HW CBS 미확인 |
| ICSSG Linux endpoint | direct gPTP, PCP 발생, SW/HW taprio egress | HW taprio+gPTP 실패/불안정, near-line timestamp timeout, Qbu sender 미검증 |
| ICSSG MCU+/R5F bridge | ownership 및 remoteproc bring-up | asCapableAcrossDomains 미성립, donor-equivalent bridge 미달 |

따라서 “AM64x TSN 지원 여부” 하나로 요약하기보다 **CPSW/ICSSG × endpoint/switch ×
Linux/MCU+ × 송신 방향 × 부하/이미지** 조합별로 판단해야 한다.

## 10. 재현성, 증적 보존 및 후속 확인

### 10.1 증적 수준

- 기반은 TI Processor SDK Linux 12.00.00.07.04, kernel baseline `c21449208550...`이다.
  다만 P1과 historical Qbu에는 `6.18.13-ti-00778-gc21449208550-dirty` running artifact가 등장한다.
  source baseline과 실제 사용 Image의 동일성을 자동 가정하지 않는다.
- Qbu는 feature 자체에 custom image delta가 필요하지 않다는 분석과 **TI SDK prebuilt actual
  certificate 미취득**을 구분한다. C Case는 별도 RM/DT/firmware 변경 의존성이 있다.
- 이번 검토에는 기존 미커밋 문서/도구도 포함했다. 특히 P3 결과 문서와 matrix/tool 다수가
  untracked 상태였으므로 이 문서는 commit된 HEAD만의 요약이 아니다.
- `artifacts/`, 자동화 `logs/`의 raw 자료는 Git 제외 로컬 보존이다. 여기서 P2 formal과 P3
  최신 두 campaign의 JSON 집계 및 자동화 Qbu result를 직접 대조했지만 모든 packet CSV/pcap을
  독립 재분석한 것은 아니다. clone만으로 raw 자료가 재현되지 않는다.

| 주요 raw 증적 | 이번 확인/역할 |
|---|---|
| `projects/am64x-tsn-validation-automation/logs/20260714-*/` | final run ID 및 Qbu result의 topology/PASS 대조 |
| `projects/am64x-tsn-quant-validation/artifacts/p1-2026-07-23/` | 디렉터리 존재; P1 수치는 결과 문서 기준 |
| `.../artifacts/qbv-multiclass-01-20260728-175056-kst/campaign-summary.json` | 5 run count/phase/rate/drop/SLAVE 직접 대조 |
| `.../artifacts/p3-qbu-operational-20260811-093501-kst/campaign-summary.json` | active/degraded, loss/error 직접 대조 |
| `.../artifacts/p3-qbu-operational-20260811-105003-kst/campaign-summary.json` | 문서보다 최신인 5회 active 결과 직접 확인 |

### 10.2 재시험 시 그대로 가져갈 원칙

1. run별 배선, MAC/driver/PHC, boot ID, Image/DTB/firmware hash, CPU online/IRQ를 고정한다.
2. bridge/VLAN/qdisc/MM/자동 network service residue를 제거하고 baseline을 확인한다.
3. CPSW TX channel 변경은 sibling port까지 down해야 한다. carrier settle 후 offload를 적용한다.
4. VLAN IP drift, PCP egress map 누락, taprio cycle 변경 시 del/add 필요성을 점검한다.
5. 요청 bitrate 대신 achieved rate와 실제 class-hit, gate phase, fragment/reassembly delta를 보존한다.
6. measurement-valid, 기능 activation, loss-free acceptance, transport/수집 실패를 구분한다.

우선 후속 질문은 Qbu 오류의 재현 가능한 원인 분리와 production acceptance 정의,
ICSSG HW Qbv+gPTP 및 near-line timestamp 문제, switchdev gPTP blocker,
일반 application timestamp qualification이다. Qbv 110% 계획/코드 차이와 P3 최신 결과의
canonical 문서 반영도 필요하다. 이 정리는 기존 시험을 재실행하거나 PASS 범위를 확장하지 않는다.

## 11. 프로젝트/근거 문서 색인

| 프로젝트 | 이 정리에서의 역할 |
|---|---|
| `am64x-gptp-eth1-lab` | direct/switch gPTP, phc2sys, PHC pulse capability |
| `tsn_dscp_pcp` | QoS prerequisite, PCP 송출/보존 |
| `tsn_qbv` | mqprio/CBS, switch blocker, endpoint SW/HW 비교, 초기 timing |
| `tsn_qbu` | clean baseline, 방향/속도/CPU별 actual preemption |
| `tsn_c_case` | MCU+ ICSSG bridge의 remoteproc 이식과 최종 실패 범위 |
| `am64x-tsn-validation-automation` | UART preflight/baseline, 7/14 기능 regression |
| `am64x-tsn-quant-validation` | P1 부하, P2 window, P3 activation/loss/error 정량 시험 |

[gptp]: ../../projects/am64x-gptp-eth1-lab/docs/results.md
[dscp]: ../../projects/tsn_dscp_pcp/docs/results.md
[qbv-results]: ../../projects/tsn_qbv/docs/results.md
[phasea]: ../../projects/tsn_qbv/docs/phaseA-endpoint-egress-qbv.md
[qbu]: ../../projects/tsn_qbu/docs/VALIDATION_STATUS.md
[ccase]: ../../projects/tsn_c_case/docs/project-review.md
[ccase-final]: ../../projects/tsn_c_case/docs/2026-07-06_gptp-bridge-fresh-start-validation.md
[auto]: ../../projects/am64x-tsn-validation-automation/docs/2026-07-14_first-automated-validation.md
[p1]: ../../projects/am64x-tsn-quant-validation/docs/p1-gptp-load-validation-2026-07-23.md
[p2q0]: ../../projects/am64x-tsn-quant-validation/docs/p2-q0-gate-enforcement-2026-07-28.md
[p2q3]: ../../projects/am64x-tsn-quant-validation/docs/p2-q3-multiclass-window-validation-plan-2026-07-28.md
[p2-code]: ../../projects/am64x-tsn-quant-validation/tools/p2_qbv_multiclass_pilot.py
[p2-artifact]: ../../projects/am64x-tsn-quant-validation/artifacts/qbv-multiclass-01-20260728-175056-kst/campaign-summary.json
[p3-status]: ../../projects/am64x-tsn-quant-validation/docs/p3-qbu-status-2026-07-31.md
[p3-op]: ../../projects/am64x-tsn-quant-validation/docs/p3-qbu-operational-campaign-result-2026-07-30.md
[p3-candidate]: ../../projects/am64x-tsn-quant-validation/docs/p3-qbu-candidate-qualification-result-2026-07-31.md
[p3-endurance]: ../../projects/am64x-tsn-quant-validation/docs/p3-qbu-combined-endurance-result-2026-08-04.md
[p3-loss]: ../../projects/am64x-tsn-quant-validation/docs/p3-qbu-loss-location-isolation-result-2026-08-04.md
[p3-followup]: ../../projects/am64x-tsn-quant-validation/artifacts/p3-qbu-operational-20260811-093501-kst/campaign-summary.json
[p3-correlation]: ../../projects/am64x-tsn-quant-validation/artifacts/p3-qbu-operational-20260811-105003-kst/campaign-summary.json
