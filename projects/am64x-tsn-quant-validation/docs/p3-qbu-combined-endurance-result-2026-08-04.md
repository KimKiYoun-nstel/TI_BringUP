# P3 Qbu/IET Combined Condition Endurance 결과

## 실행 정보

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_COMBINED_ENDURANCE_01` |
| Raw artifact | `artifacts/p3-qbu-combined-endurance-20260804-kst` |
| Session | independent reboot 후 SK boot ID `02b6264d-7032-4c1b-9cb7-6df5528f5600`, TMDS boot ID `5269e612-0108-4e10-975b-7e5dbecd37d1` |
| Intended on profile | preemptible UDP 5002 CPU0, express UDP 5003 CPU1, 50M/50M, 1472 B, pacing 100 us |
| Acceptance | every on run `active`, both flow loss 0, assembly/SMD error 0 |

## 결과

off control 30 s는 `control-pass`였다. 첫 300 s on run은 measurement validity, link, peer,
MM verification, filter/hardware class-hit, Qbu counter causality를 모두 통과했지만
`classification: degraded`였다.

| 항목 | 값 |
|---|---:|
| Preemptible lost packets | 10 |
| Express lost packets | 0 |
| Preemptible/express achieved rate | 49.9998 / 49.9997 Mbit/s |
| Sender fragment / receiver fragment / assembly OK delta | 1,005,769 / 1,005,769 / 1,005,769 |
| Receiver assembly/SMD error | 0 / 0 |
| SK CPSW RX drop/CRC error | 0 / 0 |

## Acceptance Gate

`run_acceptance` gate가 packet loss를 검출해 campaign은 completed run 2 (off control 1 + on 1)에서
즉시 `failed`로 종료했다. 예정한 on 10회는 실행하지 않았다. 이는 harness failure가 아니라
measurement acceptance failure다.

## CPU/IRQ/Softirq Evidence

| Evidence | CPU0 delta | CPU1 delta |
|---|---:|---:|
| CPSW `tx2` IRQ, preemptible queue | 1,273,795 | 0 |
| CPSW `tx3` IRQ, express queue | 0 | 1,273,797 |
| `NET_RX` softirq | 1,273,843 | 1,273,797 |

SK는 CPU1이 offline인 topology이며, CPSW `rx0` IRQ는 `+1,289,764`, `NET_RX` softirq는
CPU0에서 `+1,282,387` 증가했다. receiver hardware counter에는 RX FIFO/ALE drop, CRC,
MAC Merge assembly/SMD error가 없다.

따라서 이번 10-packet preemptible loss는 TX queue CPU migration이나 눈에 보이는 CPSW
PHY/MAC/MM hardware error로 설명되지 않는다. userspace UDP sequence 관측과 hardware counter
사이의 location을 확정하려면 NAPI/socket receive queue/scheduler wakeup evidence가 추가로 필요하다.

## 결론

- 이 profile은 deterministic diagnostic condition도, production loss-free profile도 아니다.
- P3 production acceptance는 거절 상태를 유지한다.
- 다음 원인분리는 rate matrix 반복이 아니라 SK receiver single-CPU NAPI/socket pressure와 sender
  queue-service timing을 구분하는 telemetry-first design으로 진행해야 한다.
