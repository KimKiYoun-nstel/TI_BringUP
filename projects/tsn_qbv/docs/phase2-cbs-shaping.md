# Phase 2 CBS Shaping

## 목적

Qbv 전에 CBS로 queue/class 단위 shaping이 실제 traffic pattern 변화로 이어지는지 확인한다.

## 준비 자산

- `../board/setup_cbs.sh`
- Phase 1 결과

## 1차 pass 기준

- CBS qdisc 적용 성공
- 적용 전후 throughput, jitter, burst pattern 차이 관찰

## 현재 상태

- 완료

## 이번 적용 상태

- live 시작점은 `Phase 1 reusable state`
- `eth0` `mqprio map`:

```text
2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
```

의도:

- `p7 -> TC0 -> class 100:1`
- `p6 -> TC1 -> class 100:2`
- `p0 -> TC2 -> class 100:3`

- SK sender helper path 유지:
  - `br-tsn.301 = 10.31.0.3/24`
  - UDP `5001` -> `skbedit priority 7`
  - UDP `5002` -> `skbedit priority 6`
  - UDP `5003` -> default `p0`

## CBS 적용 결과

### hardware offload

다음 시도는 reject 되었다.

```text
tc qdisc replace dev eth0 parent 100:1 cbs ... offload 1
Error: Specified device failed to setup cbs hardware offload.
```

### software CBS

다음은 accept 되었다.

```text
tc qdisc replace dev eth0 parent 100:1 cbs \
  locredit -1438 hicredit 62 sendslope -999000 idleslope 1000 offload 0
```

## 비교 실험

동시 부하:

- Flow A: UDP `5001`, `p7`, target `10 Mbits/sec`
- Flow B: UDP `5003`, `p0`, background `20 Mbits/sec`

### CBS 전

`5001` receiver:

```text
4.77 MBytes  10.0 Mbits/sec  receiver
```

`5003` receiver:

```text
9.55 MBytes  20.0 Mbits/sec  receiver
```

class counter:

```text
class 100:1 -> 5147929 bytes / 3469 pkt
class 100:3 -> 10301835 bytes / 6928 pkt
```

### CBS 후

`5001` receiver:

```text
591 KBytes  1.00 Mbits/sec  receiver
```

`5003` receiver:

```text
9.54 MBytes  20.0 Mbits/sec  receiver
```

class/qdisc evidence:

```text
qdisc cbs 8003: parent 100:1 ...
Sent 624357 bytes 434 pkt

class 100:1 -> 624357 bytes / 434 pkt
class 100:3 -> 20594731 bytes / 13850 pkt
```

## 판정

Phase 2는 완료로 본다.

근거:

1. CBS qdisc가 software mode로는 실제 적용되었다.
2. target `p7` flow는 `10 Mbits/sec -> 약 1 Mbits/sec`로 줄었다.
3. background `p0` flow는 `20 Mbits/sec`를 유지했다.
4. 즉 queue/class 단위 shaping이 실제 traffic pattern 차이로 이어졌다.

## 현재 live 유지 상태

다음 `Phase 3` 시작을 위해 현재 live는 그대로 유지한다.

- `eth0`: Phase 2 `mqprio map` 유지
- `eth0 parent 100:1`: CBS `offload 0` 유지
- `br-tsn.301`: sender path 유지
- TMDS `ep1`/`ep2`, `5001`/`5002`/`5003` receiver 유지
