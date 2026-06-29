# Endpoint Taprio Coexistence Matrix

> Evidence-only note: current canonical summary is `docs/phaseA-endpoint-egress-qbv.md`.

## 목적

현재 direct endpoint 경로 3개에 대해 다음 항목을 한 번에 비교한다.

1. software `taprio`
2. hardware `taprio`
3. `taprio + gPTP coexistence`

대상 경로:

1. `SK eth0(CPSW) -> TMDS eth1(CPSW)`
2. `SK eth1(CPSW) -> TMDS eth2(ICSSG)`
3. `TMDS eth2(ICSSG) -> SK eth1(CPSW)`

`TMDS eth1 -> SK eth0`는 현재 TMDS control-port model 충돌 때문에 제외한다.

## Matrix

| Direction | SW taprio egress | HW taprio egress | SW + gPTP coexistence | HW + gPTP coexistence | 판정 |
|---|---|---|---|---|---|
| `SK eth0 -> TMDS eth1` | success | success | success | success | pair2 CPSW path는 SW/HW 모두 안정적 |
| `SK eth1 -> TMDS eth2` | success | success | success | partial | HW path에서 traffic은 유지되지만 gPTP state가 불안정 |
| `TMDS eth2 -> SK eth1` | success | success | success | fail | HW path는 tx timestamp timeout으로 gPTP failure |

## 1. SK eth0(CPSW) -> TMDS eth1(CPSW)

### SW taprio

- schedule: `clockid CLOCK_TAI`, `0x5 250000 / 0x3 250000`
- traffic:
  - `5001`: `20.0 Mbits/sec`, loss `0/8634`
  - `5002`: `20.0 Mbits/sec`, loss `0/8634`
- TMDS `ptp4l`:
  - `MASTER -> UNCALIBRATED -> SLAVE`

### HW taprio

- schedule: `flags 2`, `0x5 250000 / 0x3 250000`
- traffic:
  - `5001`: `20.0 Mbits/sec`, loss `0/13814`
  - `5002`: `20.0 Mbits/sec`, loss `0/13814`
- TMDS `ptp4l`:
  - `MASTER -> UNCALIBRATED -> SLAVE`

### 판단

- pair2 CPSW path는 SW/HW 모두에서 traffic과 gPTP coexistence가 성립했다.
- 현재 direct endpoint 기준 가장 안정적인 reference path로 볼 수 있다.

## 2. SK eth1(CPSW) -> TMDS eth2(ICSSG)

### SW taprio

- 기존 Phase A 결과 기준 coexistence success
- `switch_mode=false` direct path에서 same-port software `taprio`와 gPTP가 공존했다.

### HW taprio

- hardware `taprio` egress 자체는 이미 success (`500 us`)
- `TC0 always-open` HW schedule에서 traffic도 유지됐다.
- 그러나 gPTP log는 완전히 안정적이지 않았다.

관측:

- SK `ptp4l`:
  - `LISTENING -> FAULTY -> LISTENING -> GRAND_MASTER`
- TMDS `ptp4l`:
  - `LISTENING -> UNCALIBRATED -> SLAVE`
  - 이후 `SLAVE -> MASTER -> UNCALIBRATED -> SLAVE` 재천이 발생

### 판단

- hardware `taprio + traffic`은 성립한다.
- 하지만 same-port gPTP coexistence는 아직 stable success로 판정하기 어렵다.
- 현재 상태는 `partial / unstable`이다.

## 3. TMDS eth2(ICSSG) -> SK eth1(CPSW)

### SW taprio

- schedule: software `taprio`, `clockid CLOCK_TAI`, `0x5 500000 / 0x3 500000`
- traffic:
  - `5001`: `20.0 Mbits/sec`, loss `0/13813`
  - `5002`: `20.0 Mbits/sec`, loss `0/13813`
- TMDS `ptp4l`:
  - `MASTER -> UNCALIBRATED -> SLAVE`

### HW taprio

- schedule: hardware `taprio`, `flags 2`, `0x5 500000 / 0x3 500000`
- ICSSG minimum cycle 제약에 맞춰 total `1 ms` 사용
- gPTP log:

```text
timed out while polling for tx timestamp
send peer delay request failed
LISTENING -> FAULTY
```

- 같은 run에서 traffic도 정상 delivery로 이어지지 못했고, TMDS sender 쪽 filter counter도 증가하지 않았다.

### 판단

- reverse ICSSG path에서는 software `taprio + gPTP coexistence`는 성립했다.
- 반면 hardware `taprio + gPTP coexistence`는 실패했다.

## 4. Practical Difference

### CPSW sender path (`SK eth0`, `SK eth1`)

- hardware `taprio`는 실제 EST offload capability를 증명한다.
- CPSW direct sender에서는 `500 us` cycle까지 안정적으로 사용 가능하다.
- pair2에서는 hardware coexistence도 success다.

### ICSSG sender path (`TMDS eth2`)

- software `taprio`는 coexistence까지 더 유연하게 성립했다.
- hardware `taprio`는 minimum cycle, queue, VLAN qos-map 등 prerequisite를 더 많이 요구한다.
- 특히 same-port gPTP와 같이 붙으면 `tx timestamp` failure가 재현될 수 있다.

## 5. Current Conclusion

```text
1. direct endpoint egress Qbv 자체는 SW/HW taprio 모두로 재현 가능하다.
2. CPSW sender path는 HW taprio + gPTP coexistence까지 비교적 안정적이다.
3. ICSSG sender path는 SW taprio는 coexistence가 되지만, HW taprio는 same-port gPTP에서 아직 불안정하거나 실패한다.
```
