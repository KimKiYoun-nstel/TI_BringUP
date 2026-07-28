# P1 gPTP High-Load 정량 검증 결과

## 결론

P1은 TMDS64EVM `eth2`에서 SK-AM64B `eth1`으로 background traffic을 발생시킬 때,
gPTP 동기화가 유지되는지 확인한 시험이다. Qbv/Qbu 기능 효과나 application packet의
one-way latency를 측정한 시험은 아니다.

이번 P1의 최종 판정은 다음과 같다.

| 조건 | 최종 판정 | 말할 수 있는 범위 |
|---|---|---|
| actual 약 800 Mbit/s, 60 s | PASS | gPTP `SLAVE` 유지, TX timestamp timeout 및 sync loss 없음 |
| actual 850.1, 900.2, 953.9 Mbit/s, 각 60 s | 안정 관찰 | 해당 단일 run에서 state transition 없음 |
| actual 960.8~971.4 Mbit/s | unstable | 5회 중 2회에서 `SLAVE -> MASTER` announce receipt timeout 관찰 |
| actual 약 984 Mbit/s, 60 s unlimited | FAIL 재현 | peer-delay TX timestamp polling timeout과 `FAULTY` 반복 |

따라서 현 current kernel/current firmware 조건에서 **800 Mbit/s는 검증된 P1 안정
background-load 조건**이다. actual 960 Mbit/s 이상은 정상 run이 일부 있더라도 gPTP
stability PASS로 사용하지 않는다. 이 결과는 ICSSG hardware specification limit을 확정한
것이 아니라, 이 시험 구성에서 관찰한 operational limit이다.

## 시험 목적

gPTP는 Qbv gate timing, Qbu A/B 비교, timestamp pairing에 필요한 공통 시간축의 기반이다.
P1의 목적은 다음 질문에 답하는 것이다.

> Ethernet link가 큰 background traffic을 처리하는 중에도 TMDS ICSSG의 gPTP packet과
> hardware TX timestamp 처리가 정상적으로 유지되는가?

이 시험에서 확인하는 것은 gPTP control-plane health다.

- PTP state (`SLAVE`, `FAULTY`, `MASTER`)
- peer-delay TX timestamp timeout 유무
- clock offset 및 path delay 추세
- traffic actual achieved rate
- link flap 및 `ptp4l` restart 이후 recovery time

이 시험에서 확인하지 않는 것은 다음과 같다.

- Qbv gate 안/밖 packet 비율
- Qbu fragment/reassembly 또는 express latency
- 일반 application packet의 end-to-end loss-free delivery
- packet별 TX/RX raw-HW timestamp 기반 one-way latency

## 고정 시험 구성

```text
TMDS64EVM eth2 (ICSSG, /dev/ptp2, 70:ff:76:20:22:9a)
       -- 1 Gbps/full direct cable --
SK-AM64B eth1 (CPSW/CPTS, /dev/ptp0, 70:ff:76:1f:f2:87)
```

- SK `eth1`: L2/P2P hardware-timestamp `ptp4l` grand master
- TMDS `eth2`: L2/P2P hardware-timestamp `ptp4l` slave
- generator: TMDS `/tmp/trafgen`, target arm64 binary
- traffic: TMDS source MAC에서 SK destination MAC으로 향하는 1514-byte unknown EtherType
  (`0x88b5`) raw frame
- duration: 각 high-load sample 60 s
- traffic accounting: trafgen TX summary와 SK netdev RX packet/byte delta를 함께 기록

`trafgen -P 1-1`은 CPU ID 지정이 아니라 one fork 지정이다. trafgen output은 one-fork
run에서 `CPU0`를 표시한다. CPU placement를 분리한 진단 run에서만 `taskset`을 사용했다.

각 run 후 `ptp4l`을 종료하고 양 board의 HWTSTAMP TX/RX filter를 off로 복귀했다. final
state에서도 `ptp4l`은 실행하지 않으며 TMDS `/tmp/trafgen` binary만 재사용용으로 남겼다.

## PASS/FAIL 방법

P1은 사전에 board-specific offset budget이나 exact rate tolerance가 정해진 certification
시험이 아니었다. 따라서 다음 operational rule로 판정했다.

| 판정 | 조건 |
|---|---|
| 안정 PASS | 60 s 동안 TMDS가 `SLAVE`를 유지하고, sync loss, `FAULTY`, peer-delay TX timestamp timeout이 없으며, achieved rate와 PTP log를 보존 |
| unstable | `SLAVE -> MASTER` 같은 PTP state transition 또는 announce receipt timeout이 발생 |
| FAIL | peer-delay request/response의 TX timestamp polling timeout과 `FAULTY`가 발생 |

SK netdev RX packet/byte delta는 sender accounting과 대응했다. 다만 unknown EtherType frame에는
application receiver가 없고 `rx_dropped`가 증가할 수 있으므로, 이 counter는 frame arrival
증거일 뿐 end-to-end loss-free proof로 사용하지 않는다.

## 결과

### Idle 및 80% 조건

idle에서 TMDS는 `SLAVE`로 수렴했고 steady RMS는 `1~16 ns`, max는 `2~21 ns`, path delay는
`435~437 ns`였다.

80% rate-mode에서는 trafgen이 actual 약 `800.1 Mbit/s`를 60 s 동안 발생했다.

- sender: `6,000,072,840 byte`
- TMDS state: `SLAVE` 유지
- steady RMS: `1~19 ns`
- max: `1~23 ns`
- path delay: 일시 `454 ns`, steady `437~440 ns`
- TX timestamp timeout, `FAULTY`, sync loss: 없음

따라서 800 Mbit/s case는 P1 PASS로 채택한다.

### Rate Sweep 및 Near-Line 결과

| Requested | Achieved | 상태 | 해석 |
|---|---:|---|---|
| 850 Mbit/s | 850.1 Mbit/s | 안정 | `SLAVE` 유지 |
| 900 Mbit/s | 900.2 Mbit/s | 안정 | `SLAVE` 유지 |
| 950 Mbit/s | 953.9 Mbit/s | 안정 | `SLAVE` 유지 |
| 960 Mbit/s | 942.7 Mbit/s | 안정 참고 | achieved rate가 낮아 boundary 근거에서 제외 |
| 975 Mbit/s | 971.1 Mbit/s | unstable | announce receipt timeout, `SLAVE -> MASTER` |
| 975 Mbit/s repeat | 971.2 Mbit/s | 안정 | 60 s state transition 없음 |
| 975 Mbit/s 추가 3회 | 960.8, 969.1, 971.4 Mbit/s | 혼재 | 969.1 Mbit/s에서 `SLAVE -> MASTER` |
| unlimited repeat | 984.0 Mbit/s | FAIL | TX timestamp timeout 및 `FAULTY` 반복 |

rate-mode achieved rate가 고부하에서 request와 일치하지 않았고, 같은 975 Mbit/s request도
960.8~971.4 Mbit/s로 달랐다. 따라서 단일 숫자로 “이 rate부터 반드시 실패”라고 정할 수
없다. 현재 evidence에서는 actual 960 Mbit/s 이상을 unstable diagnostic range로 취급한다.

### CPU 및 Scheduling 분리 진단

다음은 CPU가 유일한 원인인지 확인하기 위한 temporary diagnostic run이다.

| 조건 | Achieved | 결과 |
|---|---:|---|
| TMDS generator CPU0, TMDS CPU1 busy-loop | 948.5 Mbit/s | `SLAVE` 유지 |
| SK 유일 CPU0 busy-loop | 800.2 Mbit/s | `SLAVE` 유지 |
| TMDS generator CPU1, TMDS `ptp4l` CPU0 | 983.4 Mbit/s | TX timestamp timeout 및 `FAULTY` 반복 |
| 위 조건 + TMDS `ptp4l` `SCHED_FIFO` priority 50 | 983.8 Mbit/s | 동일 failure 반복 |

TMDS ICSSG IRQ는 CPU0/CPU1 모두 허용됐지만 관찰 시 counter는 CPU0에서 증가했다. ICSSG
firmware queue overflow, dropped packet, TX timestamp dropped counter는 diagnostic run 후 모두
0이었다.

이로부터 다음을 알 수 있다.

- generator가 CPU0에서 실행되는 것만으로 failure를 설명할 수 없다.
- `ptp4l` userspace priority를 올리는 것만으로 failure를 해결할 수 없다.
- ICSSG TX timestamp completion의 kworker/IRQ scheduling, driver/firmware queue path, gPTP
  traffic-class/queue mapping은 여전히 확인해야 한다.

이는 hardware defect나 hardware spec limit의 확정 근거가 아니다.

### Recovery

| 시험 | 결과 |
|---|---|
| TMDS `ptp4l` restart | process start 후 약 7.2 s에 `SLAVE`, 약 18 s 내 수십 ns 이하로 수렴 |
| TMDS `eth2` 5 s link flap | link up 후 약 15.1 s에 `SLAVE`, 약 31 s 내 수십 ns 수준으로 수렴 |

## 과정의 특별 이슈

### pktgen test-kernel 경로 중단

`CONFIG_NET_PKTGEN=y` test kernel은 TMDS에서 pktgen banner까지 boot했지만 rootfs
`PARTUUID`를 찾지 못해 login에 도달하지 못했다. original Image/DTB/modules는 rollback 후
정상 복구했고, 이후 P1은 current kernel Image를 유지하는 trafgen으로 수행했다. 이 boot
failure는 P1 gPTP 결과가 아니라 pktgen test-kernel deployment 경로의 별도 이슈다.

### High-rate UDP receiver는 P1 generator로 부적합

TMDS-to-SK parallel iperf3 UDP는 sender 약 793 Mbit/s에도 SK receiver achieved rate가
10.74 Mbit/s, loss가 98.57%였다. 이 경로는 SK userspace receiver bottleneck 때문에 P1
high-rate load profile로 사용하지 않았다.

### trafgen의 적용 범위

P1 trafgen frame은 unknown EtherType raw background traffic이다. Qbv/Qbu PCP/queue mapping,
gate conformance, packet latency pairing에는 사용할 수 없다. P2 이후에 trafgen을 사용하려면
packet format, traffic class, qdisc path와 receiver timestamp method를 별도 qualification해야 한다.

## 제약

- current TMDS kernel은 `6.18.13-ti-00778-gc21449208550-dirty`이고 exact historical source
  provenance가 없다. 결과는 이 running artifact에 한정한다.
- SK CPSW RX HWTSTAMP는 generic UDP RX raw-HW filter를 지원하지 않는다. P1의 PTP health는
  유효하지만 one-way latency measurement 기반은 아니다.
- traffic generator의 high-rate actual rate가 requested rate와 완전히 일치하지 않는다.
- 60 s sample 수와 rate sweep 반복 수는 driver/firmware의 formal threshold 또는 reliability
  probability를 정하기에 충분하지 않다.
- P1의 800 Mbit/s PASS는 gPTP stability 결론이며 generic application traffic loss 보증이 아니다.

## 선택 가능한 후속 시험

P1을 다시 열 필요는 없지만, 아래 시험은 원인 분리 또는 TSN mitigation 확인에 유용하다.

1. ICSSG TX timestamp completion에 관련된 IRQ, kworker, driver/firmware queue의 trace/counter를
   같은 984 Mbit/s failure 조건에서 수집한다.
2. 동일 achieved near-line rate에서 gPTP traffic class/queue mapping을 확인하고 Qbv off/on 또는
   priority queue A/B로 gPTP protection 효과를 본다.
3. 950 Mbit/s 부근을 여러 번 반복해 operational stable envelope를 더 좁힌다.
4. Stage 0 `QUALIFY_TIMESTAMP_1G_01`을 수행해 P2 Qbv phase/Qbu latency 검증에 필요한 TX/RX
   raw-HW timestamp와 sequence pairing을 확보한다.

## 증적과 관련 문서

- detailed session evidence: `docs/session-handoff-2026-07-23.md`
- measurement gate/data contract: `docs/measurement-plan.md`
- topology: `config/topology.yaml`
- raw local logs: `artifacts/p1-2026-07-23/`
- raw log checksum manifest: `artifacts/p1-2026-07-23/checksums.sha256`

raw logs와 trafgen binary는 Git 제외 local artifact다. source commit, build method, binary checksum은
`session-handoff-2026-07-23.md`에 기록한다.
