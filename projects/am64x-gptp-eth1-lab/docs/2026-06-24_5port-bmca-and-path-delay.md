# 2026-06-24 5-Port BMCA and Path Delay Test

## 목적

현재 연결된 5개 포트 기준으로 다음 두 가지를 분리 확인한다.

1. BMCA 기본 모드에서 어떤 clock identity가 최종 GM 역할을 잡는지
2. GM을 사실상 고정한 상태에서 각 포트별 path delay를 읽을 수 있는지

이번 문서는 **현재 실험에서 실제로 얻은 결과**만 기록한다.
성공하지 못한 측정도 그대로 남긴다.

## 시험 시점 연결 구조

- SK-AM64B
  - `eth0`: control port, `192.168.0.110/24`
  - `eth1`: no-IP L2 port
- TMDS64EVM
  - `eth0`: control port, `192.168.0.220/24`
  - `eth1`: no-IP L2 port
  - `eth2`: no-IP L2 port, ICSSG

해석 기준:

- 포트 수는 5개지만, Linux `ptp4l` 관점의 clock instance는 3개다.
  - SK CPSW clock: `eth0`, `eth1` -> shared `/dev/ptp0`
  - TMDS CPSW clock: `eth0`, `eth1` -> shared `/dev/ptp0`
  - TMDS ICSSG clock: `eth2` -> `/dev/ptp2`

## 저장한 원본 로그 위치

### BMCA 기본 모드

- `logs/2026-06-24_5port-bmca/sk_2port_ptp4l.log`
- `logs/2026-06-24_5port-bmca/tmds_cpsw_2port_ptp4l.log`
- `logs/2026-06-24_5port-bmca/tmds_icssg_eth2_ptp4l.log`
- `logs/2026-06-24_5port-bmca/sk_2port_ptp4l_after-phc-set.log`
- `logs/2026-06-24_5port-bmca/tmds_cpsw_2port_ptp4l_after-phc-set.log`
- `logs/2026-06-24_5port-bmca/tmds_icssg_eth2_ptp4l_after-phc-set.log`

### Path delay / GM mode 보조 로그

- `logs/2026-06-24_5port-path-delay/`
- `logs/2026-06-24_5port-path-delay-gm-modes/`
- `logs/2026-06-24_5port-path-delay-gm-modes/forced-gm/`

## 1. BMCA 기본 모드 결과

### 관찰 결과

PHC epoch를 `CLOCK_REALTIME`에 맞춘 뒤 3개 clock instance를 동시에 실행했다.

핵심 로그:

- SK CPSW:
  - `selected best master clock 98038a.fffe.77ced6`
  - 두 포트 모두 `assuming the grand master role`
- TMDS CPSW:
  - `selected best master clock 28b5e8.fffe.cc2a3f`
  - `eth0`: `MASTER -> UNCALIBRATED on RS_SLAVE`
  - `eth1`: `MASTER -> PASSIVE on RS_PASSIVE`
- TMDS ICSSG:
  - `selected /dev/ptp2 as PTP clock`
  - `selected best master clock 28b5e8.fffe.cc2a3f`
  - `eth2`: `MASTER -> UNCALIBRATED on RS_SLAVE`

### 해석

- 현재 5-port L2 시험에서 **TMDS 쪽 두 clock(TMD CPSW, TMDS ICSSG)** 은 모두
  **SK clock identity `28b5e8.fffe.cc2a3f`** 를 상위 master로 선택했다.
- 반면 SK 로그는 foreign master를 보면서도 최종적으로 local GM 역할을 유지하는 형태로 끝났다.
- 즉 이번 시간창에서 BMCA winner는 **SK CPSW clock** 으로 해석하는 것이 가장 자연스럽다.

### path delay 확보 여부

- BMCA 기본 모드에서는 TMDS `eth0`, `eth2`가 `UNCALIBRATED`까지만 내려가고
  안정적 `SLAVE` 상태로 수렴하지 않아 유효한 `rms/delay/freq` 로그를 얻지 못했다.
- TMDS `eth1`은 같은 CPSW clock의 다른 포트라 `PASSIVE`로 정리되었다.

결론:

```text
BMCA winner는 관측되었지만,
5-port 동시 모드만으로는 모든 포트의 안정적 path delay를 얻지 못했다.
```

## 2. 독립 GM 지정 시도 결과

## 시도 방법

강제 GM 모드 목적은 각 포트를 slave로 한 번씩 내려서 path delay를 읽는 것이었다.

시도한 조합:

1. GM `TMDS eth0` -> slave `SK eth0`
2. GM `TMDS eth0` -> slave `SK eth1`
3. GM `SK eth0` -> slave `TMDS eth0`
4. GM `SK eth0` -> slave `TMDS eth1`
5. GM `SK eth0` -> slave `TMDS eth2`

### 2-1. `-s client only` 방식

결과:

- 모든 slave 포트가 foreign master를 보고
- `selected best master clock ...`
- `LISTENING -> UNCALIBRATED on RS_SLAVE`

까지만 진행되었고,
`UNCALIBRATED -> SLAVE` 및 `rms/delay/freq` 안정화 로그는 나오지 않았다.

대표 예:

- `gm_tmds_eth0__slave_sk_eth0_slave.log`
- `gm_sk_eth0__slave_tmds_eth2_slave.log`

### 2-2. `priority1` 차이 기반 GM 고정 시도

추가로:

- GM 쪽 `priority1 10`
- slave 쪽 `priority1 200`

를 준 조합도 시험했다.

대표 예:

- `prio_test_sk_eth0_gm.log`
- `prio_test_tmds_eth2_slave.log`

결과:

- slave 포트는 foreign master를 관측하고
- `selected best master clock ...`
- `MASTER -> UNCALIBRATED on RS_SLAVE`

까지만 진행되었고,
역시 안정적 `SLAVE`와 `path delay` 값까지는 내려가지 않았다.

## 3. 포트별 현재 판정

| Board | Port | PHC | BMCA 참여 | GM/Slave 정리 | path delay 확보 여부 |
|---|---|---|---|---|---|
| SK | eth0 | `/dev/ptp0` | 가능 | BMCA에서 GM clock 측 | 미확보 |
| SK | eth1 | `/dev/ptp0` | 가능 | BMCA에서 GM clock 측 | 미확보 |
| TMDS | eth0 | `/dev/ptp0` | 가능 | BMCA에서 `UNCALIBRATED` | 미확보 |
| TMDS | eth1 | `/dev/ptp0` | 가능 | BMCA에서 `PASSIVE` | 미확보 |
| TMDS | eth2 | `/dev/ptp2` | 가능 | BMCA에서 `UNCALIBRATED` | 미확보 |

## 4. 이번 세션의 핵심 결론

1. **5개 포트 모두 gPTP BMCA 참여 자체는 가능**하다.
2. **TMDS eth2는 ICSSG `/dev/ptp2`로 참여**한다.
3. **BMCA winner는 SK CPSW clock으로 해석**된다.
4. 하지만 **현재 5-port local L2 동시 시험만으로는 모든 포트의 안정적 path delay 수치를 확보하지 못했다.**

## 5. 왜 path delay 확보가 어려웠는가

현재 관찰 사실만 적으면 다음과 같다.

- shared PHC를 가진 multi-port clock이 같은 L2에 함께 참여하고 있다.
- 그 결과 일부 포트는 `PASSIVE`, 일부는 `UNCALIBRATED`까지만 내려간다.
- 이번 시간창에서는 `SLAVE` 안정화 이후 나오는 `rms/delay/freq`가 확보되지 않았다.

이 문서에서는 이유를 더 과하게 단정하지 않고, **로그로 확인된 결과까지만** 기록한다.

## 6. 후속 권장

path delay를 실제 수치로 확보하려면 다음 둘 중 하나를 선택해야 한다.

1. 현재 5-port L2 상태에서 더 긴 시간으로 `SLAVE` 안정화를 기다린다.
2. 각 포트를 대표 slave로 단순화한 추가 측정 절차를 설계한다.

현재 단계에서 확정된 것은:

```text
5-port BMCA 참여 가능: yes
BMCA winner 관측: yes
각 포트 stable path delay 확보: not yet
```
