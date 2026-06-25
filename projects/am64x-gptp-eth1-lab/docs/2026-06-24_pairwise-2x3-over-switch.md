# 2026-06-24 Pairwise 2x3 gPTP Test Over Local L2 Switch

## 목적

현재 local L2 switch에 연결된 포트 기준으로,

- SK `eth0`, `eth1`
- TMDS `eth0`, `eth1`, `eth2`

총 `2 x 3` 조합을 **1:1 pairwise**로 나누어 시험한다.

핵심 질문은 다음이다.

1. local L2 switch 경유 환경에서도 `ptp4l`이 stable slave까지 내려가는가?
2. direct link에서 보였던 `SLAVE + rms/path delay/freq` 수치가 switch 경유에서도 재현되는가?
3. 되지 않는다면, 현재 단계에서 direct link만 가능한지 판단할 근거가 되는가?

## 시험 대상 조합

### BMCA 기본 모드

1. `SK eth0` ↔ `TMDS eth0`
2. `SK eth0` ↔ `TMDS eth1`
3. `SK eth0` ↔ `TMDS eth2`
4. `SK eth1` ↔ `TMDS eth0`
5. `SK eth1` ↔ `TMDS eth1`
6. `SK eth1` ↔ `TMDS eth2`

### GM 지정 시도

포트별 slave path delay를 확보하기 위해 다음 조합을 추가로 시도했다.

- `GM SK eth0 -> slave TMDS eth0`
- `GM SK eth0 -> slave TMDS eth1`
- `GM SK eth0 -> slave TMDS eth2`
- `GM TMDS eth0 -> slave SK eth0`
- `GM TMDS eth0 -> slave SK eth1`

GM 지정은 두 방식으로 시도했다.

1. `ptp4l -s` client only
2. `priority1` 차이 기반 사실상 고정 GM

## 로그 위치

### BMCA 기본 모드

- `logs/2026-06-24_pairwise-2x3/bmca/`

주요 파일:

- `eth0_eth0_sk.log`, `eth0_eth0_tmds.log`
- `eth0_eth1_sk.log`, `eth0_eth1_tmds.log`
- `eth0_eth2_sk.log`, `eth0_eth2_tmds.log`
- `eth1_eth0_sk.log`, `eth1_eth0_tmds.log`
- `eth1_eth1_sk.log`, `eth1_eth1_tmds.log`
- `eth1_eth2_sk.log`, `eth1_eth2_tmds.log`

### GM 지정 시도

- `logs/2026-06-24_5port-path-delay-gm-modes/forced-gm/`
- `logs/2026-06-24_5port-path-delay-gm-modes/prio_test_*.log`

## 1. BMCA 기본 모드 결과

## 공통 관찰

모든 6개 조합에서 다음은 공통으로 확인되었다.

- 각 포트는 자신에게 맞는 PHC를 선택했다.
  - SK `eth0`, `eth1`: `/dev/ptp0`
  - TMDS `eth0`, `eth1`: `/dev/ptp0`
  - TMDS `eth2`: `/dev/ptp2`
- 서로 `new foreign master`를 관측했다.
- BMCA winner는 형성되었다.

그러나 **모든 조합에서 stable `SLAVE`까지는 내려가지 않았다.**

TMDS 쪽 로그는 모두 다음 패턴으로 끝났다.

```text
new foreign master ...
selected best master clock ...
MASTER to UNCALIBRATED on RS_SLAVE
```

SK 쪽 로그는 대체로 다음 패턴으로 끝났다.

```text
LISTENING to MASTER
assuming the grand master role
new foreign master ...
```

즉 이번 local L2 switch 경유 pairwise 시험에서는

```text
foreign master 관측: yes
BMCA winner 관측: yes
stable SLAVE: no
path delay 수치 출력: no
```

상태였다.

## 조합별 요약

| SK port | TMDS port | TMDS 선택 PHC | foreign master 관측 | stable SLAVE | delay/rms 확보 |
|---|---|---|---|---|---|
| eth0 | eth0 | `/dev/ptp0` | yes | no (`UNCALIBRATED`) | no |
| eth0 | eth1 | `/dev/ptp0` | yes | no (`UNCALIBRATED`) | no |
| eth0 | eth2 | `/dev/ptp2` | yes | no (`UNCALIBRATED`) | no |
| eth1 | eth0 | `/dev/ptp0` | yes | no (`UNCALIBRATED`) | no |
| eth1 | eth1 | `/dev/ptp0` | yes | no (`UNCALIBRATED`) | no |
| eth1 | eth2 | `/dev/ptp2` | yes | no (`UNCALIBRATED`) | no |

## 2. direct link와의 비교에서 의미 있는 점

이전 세션에서,

- `SK eth1` ↔ `TMDS eth2`

를 **직결 cable**로 연결했을 때는

```text
TMDS eth2: MASTER -> UNCALIBRATED -> SLAVE
rms/path delay/freq 안정화
delay 약 438~440 ns
```

가 실제로 확인되었다.

반면 이번 문서의 같은 포트 조합은 **local L2 switch 경유** 상태였고,
결과는

```text
MASTER -> UNCALIBRATED
```

까지만 진행되었다.

즉 이번 시점의 가장 중요한 관찰은:

```text
같은 포트 조합이라도
direct link에서는 stable SLAVE가 되지만,
현재 local L2 switch 경유 상태에서는 stable SLAVE가 재현되지 않았다.
```

이다.

이 결과는 “현재 문제를 만든 조건”을 direct vs switch 경유 차이로 좁히는 근거가 된다.

## 3. GM 지정 시도 결과

## `-s client only` 방식

대표 로그:

- `gm_sk_eth0__slave_tmds_eth2_slave.log`
- `gm_tmds_eth0__slave_sk_eth0_slave.log`

공통 결과:

```text
selected /dev/ptpX as PTP clock
new foreign master ...
selected best master clock ...
LISTENING to UNCALIBRATED on RS_SLAVE
```

즉 slave를 강하게 요구해도 `SLAVE`까지 가지 못했다.

## `priority1` 차이 방식

대표 로그:

- `prio_test_sk_eth0_gm.log`
- `prio_test_tmds_eth2_slave.log`

결과:

- foreign master와 best master 선택은 관측됨
- 하지만 역시 `MASTER -> UNCALIBRATED`에서 멈춤
- 안정적 `rms/delay/freq` 값은 확보되지 않음

## GM 지정 시도 결론

```text
GM을 사실상 고정해도,
현재 local L2 switch 경유 환경에서는
stable SLAVE 및 path delay 수치 확보에 실패했다.
```

## 4. 이번 시험의 최종 결론

### 확인된 것

1. 모든 pairwise 조합에서 `ptp4l` 실행 가능
2. 모든 pairwise 조합에서 foreign master 관측 가능
3. 모든 pairwise 조합에서 BMCA winner 형성은 가능
4. TMDS `eth2`는 switch 경유 pairwise 조합에서도 `/dev/ptp2`로 참여

### 확인되지 않은 것

1. local L2 switch 경유 pairwise 환경에서 stable `SLAVE`
2. local L2 switch 경유 pairwise 환경에서 `rms`, `delay`, `freq` 안정화 수치
3. 포트별 path delay 숫자

### 현재 단계 해석

이번 결과만 놓고 보면,

```text
direct link에서는 stable slave/path delay 측정이 가능했지만,
현재 local L2 switch 경유 구성에서는 아직 stable slave/path delay 측정이 되지 않았다.
```

라고 정리하는 것이 가장 정확하다.

이 문서는 “switch 경유가 절대 불가능하다”고 단정하지 않는다.
다만 **현재 구성/시간창/설정 기준으로는 재현되지 않았다**는 사실을 기록한다.

## 5. 후속 권장

1. local L2 switch 경유 상태에서 `UNCALIBRATED`가 오래 지속되는 원인을 더 좁히려면,
   스위치 filtering/pdelay 처리/VLAN 동작을 따로 분리해야 한다.
2. 기능 확인 기준의 성공 경로는 여전히 direct link다.
3. path delay 숫자가 꼭 필요하면 현재 단계에서는 direct path를 canonical 측정 경로로 보는 것이 안전하다.
