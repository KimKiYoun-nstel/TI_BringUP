# Phase 3 taprio Apply Check

## 목적

Qbv 본실험 전에 `taprio` qdisc가 적용 가능한지, 그리고 hardware offload가 accepted 되는지 확인한다.

## 준비 자산

- `../board/setup_taprio.sh`
- Phase 1 결과

## 1차 pass 기준

- `taprio` qdisc 적용 성공
- traffic이 계속 흐름
- 가능하면 offload accept/reject 원인을 `dmesg`로 확인

## 현재 상태

- 완료

## 이번 확인 상태

- live 시작점은 `Phase 2 reusable state`
- `eth0`는 Phase 2 `mqprio map`과 `CBS offload 0` 상태에서 시작
- `sch_taprio` module load 가능 확인
- kernel config 확인:

```text
CONFIG_NET_SCH_TAPRIO=m
CONFIG_TI_K3_AM65_CPTS=y
CONFIG_TI_AM65_CPSW_QOS=y
```

## 첫 시도

다음 2-entry schedule을 적용했다.

```text
gatemask 0x1 50ms
gatemask 0x6 50ms
```

결과:

- `tc qdisc replace ... taprio ...` 자체는 성공
- 그러나 같은 running schedule 상태에서 map/gate를 바꾸는 재설정은 다음 에러로 막혔다.

```text
Error: Changing the traffic mapping of a running schedule is not supported.
```

- 이 selective schedule 상태에서는 `br-tsn.301 -> TMDS` control-path traffic이 끊겼다.

즉 이 단계에서는 **taprio apply는 되지만, gate mask 설계가 공격적이면 continuity가 깨질 수 있음**을 확인했다.

## 재시도: all-open schedule

running schedule을 `tc qdisc del dev eth0 root`로 내린 뒤,
다음 all-open schedule로 다시 생성했다.

```text
sched-entry S ff 100000000
```

결과:

```text
TAPRIO_RECREATE_RC=0
qdisc taprio 8005: root tc 3 map 2 2 2 2 2 2 1 0 2 2 2 2 2 2 2 2
clockid TAI
index 0 cmd S gatemask 0xff interval 100000000
```

## Traffic continuity 확인

all-open schedule 상태에서:

- `ping -I br-tsn.301 10.31.0.2`: 성공
- UDP `5001`, `5 Mbits/sec`, `2 sec`: 성공
- UDP `5003`, `5 Mbits/sec`, `2 sec`: 성공

receiver 결과:

`5001`:

```text
1.19 MBytes  5.00 Mbits/sec  receiver
```

`5003`:

```text
1.19 MBytes  5.00 Mbits/sec  receiver
```

## 판정

Phase 3은 완료로 본다.

근거:

1. `taprio` qdisc가 현재 kernel/runtime에서 실제 적용되었다.
2. running schedule 재설정 제약이 있음을 확인했다.
3. all-open schedule에서는 traffic continuity가 유지되었다.
4. fatal reject 없이 `Phase 4`에 쓸 수 있는 `taprio live state`를 확보했다.

## 현재 live 유지 상태

다음 `Phase 4` 시작을 위해 현재 live는 그대로 유지한다.

- `eth0`: root `taprio` all-open schedule 유지
- `br-tsn.301`: sender path 유지
- TMDS `ep1`/`ep2`, `5001`/`5002`/`5003` receiver 유지
