# P3 Qbu/IET Loss Location and Fragment Boundary 결과

## 범위

independent boot에서 combined CPU/pacing condition의 endurance acceptance가 실패한 뒤,
50M/50M Qbu on loss의 location을 userspace UDP receive path와 MAC Merge SMD path로 분리했다.
모든 on run은 TMDS UDP 5002 CPU0, UDP 5003 CPU1, 1472 B, 300 s이며 activation counter
causality를 요구했다.

## Receiver UDP Queue

default SK receive buffer 229376 B의 combined telemetry run에서는 degraded run에 SK UDP
`InErrors`와 `RcvbufErrors`가 각각 `+2` 증가했고 preemptible loss 2, express loss 9가 함께
발생했다. SK softnet dropped/time-squeeze는 증가하지 않았고 CPSW RX FIFO/ALE/CRC/MM assembly
error도 0이었다.

SK `net.core.rmem_default`를 test 동안만 1048576 B로 올리고 cleanup/reset에서 229376 B로
복구한 A/B에서는 server `rcvbuf_actual: 1048576`을 확인했다. 세 on run 모두 UDP
`InErrors`/`RcvbufErrors` delta와 preemptible loss가 0이었다. 따라서 receiver UDP socket
buffer overflow는 관측된 preemptible loss의 직접 원인 중 하나다.

그러나 같은 A/B에서 express loss는 0/2/4, receiver SMD error는 0/2/4로 남았다. 이 loss는
receiver UDP buffer overflow가 아닌 MAC Merge SMD path와 동반된다.

## Sender/Fragment A/B

| Condition | Classification | Preemptible loss max | Express loss max | SMD error max | 판정 |
|---|---|---:|---:|---:|---|
| 50M/50M, 100 us, fragment 124, rmem 1 MiB | `active` 1, `degraded` 2 | 0 | 4 | 4 | receiver overflow 제거 후 express/SMD 잔존 |
| 20M/50M, 100 us, fragment 124, rmem 1 MiB | `active` 2, `degraded` 1 | 11 | 927 | 877 | preemptible rate 감소가 해결책 아님 |
| 50M/50M, 10 us, fragment 124, rmem 1 MiB | `degraded` 3 | 2 | 63 | 59 | 더 짧은 pacing은 악화 |
| 50M/50M, 100 us, fragment 188, rmem 1 MiB | `active` 2, `degraded` 1 | 0 | 5 | 4 | 124보다 일부 개선, deterministic 아님 |
| 50M/50M, 100 us, fragment 252, rmem 1 MiB | `active` 1, `degraded` 2 | 0 | 21 | 19 | 188보다 악화 |

CPSW ethtool MM implementation은 sender `tx-min-frag-size`에 60, 124, 188, 252만 허용한다.
188 B는 현재 표본에서 가장 낮은 SMD/express-loss boundary 후보지만 한 300 s run에서 express
loss 5/SMD 4가 발생했으므로 candidate acceptance를 받지 못한다.

## Control Interpretation

IET-off control은 MAC Merge fragment/reassembly counter zero를 확인하는 negative control로는
유효하지만, current queue configuration에서 preemptible/express traffic loss가 큰
`control-degraded`가 반복됐다. 따라서 IET-off offered-rate performance를 IET-on loss의 direct
baseline으로 해석하지 않는다. on-case의 hardware class-hit, Qbu counters, MM state, UDP MIB,
CPSW/softirq evidence를 원인분리 기준으로 사용한다.

## Current Decision

1. SK receiver UDP socket buffer 1 MiB runtime setting은 future P3 diagnostic run에서 유지한다.
   persistent sysctl/rootfs 변경은 하지 않는다.
2. Sender pacing 10 us, preemptible 20M, fragment 252는 loss-free solution이 아니다.
3. Fragment 188은 추가 driver-level queue/IRQ service telemetry가 준비된 뒤에만 재검증한다.
4. P3에는 production loss-free Qbu profile이 없다. 다음 원인분리는 repeat rate sweep이 아니라
   CPSW queue service/NAPI/IRQ dispatch와 MAC Merge SMD error timing correlation을 수집하는
   instrumentation-first run이어야 한다.

## Harness Changes Validated







- target snapshot: CPU online, CPSW TX2/TX3/RX0 IRQ, softirq, UDP MIB, softnet statistics
- SK receiver `rmem_default` runtime override and cleanup/reset restoration
- UART stage/control, UART-discovered TMDS `eth0` DHCP address before bounded SSH artifact transfer
- UDP listener readiness barrier through `/proc/net/udp`

## Related Artifacts

- `artifacts/p3-qbu-combined-telemetry-20260804-kst`
- `artifacts/p3-qbu-receiver-rcvbuf-20260804-retry2-kst`
- `artifacts/p3-qbu-preemptible-intensity-20260804-kst`
- `artifacts/p3-qbu-pacing-10us-20260804-kst`
- `artifacts/p3-qbu-frag188-20260804-kst`
- `artifacts/p3-qbu-frag252-20260804-kst`
