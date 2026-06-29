# 2026-06-26 Phase 2 CBS Validation

## 목적

Phase 2 목표는 `mqprio`로 분리된 traffic class 위에 `CBS`를 적용해,
queue/class 단위 shaping이 실제 throughput 변화로 이어지는지 확인하는 것이다.

## 시작 live 상태

Phase 1에서 확인한 reusable live 상태를 그대로 사용했다.

- TMDS `ep1` receiver 유지
- TMDS `ep2` endpoint 유지
- SK `br-tsn.301 = 10.31.0.3/24` sender 유지
- SK `eth0` egress에 Phase 2용 `mqprio map` 적용:

```text
2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
```

의도:

- `p7 -> TC0 -> class 100:1`
- `p6 -> TC1 -> class 100:2`
- `p0 -> TC2 -> class 100:3`

## sender marking

`br-tsn.301`에서 유지한 egress filter:

- UDP `5001` -> `skbedit priority 7`
- UDP `5002` -> `skbedit priority 6`
- UDP `5003` -> default `p0`

이번 Phase 2는 아래 두 flow에 집중했다.

- Flow A: UDP `5001`, PCP `7`, target `10 Mbits/sec`
- Flow B: UDP `5003`, PCP `0`, background `20 Mbits/sec`

## CBS apply 결과

### hardware offload 시도

명령:

```bash
tc qdisc replace dev eth0 parent 100:1 cbs \
  locredit -1438 hicredit 62 sendslope -999000 idleslope 1000 offload 1
```

결과:

```text
Error: Specified device failed to setup cbs hardware offload.
```

### software CBS 시도

명령:

```bash
tc qdisc replace dev eth0 parent 100:1 cbs \
  locredit -1438 hicredit 62 sendslope -999000 idleslope 1000 offload 0
```

결과:

```text
qdisc cbs 8003: parent 100:1 ... offload 0
```

## 비교 실험

### 1. CBS 전

동시에 송신:

- `5001` at `10 Mbits/sec`
- `5003` at `20 Mbits/sec`

receiver 결과:

`5001`:

```text
4.77 MBytes  9.99 Mbits/sec  receiver
```

`5003`:

```text
9.55 MBytes  20.0 Mbits/sec  receiver
```

class 결과:

```text
class 100:1 -> 5147929 bytes / 3469 pkt
class 100:3 -> 10301835 bytes / 6928 pkt
```

### 2. CBS 후

동일하게 동시에 송신:

- `5001` at `10 Mbits/sec`
- `5003` at `20 Mbits/sec`

receiver 결과:

`5001`:

```text
591 KBytes  1.00 Mbits/sec  receiver
```

`5003`:

```text
9.54 MBytes  20.0 Mbits/sec  receiver
```

qdisc / class 결과:

```text
qdisc cbs 8003: parent 100:1
Sent 624357 bytes 434 pkt

class 100:1 -> 624357 bytes / 434 pkt
class 100:3 -> 20594731 bytes / 13850 pkt
```

## 판정

Phase 2는 완료로 본다.

확정된 사실:

1. hardware offload CBS는 현재 환경에서 reject 되었다.
2. software CBS는 실제로 적용되었다.
3. `p7` target flow는 약 `1 Mbits/sec` 수준으로 제한되었다.
4. `p0` background flow는 `20 Mbits/sec`를 유지했다.

즉 현재 환경에서는 **software CBS 기준으로 queue/class shaping 효과**가 재현되었다.

## 다음 단계 준비 상태

다음 `Phase 3`를 위해 현재 live는 그대로 유지한다.

- `eth0`: Phase 2 `mqprio map` 유지
- `eth0 parent 100:1`: `CBS offload 0` 유지
- `br-tsn.301`: sender path 유지
- TMDS receiver namespace / `iperf3` server 유지
