# P2-Q3 다중 Class Window 검증 계획

## 목적

P2의 Qbv 검증에서 physical link 1 Gbit/s full-load를 전제로 하지 않는다. 대신 각
traffic class의 open window가 제공하는 service capacity보다 해당 class의 offered load가
큰 조건을 만든다. 이 조건이면 전체 link가 유휴여도 low-priority queue backlog와 class
isolation을 검증할 수 있다.

## 채택 Schedule

cycle은 1 ms이며, 한 순간에는 한 TC만 연다.

```text
TC2: gate 0x4, 500 us, service capacity 500 Mbit/s
TC1: gate 0x2, 250 us, service capacity 250 Mbit/s
TC0: gate 0x1, 250 us, service capacity 250 Mbit/s
```

TC2는 검증 PTP event traffic, TC1은 same-port gPTP, TC0는 UDP background다. SK의
active mapping은 `map 0 0 1 2 ...`이며, 다음의 socket priority가 TC를 선택한다.

```text
TC0: UDP default priority 0
TC1: gPTP socket_priority 2
TC2: P2 critical SO_PRIORITY 3, wire PCP 2
```

SK `eth0.311`에서 priority 2의 VLAN egress PCP는 6이고, TC2 P2 raw frame의 wire PCP는
2다. 따라서 wire PCP 값과 taprio TC 선택은 같은 값이라고 가정하지 않는다.

## Load Contract

background는 `iperf3` UDP 500 Mbit/s request를 사용한다. 단일 userspace generator가
exact 500 Mbit/s를 만들지 않아도, source offered rate가 TC0 capacity 250 Mbit/s의 110%
초과이면 충분하다. receiver achieved rate는 TC0 250 Mbit/s capacity 부근이어야 하며,
SK `parent 100:1` PFIFO drop 증가가 persistent TC0 backlog의 직접 증적이다.

critical traffic은 기존 P2 contract를 유지한다.

```text
PTPv2 L2 Sync domain 127
128 B, VLAN 311, wire PCP 2, SO_PRIORITY 3
1 ms period, TX/RX raw-HW timestamp
```

critical frame은 target TC2 window의 450 us 전에 enqueue한다. 이전 cycle의 TC1 slot에서
enqueue되므로 TC2 gate가 닫힌 상태이며, 다음 cycle TC2 open edge에서 release된다.

## Pilot Validity Gate

1. SK TX와 TMDS RX raw-HW count가 sample count와 일치한다.
2. 모든 critical TX raw-HW phase가 TC2의 `0 <= phase < 500 us`에 있다.
3. critical release-delay p99가 500 us 미만이다.
4. source background rate가 TC0 allocation 250 Mbit/s 초과다.
5. TMDS background receive rate가 200 Mbit/s 초과다.
6. SK TC0 queue drop delta가 양수다.
7. TMDS gPTP port state가 종료 시점에 `SLAVE`다.

이 검증은 full line-rate certificate가 아니라, low-priority class가 자기 gate capacity를
초과한 backlog 상태에서 TC2 scheduled service가 유지되는지 확인하는 Qbv evidence다.

## 실행

```bash
python3 projects/am64x-tsn-quant-validation/tools/p2_qbv_multiclass_pilot.py
```

runner는 pilot 종료 또는 실패 시 SK `eth0`을 1 ms all-open `0x7` taprio schedule로
복구한다.

## Formal Campaign Contract

Formal P2 result는 동일 조건의 5 runs x 300 s다. 각 run은 Pilot Validity Gate를 모두
통과해야 하며, 한 run이라도 실패하면 campaign 전체를 PASS로 선언하지 않는다.

```bash
python3 projects/am64x-tsn-quant-validation/tools/p2_qbv_multiclass_campaign.py
```

## Pilot 결과

유효 pilot은 `artifacts/p2-qbv-multiclass-pilot-20260728-170652-kst/`에 보관했다.

| 항목 | 결과 |
|---|---:|
| critical SK TX raw-HW | 60,000 / 60,000 |
| critical TMDS RX raw-HW | 60,000 / 60,000 |
| critical TX phase min / p99 / max | 0.370 / 9.426 / 271.778 us |
| critical release-delay p99 | 10.642 us |
| TC0 source offered rate | 308.394 Mbit/s |
| TC0 TMDS receive rate | 243.300 Mbit/s |
| SK TC0 PFIFO drop delta | 375,784 packet |
| TMDS gPTP 종료 상태 | `SLAVE` |

TC0 source offered rate는 250 Mbit/s allocation보다 23.4% 높다. 동시에 receiver rate는
250 Mbit/s allocation 부근이고 PFIFO drop이 증가했으므로, 이 pilot은 TC0가 지속 backlog인
조건을 만들었다. 그 상태에서 TC2 critical raw-HW phase가 500 us TC2 window 안에 남았고,
release-delay p99도 500 us validity gate를 통과했다.

유효 pilot 종료 후 SK는 `0x7 1000000 ns`, `flags 0x2` all-open schedule로 복구됐고, SK는
`MASTER`, TMDS는 `SLAVE` 상태를 유지했다.

## Formal Campaign 결과

`artifacts/qbv-multiclass-01-20260728-175056-kst/`의 5 runs x 300 s formal campaign은
모든 run이 PASS했다. `campaign-status.json`은 `passed`이며 aggregate summary는
`campaign-summary.json`에 보관한다.

| 항목 | 5-run 결과 |
|---|---:|
| critical SK TX raw-HW / TMDS RX raw-HW | 각 run `300,000 / 300,000` |
| critical raw-HW total | `1,500,000 / 1,500,000` |
| critical TX phase p99 | 각 run `9.426 us` |
| critical TX phase max | `240.042~448.146 us` |
| critical release-delay p99 | `9.426~10.642 us` |
| TC0 source offered rate | `274.359~280.795 Mbit/s` |
| TC0 TMDS receive rate | `242.297~243.291 Mbit/s` |
| SK TC0 PFIFO drop delta | run당 `805,908~974,820`, 합계 `4,503,840` packet |
| TMDS gPTP 종료 상태 | 모든 run `SLAVE` |

TC0 source offered rate는 모든 run에서 250 Mbit/s allocation을 초과했고 TC0 drop도 양수다.
따라서 background queue가 지속 backlog인 상태가 실제로 성립했다. 그 상태에서 모든 critical
TX raw-HW phase가 TC2 500 us window에 남았으므로 `QBV_MULTICLASS_01`은 PASS다.

run-03은 sender와 receiver가 target에서 정상 종료한 뒤 UART daemon host route가 일시적으로
끊겨 status polling과 automatic collection이 실패했다. SK/TMDS remote run state, raw-HW
CSV, TMDS 종료 gPTP snapshot을 management SSH로 회수한 뒤 같은 validity gate를 재실행해
PASS를 확인했다. 이후 UART route 복구 후 run-04/run-05는 정상 UART orchestration으로
완료했다.

이 PASS는 lower-class allocation overflow 아래 TC2 window service의 반복 증적이다. all-open
OFF 대비 latency improvement, 1 Gbit/s full-load protection, hard real-time deadline 또는
zero-miss 보장은 주장하지 않는다.
