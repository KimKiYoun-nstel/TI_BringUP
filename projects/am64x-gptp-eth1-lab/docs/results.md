# AM64x gPTP eth1 Lab Current Results

## 최신 정리

현재까지의 작업을 한 줄로 정리하면 다음과 같다.

```text
두 보드의 direct line에서는 path delay까지 측정 가능했지만,
local L2 switch에 연결하면 gPTP frame 송수신과 BMCA는 보이더라도
stable SLAVE 형성이 되지 않아 실질적인 gPTP 형상 완성까지는 가지 못했다.
```

### direct 경로 결론

- canonical direct 경로: `SK eth1 <-> TMDS eth2`
- 결과: `MASTER -> UNCALIBRATED -> SLAVE` 확인
- 결과: `rms / delay / freq` 안정화 확인
- 결과: path delay 약 `438~440 ns` 관측

즉 direct line 기준으로는 userspace `ptp4l` gPTP 동작과 path delay 측정이 가능했다.

### local L2 switch 경유 결론

- 시험 포트: `SK eth0`, `eth1` 대 `TMDS eth0`, `eth1`, `eth2`
- 결과: `0x88f7` frame 송수신 확인
- 결과: foreign master 관측 및 BMCA winner 형성 확인
- 한계: 모든 조합에서 `UNCALIBRATED`에 머물렀고 stable `SLAVE`까지는 내려가지 않음
- 한계: 포트별 path delay 수치는 확보하지 못함

즉 local L2 switch 경유 상태에서는 gPTP frame 교환은 되지만,
현재 구성 기준으로는 실질적인 gPTP 형상 완성으로 보기는 어렵다.

### 현재 유지할 배선 형상

- `SK eth0`: control port
- `TMDS eth0`: control port, 동시에 local L2 연결 유지
- `SK eth1 <-> TMDS eth2`: direct gPTP 측정 경로
- `TMDS eth1`: local L2 연결 유지

### PHC external pulse 관점의 현재 결론

- `ptp4l`은 PHC를 동기화할 뿐, 자동으로 외부 pulse를 내보내지는 않는다.
- 하지만 Linux runtime에서 PHC capability를 직접 확인한 결과:
  - SK `eth1 -> /dev/ptp0`: `n_per_out=2`, `pps=1`
  - TMDS `eth2 -> /dev/ptp2`: `n_per_out=1`, `pps=1`
- 두 target PHC 모두 `testptp` 기반 perout/PPS ioctl은 확인 가능했다.
- rootfs에는 `testptp`가 없지만, local kernel selftest source로 cross-build해 재사용 가능하다.
- 다만 현재 booted image 기준으로는 차이가 있다.
  - SK `/dev/ptp0`: capability는 있으나 output pin이 아직 `ECAP0`로 mux되어 있어 바로 외부 측정 불가
  - TMDS `/dev/ptp2`: IEP output candidate pinmux가 runtime에서 적용된 상태라 외부 측정 가능성이 높음
- 따라서 “하드웨어적으로 전기 신호 출력이 가능한지”에 대해서는 **가능성 있음**으로 판단하지만,
  “현재 이미지/배선만으로 즉시 scope 측정 가능한지”는 보드별로 다르다.

관련 상세 기록:

- `docs/2026-06-25_phc-external-pulse-runtime-check.md`

## 참고

아래 내용은 이번 정리 이전에 수행한 direct 검증 기록이다.
프로젝트의 최신 결론은 위 `최신 정리` 섹션을 우선 기준으로 본다.

## 검증 목적

이번 검증의 목적은 다음 세 가지를 실제 보드에서 확인하는 것이다.

1. `SK-AM64B eth1 <-> TMDS64EVM eth1` direct link가 gPTP 실험 경로로 안정적인지
2. `ptp4l`이 L2 + P2P + hardware timestamp 조건에서 실제 `MASTER/SLAVE`를 형성하는지
3. `phc2sys`로 SLAVE 보드의 `CLOCK_REALTIME`까지 동기화할 수 있는지

## 검증 구성

- direct link: `SK-AM64B eth1 <-> TMDS64EVM eth1`
- management SSH:
  - SK-AM64B: `root@192.168.0.110`
  - TMDS64EVM: `root@192.168.0.220`
- gPTP transport: L2
- delay mechanism: P2P
- timestamp: hardware
- `ptp4l` source interface: `eth1`
- `phc2sys` target: `CLOCK_REALTIME`

사용한 공통 설정 파일:

```text
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
```

## 사전 조건 확인 결과

| 항목 | SK-AM64B | TMDS64EVM |
|---|---|---|
| 관리 IP | `192.168.0.110` | `192.168.0.220` |
| 관리 interface | `eth0` | `eth0` |
| gPTP interface | `eth1` | `eth1` |
| eth1 link | up | 부팅 직후 down, `ip link set eth1 up` 후 up |
| speed/duplex | `1000Mb/s Full` | `1000Mb/s Full` |
| driver | `am65-cpsw-nuss` | `am65-cpsw-nuss` |
| PTP provider index | `0` | `0` |
| PHC device | `/dev/ptp0` | `/dev/ptp0` |
| hardware timestamp | 가능 | 가능 |

추가 관찰:

- SK-AM64B `eth1`는 자동으로 `169.254.x.x` link-local 주소를 받을 수 있다.
- TMDS64EVM `eth1`는 IP가 없어도 L2 gPTP 검증에는 문제가 없었다.

## ptp4l 결과

### 역할 형성

- `SK-AM64B`: MASTER
- `TMDS64EVM`: SLAVE

### 상태 전이

SK-AM64B:

```text
INITIALIZING -> LISTENING -> MASTER
new foreign master 70ff76.fffe.202299-1 관측
```

TMDS64EVM:

```text
INITIALIZING -> LISTENING -> MASTER -> UNCALIBRATED -> SLAVE
selected best master clock 70ff76.fffe.1ff287
```

의미:

- BMCA 기준으로 SK-AM64B clock이 최종 best master로 선택되었다.
- TMDS64EVM은 local grand master 역할을 버리고 정상적으로 slave 경로로 전환되었다.

### SLAVE offset / delay 안정화

TMDS64EVM `ptp4l`에서 확인한 대표 값:

```text
rms 94093  delay 426  freq +7638
rms 2222   delay 426  freq +6121
rms 952    delay 426  freq +8317
rms 136    delay 427  freq +8261
rms 11     delay 427  freq +8191
rms 7      delay 426  freq +8179
```

후속 재검증에서도 유사하게 안정화됨:

```text
rms 45  -> 36 -> 12 -> 5 -> 3 -> 7
delay 426~427 ns 유지
freq 약 +8.0k ppb 부근 유지
```

판단:

- TMDS64EVM는 SLAVE 상태를 유지했다.
- `master offset`은 초기 과도 상태 이후 빠르게 수렴했다.
- `path delay`는 약 `426~427 ns`로 안정적이었다.

## phc2sys 결과

### 초기 실패 원인

초기 `phc2sys` 실패는 TMDS64EVM 단독 문제가 아니었다.

확인 당시:

- SK-AM64B `CLOCK_REALTIME`: `2026-06-23 ...`
- SK-AM64B `PHC(/dev/ptp0)`: `Thu Jan 1 00:41:25 1970`
- TMDS64EVM `CLOCK_REALTIME`: `2026-06-23 ...`
- TMDS64EVM `PHC(/dev/ptp0)`: `Thu Jan 1 00:41:25 1970`

즉, MASTER와 SLAVE 모두 PHC epoch가 wall clock와 맞지 않았고,
특히 MASTER인 SK-AM64B의 PHC 기준이 잘못된 상태였다.

### 조치

SK-AM64B에서 다음 명령으로 PHC를 `CLOCK_REALTIME`에 맞췄다.

```bash
phc_ctl /dev/ptp0 set
```

확인 결과:

```text
before: Thu Jan 1 00:41:50 1970
after : Tue Jun 23 08:39:52 2026
```

### 재검증 결과

TMDS64EVM에서 `ptp4l`이 충분히 `SLAVE`로 안정화된 뒤,
다음 명령으로 system clock 동기화를 재검증했다.

```bash
phc2sys -s eth1 -c CLOCK_REALTIME -O 0 -m
```

대표 로그:

```text
CLOCK_REALTIME phc offset -2633856240
CLOCK_REALTIME phc offset -2745029931
CLOCK_REALTIME phc offset     195367
CLOCK_REALTIME phc offset      64394
CLOCK_REALTIME phc offset    -139785
CLOCK_REALTIME phc offset    -212483
```

실행 전후 비교:

```text
before: offset from CLOCK_REALTIME is -2521399878ns
after : offset from CLOCK_REALTIME is -211734ns
```

판단:

- `phc2sys` 재검증은 성공했다.
- TMDS64EVM `CLOCK_REALTIME`는 최종적으로 PHC와 약 `-0.21 ms` 수준까지 근접했다.
- 이번 구성에서는 `ptp4l` 안정화 후 `phc2sys -O 0`가 재현성 있는 절차였다.

## tcpdump 결과

`tcpdump -i eth1 -e -nn ether proto 0x88f7`에서 다음 프레임을 확인했다.

- `Announce`
- `Sync`
- `Follow_Up`
- `Pdelay_Req`
- `Pdelay_Resp`
- `Pdelay_Resp_Follow_Up`

의미:

- gPTP가 UDP/IP가 아니라 실제 Ethernet L2 (`0x88f7`) 기준으로 송수신되고 있음을 확인했다.
- P2P delay measurement와 BMCA 관련 프레임이 모두 direct link 상에서 관찰되었다.

## 최종 판정

### 성공한 항목

1. `SK-AM64B eth1`와 `TMDS64EVM eth1` 모두 `1000Mb/s Full` link 유지 확인
2. 양쪽 `eth1`에서 hardware timestamp 가능 확인
3. L2 gPTP 설정으로 `ptp4l` 실행 가능 확인
4. `SK-AM64B = MASTER`, `TMDS64EVM = SLAVE` 상태 형성 확인
5. TMDS64EVM `master offset` 및 `path delay` 안정화 확인
6. `phc2sys`로 TMDS64EVM `CLOCK_REALTIME` 동기화 재검증 성공
7. `tcpdump`에서 `ether proto 0x88f7` PTP frame 확인

### 현재 결론

이번 세션 기준으로

```text
SK-AM64B ↔ TMDS64EVM CPSW 기반 gPTP 1차 검증 완료
```

로 판정한다.

## 후속 메모

- TMDS64EVM은 실험 시작 전 `ip link set eth1 up` 여부를 항상 확인한다.
- MASTER 역할을 맡는 보드에서는 `phc_ctl /dev/ptp0 get`으로 PHC epoch를 먼저 점검한다.
- 필요하면 이 절차를 host helper script 또는 board-side helper로 승격할 수 있다.
