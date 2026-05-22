# 2026-05-22 SK-AM64B Phase 4 SHM + VTM live validation

## 목적

SK-AM64B에서 Phase 4의 다음 항목을 실보드로 검증했다.

```text
1. reserved-memory 기반 R5F -> A53 SHM status block
2. A53 r5ctl shm-status read path
3. R5F VTM sensor0/sensor1 raw read
4. raw -> milli-Celsius 변환 결과와 Linux hwmon 비교
```

## 사전 상태

초기 확인에서 보드는 다음 mismatch 상태였다.

```text
- active firmware: Phase 4 button-event-lab test firmware
- running DT: r5f-status-shm@a5800000 없음
- /proc/iomem: a5800000 포함 구간이 System RAM
```

즉 new firmware / old DTB 조합이었고, 이 상태에서는 SHM write가 unsafe하다.

## 조치

1. DTB-only deploy를 수행했다.
2. deploy 결과만으로는 running DT에 SHM node가 바로 반영되지 않아, Phase 4 검증에 사용한 DTB를 수동 반영 후 재부팅했다.
3. 이후 running DT와 `/proc/iomem`에서 SHM carveout이 실제로 보이는지 다시 확인했다.
4. 최신 `am64-main-r5f0_0-fw`, `r5ctl`, manage script를 배포하고 재부팅했다.

## 확인한 핵심 증적

### 1. reserved-memory 반영

sysfs 기준 reserved-memory node 존재:

```text
/sys/firmware/devicetree/base/reserved-memory/r5f-status-shm@a5800000
```

`reg` 값:

```text
0x00000000 0xa5800000 0x00000000 0x00001000
```

`compatible` 값:

```text
shared-dma-pool
```

`/proc/iomem` 기준:

```text
9e800000-a5800fff : reserved
```

### 2. 기본 SHM status 동작

실보드 `r5ctl shm-status` 예시:

```text
magic=0x52354653
version=0x00010000
abi_size=144
seq=120
heartbeat=120
shm_update_count=120
shm_update_period_ms=100
```

판단:

```text
- SHM ABI header/magic/version 정상
- sequence/heartbeat/update_count 증가 정상
- A53 /dev/mem read path 정상
```

### 3. RPMsg telemetry 연동

`r5ctl status` 후 SHM 확인 시:

```text
rpmsg_rx_count=1
rpmsg_tx_count=1
last_command_id=0x0003
last_error=OK
```

즉 RPMsg command/response count와 마지막 command ID가 SHM에 반영됨을 확인했다.

### 4. GPIO -> SHM 반영

`r5ctl gpio set mcu_gpio0_8 1` 후 1초 뒤 `r5ctl shm-status`에서 다음을 확인했다.

```text
last_command_id=0x0102
output_state=1
rpmsg_rx_count=5
rpmsg_tx_count=5
```

검증 종료 후에는 `r5ctl gpio set mcu_gpio0_8 0`으로 원복했다.

### 5. VTM raw register 교차검증

보드에서 `devmem2`로 다음 register를 read했다.

```text
0x00b00308 -> 0x0008095A / 0x00080955 / 0x00080958
0x00b00328 -> 0x00080957 / 0x00080956 / 0x00080956
```

Linux driver와 동일하게 `0x3ff` mask를 적용하면 low 10-bit raw는 다음과 같다.

```text
sensor0 raw candidates: 0x15A=346, 0x155=341, 0x158=344
sensor1 raw candidates: 0x157=343, 0x156=342, 0x156=342
```

R5F SHM 예시 값:

```text
soc_temp0_raw=344
soc_temp1_raw=343
```

판단:

```text
R5F의 3-sample/closest-two-average 방식이 A53 side raw MMIO read와 일관된다.
```

### 6. milli-Celsius 비교

최종 재검증에서 다음을 확인했다.

```text
R5F SHM:
  soc_temp0_raw=344
  soc_temp0_millicelsius=44981
  soc_temp1_raw=343
  soc_temp1_millicelsius=44753

Linux hwmon:
  main0_thermal=44981
  main1_thermal=44981

delta:
  soc_temp0_delta_millicelsius=0
  soc_temp1_delta_millicelsius=-228
```

이전 샘플에서도 수백 mC 수준 차이로 수렴했다.

## 판단

확정된 사실:

```text
1. SK-AM64B에서 r5f-status-shm@a5800000 carveout이 실제 booted DT에 반영되었다.
2. R5F는 SHM에 runtime/RPMsg/GPIO/event telemetry를 주기적으로 기록한다.
3. A53 r5ctl shm-status는 SHM snapshot을 정상적으로 읽는다.
4. R5F는 VTM sensor index 0/1 raw code를 읽고 milli-Celsius로 변환한다.
5. 변환 결과는 Linux hwmon main0_thermal/main1_thermal와 대체로 일치한다.
```

합리적 추정:

```text
1. AM64x 경로에서는 Linux driver와 동일한 golden polynomial 기반 lookup만으로도 실용적인 정확도를 확보한다.
2. sensor0/1 mapping은 main0_thermal/main1_thermal과 맞다.
```

주의:

```text
old DTB 상태에서 new Phase 4 firmware를 올리면 a5800000가 System RAM일 수 있으므로 사용하면 안 된다.
DTB 선반영은 필수 전제다.
```
