# 2026-06-30 Phase B Endpoint Egress Qbv Timing Validation Progress

## 1. 범위

- 프로젝트: `projects/tsn_qbv`
- 검증 경로: `SK eth0(CPSW sender) -> TMDS eth1(CPSW receiver)`
- 모드: `switch_mode=false` direct endpoint path
- 제외: `switch_mode=true` TSN switch / time-aware bridge 검증

이번 기록은 Phase B 진행 정리다.

- `B0`, `B1`, `B3`, `B6`는 현재 기준으로 실질 검증 완료
- `B2`는 single-flow timing 기준으로 근거 확보
- `B4`, `B5`는 시도 완료
- 그러나 현재 두 보드/현재 계측 경로 기준으로는 closeout용 strong proof를 확보하지 못했다.

## 2. 이번 실행에서 바로 수정한 공통 함정

### 2.1 VLAN IP drift 재발

- SK `eth0.311`가 다시 `169.254.x.x`로 drift하는 경우가 재발했다.
- 각 run 시작 전 `ip addr flush` 후 `10.31.1.1/24`, `10.31.1.2/24`를 다시 강제로 넣어 해결했다.

### 2.2 CPSW EST cycle 변경 시 `replace` 불안정

- `500 us -> 8 ms`로 바로 `tc qdisc replace ... flags 2`를 넣으면 다음 오류가 재현되었다.

```text
Error: ti_am65_cpsw_nuss: Can't toggle estf timer, stop taprio first.
```

- 따라서 cycle 변경 시에는 다음 순서를 기준으로 삼았다.

```text
tc qdisc del dev eth0 root
tc qdisc add dev eth0 root ... taprio ... flags 2
```

### 2.3 Phase B 문서의 기본 filter/egress-map 조합 수정 필요

기존 문서의 다음 조합은 Phase B timing 검증과 맞지 않았다.

- `taprio map 0 0 1 2 ...`
- `5001 -> skbedit priority 7`
- `5002 -> skbedit priority 6`

이 조합에서는 두 flow가 기대한 `TC2`/`TC1`로 안정적으로 분리되지 않고, child queue 사용량이 한 queue로 몰리는 흔적이 보였다.

실행 중에는 아래 조합으로 교정했다.

- `5001 -> skbedit priority 3`
- `5002 -> skbedit priority 2`
- `eth0.311 egress-qos-map`: `2:6 3:7`

즉 internal priority는 `taprio map`에 맞춰 `2/3`을 쓰고, wire PCP는 VLAN egress map으로 `6/7`을 유지했다.

### 2.4 receiver timing capture는 `eth1.311` 기준이 더 안정적

- lower device `eth1`에서 VLAN offload/raw capture를 그대로 보면 Phase B timing용 timestamp/text capture가 불안정했다.
- 이번 진행에서는 다음처럼 역할을 나눠서 사용했다.

```text
wire PCP 확인: 필요 시 lower dev `eth1`
timing capture: `eth1.311`
```

### 2.5 TMDS `/tmp` full

- 이전 pcap 잔재로 TMDS `/tmp`가 `100%`까지 차서 `ptp4l` log 생성이 실패했다.
- `phaseB_*` 임시 파일을 정리한 뒤 B6를 재시도했다.

## 3. B0 결과

목적:

- `500 us` hardware `taprio(flags 2)` replay sanity

결과:

- `flags 0x2` 확인
- `cycle-time 500000` 확인
- `No fetch RAM error` 없음
- TMDS wire capture에서 `p7`, `p6` 확인

요약 수치:

```text
p7 count = 8635
p6 count = 8598
```

판정:

- `B0` 통과

## 4. B1 결과

### 4.1 500 us

- accepted
- `flags 0x2` 확인

### 4.2 8 ms

- 기존 `taprio`가 올라간 상태에서 바로 `replace`하면 실패
- `tc qdisc del dev eth0 root` 후 `add`하면 accepted
- `flags 0x2`, `cycle-time 8000000` 확인

판정:

- `500 us`, `8 ms` 두 cycle 모두 accepted
- 단, CPSW EST cycle 전환은 `del -> add` 절차가 필요

## 5. B2 진행 결과

## 5.1 single-flow timing 기준

이번 세션에서는 먼저 single-flow로 cycle 반복성을 확인했다.

### 500 us / p7-only

```text
packets = 49819
burst delta average ~= 0.000505 s
```

### 500 us / p6-only

```text
packets = 50226
burst delta average ~= 0.000855 s
대표 delta 다수는 ~0.0005 s 부근
```

### 8 ms / p7-only

```text
packets = 62401
burst delta average ~= 0.00864 s
대표 delta 다수는 ~0.00799 ~ 0.00801 s
```

### 8 ms / p6-only

```text
packets = 62355
burst delta average ~= 0.00879 s
대표 delta 다수는 ~0.00799 ~ 0.00803 s
```

판정:

- `500 us`, `8 ms` 모두 single-flow timing 반복성은 확보되었다.
- 즉 endpoint egress timing behavior가 configured cycle과 상관관계를 가진다는 근거는 생겼다.

## 5.2 dual-flow timing

- dual-flow를 바로 걸면 capture 해석이 더 민감했다.
- `80 Mbit/s + 80 Mbit/s`는 queue backlog가 충분하지 않아 group separation이 약했다.
- 이후 `300 Mbit/s`급 offered load와 `eth1.311` capture, control-less sender로 single-flow baseline을 먼저 고정했다.

현재 판정:

- B2는 single-flow 기준 근거 확보
- dual-flow grouped pattern은 추가 정교화 여지 있음

## 6. B3 결과

gate-close stress는 single-flow high-offer load 기준으로 확인했다.

## 6.1 8 ms / p7-only

```text
sender bytes = 136024576
receiver approx ~= 182.95 Mbps
burst delta average ~= 0.00922 s
qdisc requeues = 509
```

## 6.2 8 ms / p6-only

```text
sender bytes = 136444096
receiver approx ~= 175.75 Mbps
burst delta average ~= 0.00925 s
qdisc requeues = 505
```

## 6.3 500 us / p7-only

```text
sender bytes = 132875968
receiver approx ~= 154.18 Mbps
burst delta average ~= 0.000864 s
```

## 6.4 500 us / p6-only

```text
sender bytes = 133726784
receiver approx ~= 115.33 Mbps
burst delta average ~= 0.001153 s
```

판정:

- 두 cycle 모두에서 unrestricted sender rate보다 receiver 평균 처리율이 낮아졌다.
- `8 ms`에서는 qdisc `requeues`도 명확히 증가했다.
- 즉 gate-close에 따른 제한 효과는 `500 us`, `8 ms` 모두에서 확인되었다.

## 7. B4 결과

이번 세션의 최종 B4는 `500 us` cycle, `300 Mbps per flow` paced dual-flow 기준으로 정리한다.

핵심 전제는 다음과 같이 유지했다.

```text
UDP 5001 -> skb priority 3 -> TC2 -> gate 0x04 -> wire PCP 7
UDP 5002 -> skb priority 2 -> TC1 -> gate 0x02 -> wire PCP 6
```

분석 방법:

- receiver timing capture는 `TMDS eth1.311`
- capture 시작점을 cycle boundary로 가정하지 않음
- offset `0 us .. 499 us` sweep
- packet phase는 `(timestamp - offset) % 500 us`
- best offset은 `5001 in-window ratio + 5002 in-window ratio` 최대값 기준

선정 load:

- `200M`, `300M`, `400M`을 비교했고, `300M per flow`가 세 후보 중 가장 조금 더 나은 분리 지표를 보였다.

### 7.1 Schedule A

```text
0x04 125 us
0x02 125 us
0x01 250 us
```

결과:

```text
best offset = 6 us
5001 median phase = 125 us
5002 median phase = 127 us
5001 in-window ratio = 0.4988
5002 in-window ratio = 0.3245
leakage ratio = 0.5889
```

### 7.2 Schedule B

```text
0x02 125 us
0x04 125 us
0x01 250 us
```

결과:

```text
best offset = 1 us
5001 median phase = 120 us
5002 median phase = 120 us
5001 in-window ratio = 0.3034
5002 in-window ratio = 0.5223
leakage ratio = 0.5873
```

### 7.3 해석

- `Schedule A`에서는 `5001`의 in-window ratio가 `5002`보다 높았다.
- `Schedule B`에서는 반대로 `5002`의 in-window ratio가 `5001`보다 높아졌다.
- 즉 schedule inversion에 따라 dominant in-window flow가 뒤집히는 방향성은 확인되었다.

하지만 다음 한계가 남았다.

- `5001`과 `5002`의 median phase가 기대만큼 clean하게 분리되지 않았다.
- leakage ratio가 약 `0.59` 수준으로 높다.
- 따라서 `5001 first window`, `5002 second window`의 strong causality proof로 closeout 하기는 어렵다.

판정:

- `B4 = partial`
- schedule inversion의 방향성은 보였지만, strong causality proof는 아직 부족
- 현재 구성 기준으로는 Phase B closeout 근거로 사용 불가

### 7.4 1 ms retry

사용자 질의 이후 `500 us` 대신 `1 ms` cycle로도 B4를 다시 시도했다.

이번에는 계측을 한 단계 더 강화했다.

- dual-flow offset sweep만 보지 않고
- single-flow (`p7-only`, `p6-only`)를 먼저 따로 캡처해서
- receiver-side phase histogram 기준 `250 us` 폭 최적 window를 찾고
- 그 뒤 dual-flow inversion 수치와 비교했다.

조건:

```text
Schedule A:
0x04 250 us
0x02 250 us
0x01 500 us

Schedule B:
0x02 250 us
0x04 250 us
0x01 500 us
```

offered load 후보는 `200M`, `300M`, `400M per flow`를 비교했고, 이 세션에서는 `200M per flow`가 상대적으로 가장 나았다.

#### 1 ms / Schedule A / 200M per flow

```text
best offset = 932 us
5001 median phase = 305 us
5002 median phase = 296 us
5001 in-window ratio = 0.3951
5002 in-window ratio = 0.4274
leakage ratio = 0.5890
```

#### 1 ms / Schedule B / 200M per flow

```text
best offset = 972 us
5001 median phase = 283 us
5002 median phase = 284 us
5001 in-window ratio = 0.4290
5002 in-window ratio = 0.4398
leakage ratio = 0.5655
```

해석:

- `1 ms`로 바꿔도 두 flow의 median phase가 clean하게 갈라지지 않았다.
- in-window ratio도 `Schedule A/B`에 따라 strong inversion을 보여줄 정도로 충분히 분리되지 않았다.
- leakage ratio도 여전히 높다.

즉 `1 ms`는 `500 us`보다 설명하기는 조금 쉬울 수 있지만, 이번 구성에서는 `B4`를 closeout할 정도의 strong causality를 만들지는 못했다.

### 7.5 single-flow calibrated window check

`1 ms`, `300M single-flow` 기준으로 receiver-side phase histogram에서 `250 us` 최적 window를 찾은 결과는 다음과 같다.

#### Schedule A

```text
A_p7:
best window start = 518 us
in-window ratio = 0.4601
median phase = 271 us

A_p6:
best window start = 963 us
in-window ratio = 0.4345
median phase = 283 us
```

#### Schedule B

```text
B_p7:
best window start = 732 us
in-window ratio = 0.4304
median phase = 296 us

B_p6:
best window start = 699 us
in-window ratio = 0.4538
median phase = 274 us
```

해석:

- receiver-side phase histogram에서 window 위치가 schedule 변화에 따라 clean하게 `250 us` 단위로 이동하지 않았다.
- 특히 `A_p7/A_p6`, `B_p7/B_p6`의 calibrated window start 자체가 기대만큼 안정적으로 갈라지지 않았다.
- 즉 dual-flow parser의 한계만이 아니라, 현재 receiver-side 계측 자체가 `B4 strong`에 필요한 clean phase separation을 충분히 보여주지 못하고 있다고 봐야 한다.

### 7.6 sender-side tx timestamp probe 시도

receiver-side capture 한계를 줄이기 위해 `projects/tsn_qbv/tools/tx_hwts_probe.py`를 추가하고, SK에서 sender-side timestamp 기반 계측도 시도했다.

목표:

- `eth0` TX timestamp를 user-space에서 직접 읽기
- 가능하면 PHC 기준 egress phase로 `B4`, `B5`를 재판정하기

관찰된 사실:

- socket timestamp path 자체는 열렸다.
- 그러나 이번 환경에서 probe가 받은 timestamp source는 `raw_hw` 또는 `hw`가 아니라 `sw`였다.
- probe는 `phc_device=/dev/ptp0` 기준으로 realtime -> PHC offset을 샘플링해서 `sw` timestamp를 PHC domain으로 환산했다.

#### sender-side B4 / 1 ms / Schedule A

조건:

- background flood: `300M per flow`
- traced probe: `1M per flow`
- windows:
  - `5001:0:250000`
  - `5002:250000:250000`

결과:

```text
best offset = 459000 ns
5001 in-window ratio = 0.2314
5002 in-window ratio = 0.4000
5001 median phase = 438259 ns
5002 median phase = 441170 ns
leakage ratio = 0.6843
timestamp source = sw
```

#### sender-side B4 / 1 ms / Schedule B

조건:

- background flood: `300M per flow`
- traced probe: `1M per flow`
- windows:
  - `5001:250000:250000`
  - `5002:0:250000`

결과:

```text
best offset = 851000 ns
5001 in-window ratio = 0.2314
5002 in-window ratio = 0.4510
5001 median phase = 425892 ns
5002 median phase = 306418 ns
leakage ratio = 0.6588
timestamp source = sw
```

해석:

- sender-side 계측으로도 `5002` 쪽 우세 변화는 보였지만,
- `5001`은 Schedule A/B에서 충분히 강하게 뒤집히지 않았고,
- leakage 역시 높았다.

즉 sender-side probe를 추가해도 현재 구성에서는 `B4 strong`으로 closeout할 수준의 clean causality는 확보되지 않았다.

## 8. B5 결과

future `base-time` 자체는 accepted 되었고, `tc qdisc show`에도 configured 값이 그대로 보였다.

이번 세션의 최종 비교는 사용자 지시에 맞춰 `+5 s`, `+10 s` 두 run을 기준으로 정리한다.

검증 조건:

- `8 ms` schedule
- `p7-only` traffic
- `base-time = PHC now + 5 s`
- `base-time = PHC now + 10 s`

### 8.1 +5 s run

```text
PHC device = /dev/ptp0
PHC now = 94101.481924290
configured base-time = 94106817622482
taprio apply PHC time = 94102.025023738
traffic start sys time = 1782561929.232818139
receiver first packet after capture = 1.7219401249894872 s
receiver first large-gap transition = 1.728247366991127 s
```

### 8.2 +10 s run

```text
PHC device = /dev/ptp0
PHC now = 94132.749784866
configured base-time = 94143087554906
taprio apply PHC time = 94133.259681434
traffic start sys time = 1782561960.453305535
receiver first packet after capture = 1.5780941170087317 s
receiver first large-gap transition = 1.5870702259999234 s
```

### 8.3 해석

- `future base-time accepted`는 재확인되었다.
- 그러나 `+10 s`가 `+5 s`보다 first packet 또는 first transition을 약 `5 s` 더 늦추는 현상은 보이지 않았다.
- 오히려 현재 capture 기준에서는 두 run 모두 약 `1.6 ~ 1.7 s` 부근에서 유사한 transition이 먼저 보였다.

중요한 분류:

- 이 문제는 현재로서는 `sender/receiver app 또는 daemon 성능 부족`으로 보지 않는다.
- 더 핵심적인 제약은 `검증 환경의 timebase observability`다.

현재 구조에서는 다음이 분리되어 있다.

```text
taprio base-time 기준: sender PHC (/dev/ptp0)
관측 기준: receiver tcpdump timestamp / receiver local clock
```

즉 future `base-time`이 sender PHC 기준으로 실제 적용되더라도, receiver capture만으로는 그 phase shift를 직접 증명하기 어렵다.

따라서 `B5`가 partial인 주된 이유는 성능 부족보다는 다음 쪽에 가깝다.

```text
검증 환경 구성/계측 기준의 제약
```

즉 이번 방법으로는 다음을 증명하지 못했다.

```text
future base-time 증가분이 receiver 관측 phase/start timing을 예측 가능하게 민다.
```

판정:

- `B5 = partial`
- `future base-time accepted`는 성립
- `future base-time phase proof`는 아직 미확보
- 현재 구성 기준으로는 Phase B closeout 근거로 사용 불가

### 8.4 sender-side tx timestamp probe 시도

future `base-time`을 sender-side에서 직접 확인하려고 같은 probe를 사용했다.

#### +5 s run

```text
configured base-time = 106401778103754
first_tx_hw_ns = 106397708379697
timestamp source = sw
```

#### +10 s run

```text
configured base-time = 106427878406602
first_tx_hw_ns = 106418725340808
timestamp source = sw
```

해석:

- sender-side probe에서도 future `base-time`보다 훨씬 이른 시점에 timestamped send가 먼저 잡혔다.
- 그리고 이 probe의 timestamp source가 `raw_hw`가 아니라 `sw`였다.
- 즉 현재 socket timestamp path에서 직접 얻는 값만으로는 `taprio base-time(PHC 기준)`가 만든 실제 egress start/phase를 strong하게 증명할 수 없다.

중요한 현재 blocker는 다음이다.

```text
현재 두 보드 환경에서 user-space probe는 동작하지만,
현재 확인된 timestamp source는 software tx timestamp이며,
PHC raw hardware tx timestamp를 직접 확보하지 못했다.
```

따라서 `B5`가 partial인 이유는 단순 receiver tcpdump 한계만이 아니라,
현재 user-space timestamp 경로가 PHC raw egress 기준을 직접 주지 못한다는 점까지 포함한다.

## 9. B6 결과

safe schedule은 `TC0 always-open` 구조로 확인했다.

### 9.1 8 ms safe schedule

```text
0x5 4000000
0x3 4000000
```

결과:

- TMDS `eth1`: `MASTER -> UNCALIBRATED -> SLAVE`
- `FAULTY`, `tx timestamp timeout`, `send peer delay request failed` 없음
- SK는 `MASTER` 유지
- traffic 유지

### 9.2 500 us safe schedule

```text
0x5 250000
0x3 250000
```

결과:

- TMDS `eth1`: `MASTER -> UNCALIBRATED -> SLAVE`
- failure signature 없음
- SK는 `MASTER` 유지
- traffic 유지

판정:

- `500 us`, `8 ms` safe schedule 모두에서 endpoint path hardware taprio + gPTP coexistence 성립

## 10. 현재 종합 판정

현재까지 Phase B의 상태는 다음과 같다.

- `B0`: 완료
- `B1`: 완료
- `B2`: single-flow timing 기준으로 실질 근거 확보
- `B3`: 완료
- `B4`: 미완, 여러 계측 강화 후에도 strong causality proof 미확보
- `B5`: 미완, accepted는 확인했지만 PHC phase proof 미확보
- `B6`: 완료

즉 현재까지는 다음 주장이 가능하다.

```text
SK eth0 -> TMDS eth1 direct path에서
AM64x CPSW endpoint hardware Qbv/EST는
500 us와 8 ms 두 cycle 모두에서
- offload apply
- cycle-correlated single-flow timing
- gate-close stress effect
- gPTP coexistence
를 재현했다.
```

하지만 아직 다음은 강하게 말하지 않는다.

```text
schedule inversion causality가 fully proven 되었다.
future base-time phase shift가 fully proven 되었다.
```

따라서 현재 구성/현재 계측 경로 기준의 최종 실무 판정은 다음과 같다.

```text
Phase B closeout 보류.

이유:
- B4 schedule inversion causality를 closeout 수준으로 증명하지 못했다.
- B5 future base-time phase proof를 closeout 수준으로 증명하지 못했다.
```

## 11. 다음 항목

우선순위는 다음과 같다.

1. 현재 상태 기준의 partial closeout / follow-up split 초안 작성
2. 필요 시 sender-side timestamp source를 `raw_hw`로 확보할 수 있는 추가 경로가 있는지 별도 조사
