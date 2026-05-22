# 외부 LED / 전압 실측 절차

## 목적

이 문서는 `am64x-r5f-hw-control-lab`의 마지막 Phase 1 검증인 **실제 GPIO 전압 변화 또는 외부 LED 점멸 확인** 절차를 정리한다.

이번 문서는 다음 사실을 전제로 한다.

1. A53 `r5ctl` ↔ R5F RPMsg 통신은 이미 정상 확인되었다.
2. `r5ctl trace`로 `[AM64X R5F HWLAB]` 로그를 확인할 수 있다.
3. SysConfig pinmux는 `MCU_SPI1_D0 -> MCU_GPIO0_8 (mode 7)`로 반영되었다.

아직 완료되지 않은 것은 **보드 외부에서 실제 신호가 보이는지** 확인하는 단계다.

## 준비물

### 최소 준비물

- 점퍼 와이어
- 330Ω ~ 1kΩ 저항 1개
- LED 1개

### 권장 준비물

- 멀티미터
- 로직 애널라이저 또는 오실로스코프

## 현재 구현 기준 GPIO 정보

현재 repo 구현 기준:

```text
target signal: MCU_GPIO0_8
SysConfig pad: MCU_SPI1_D0
mode: 7
GPIO base: MCU_GPIO0
GPIO pin: 8
```

주의:

```text
connector pin 번호는 아직 최종 확정 아님
package ball 주석 C7은 SoC/package 수준 정보임
반드시 SK-AM64B 회로도 / user guide / 실크를 다시 대조할 것
```

## 배선 전 확인

실제 LED를 연결하기 전에 아래를 확인한다.

1. `MCU_GPIO0_8`에 대응하는 보드 connector pin 번호
2. GND pin 위치
3. 3.3V pin 위치
4. 연결할 외부 회로와 보드 GND 공통 여부
5. 해당 pin에 다른 외부 장치가 이미 연결되어 있지 않은지

## 연결 방법 예시

### 방법 A: active-high LED

```text
MCU_GPIO target pin -> 저항(330Ω~1kΩ) -> LED -> GND
```

예상:

- `gpio set 1` 시 LED ON
- `gpio set 0` 시 LED OFF

### 방법 B: 멀티미터 전압 측정

```text
멀티미터 + probe -> MCU_GPIO target pin
멀티미터 - probe -> GND
```

예상:

- `gpio set 0` 시 약 0V
- `gpio set 1` 시 약 3.3V 근처

## 시험 전 소프트웨어 상태 정리

lab firmware 적용 후 baseline service가 trace에 잡음을 만들 수 있으므로 먼저 중지한다.

```bash
systemctl stop benchmark_server.service rpmsg_json.service || true
systemctl is-active benchmark_server.service rpmsg_json.service || true
```

기대 결과:

```text
inactive
failed 또는 inactive
```

## 시험 절차

### Step 1. 기본 상태 확인

```bash
r5ctl status
```

기대 결과:

```text
OK STATUS core=78000000.r5f service=rpmsg_chrdev endpoint=14 gpio=0 gpio_candidate=MCU_GPIO0_8 ...
```

### Step 2. Low 상태 측정

```bash
r5ctl gpio set 0
```

확인:

- 멀티미터 기준 0V 근처
- active-high LED 기준 OFF

### Step 3. High 상태 측정

```bash
r5ctl gpio set 1
```

확인:

- 멀티미터 기준 3.3V 근처
- active-high LED 기준 ON

### Step 4. Toggle 확인

```bash
r5ctl gpio toggle
r5ctl gpio toggle
```

확인:

- 상태가 반대로 바뀌는지

### Step 5. Blink 확인

```bash
r5ctl gpio blink 3
```

확인:

- LED 3회 점멸
- 또는 계측기에서 high/low 반복 관찰

### Step 6. Trace 확인

```bash
r5ctl trace
```

기대 로그 예:

```text
[AM64X R5F HWLAB] rx cmd=GPIO_SET 1
[AM64X R5F HWLAB] gpio configured candidate=MCU_GPIO0_8 base=0x04201000 pin=8
[AM64X R5F HWLAB] gpio candidate=MCU_GPIO0_8 value=1
[AM64X R5F HWLAB] tx rsp=OK GPIO_SET value=1
```

## 성공 판정

다음을 만족하면 물리 검증까지 포함한 Phase 1 성공으로 본다.

1. `r5ctl ping` / `status` / `gpio` 명령이 모두 `RC=0`
2. `r5ctl trace`로 R5F command trace 확인 가능
3. `gpio set 0/1`에 따라 실제 전압이 변함
4. `gpio blink 3`에 따라 LED 또는 계측기에서 점멸 확인 가능

## 실패 시 분기

### 통신은 되는데 LED/전압 변화가 없음

의심:

- connector pin 번호 오인
- GND 측정 위치 오류
- LED 극성 반대
- 저항/배선 문제
- 기대한 header pin과 실제 pad 노출 경로 불일치

### trace는 보이는데 `gpio set 1`에도 0V

의심:

- pad가 다른 회로에 묶여 있음
- board-level route가 예상과 다름
- 측정 지점이 package pad와 다른 net

### `ERR UNKNOWN_CMD`가 반복해서 trace에 남음

의미:

- baseline service가 lab firmware와 같은 RPMsg 채널에 payload를 보내는 중
- 실험 전에 `benchmark_server.service`, `rpmsg_json.service`를 중지하고 다시 확인

## 결과 기록 권장 형식

실측 후 아래 정보를 `docs/completion.md` 또는 별도 bring-up log에 남긴다.

```text
date/time
board IP
active firmware target
사용한 배선 방식 (LED / 멀티미터)
실제 connector pin 번호
gpio set 0 측정값
gpio set 1 측정값
gpio blink 관찰 결과
trace 요약
문제/주의사항
```

## 참고: Phase 4 SHM / 내부 온도센서 샘플 해석

이 문서는 원래 Phase 1 외부 LED / 전압 실측 절차용이지만,
실보드에서 `r5ctl shm-status`를 봤을 때 필드 의미를 빠르게 해석할 수 있도록
Phase 4 샘플도 함께 남긴다.

`shm-status` 전체 필드 설명은 별도 문서로 정리했다.

- `docs/shm-status-field-reference.md`

### 큰 그림

현재 Phase 4 구현은 다음 흐름이다.

```text
SoC internal temperature sensor (VTM)
  -> R5F가 raw code read
  -> R5F가 raw -> milli-Celsius 변환
  -> R5F가 SHM status block에 계속 write

A53 Linux
  -> r5ctl shm-status로 SHM snapshot read
  -> 동시에 Linux hwmon(main0_thermal/main1_thermal)도 read
  -> 둘을 같이 출력
```

즉 `r5ctl shm-status`에 보이는 `soc_temp*_*` 필드는 **R5F가 읽어서 SHM에 기록한 값**이고,
`linux_hwmon ... temp1_input_millicelsius=...` 줄은 **A53 Linux가 그 시점에 직접 읽은 기준값**이다.

### 예시 출력

```text
SHM status base=0xa5800000 size=0x1000
magic=0x52354653
version=0x00010000
abi_size=144
seq=9772
uptime_ms=977114
heartbeat=9772
shm_update_count=9772
main_loop_count=17
core=0x78000000
rpmsg_endpoint=14
rpmsg_rx_count=6
rpmsg_tx_count=6
rpmsg_error_count=0
last_command_id=0x0102
last_error=OK
output_gpio_id=mcu_gpio0_8
output_state=0
input_gpio_id=mcu_gpio0_6
input_state=1
event_count=0
last_event_type=none
last_event_gpio_id=0
last_event_timestamp_us=680
shm_update_period_ms=100
soc_temp0_valid=1
soc_temp0_raw=339
soc_temp0_millicelsius=43840
soc_temp0_last_error=OK
soc_temp1_valid=1
soc_temp1_raw=339
soc_temp1_millicelsius=43840
soc_temp1_last_error=OK
linux_hwmon name=main0_thermal path=/sys/class/hwmon/hwmon2 temp1_input_millicelsius=43840
linux_hwmon name=main1_thermal path=/sys/class/hwmon/hwmon3 temp1_input_millicelsius=43611
soc_temp0_delta_millicelsius=0
soc_temp1_delta_millicelsius=229
```

### 필드 의미

#### SHM header / snapshot 관련

```text
SHM status base
  A53이 /dev/mem mmap에 사용한 SHM physical address

size
  SHM reserved-memory 크기

magic
  SHM 구조체 식별값
  0x52354653 = "R5FS"

version
  SHM ABI 버전

abi_size
  현재 구조체 크기(byte)

seq
  snapshot sequence
  R5F가 SHM을 한 번 갱신할 때마다 증가
```

해석:

```text
seq/heartbeat/shm_update_count가 계속 증가하면
R5F가 SHM을 주기적으로 write하고 있다고 볼 수 있다.
```

#### runtime / loop 관련

```text
uptime_ms
  R5F firmware uptime (ms)

heartbeat
  SHM update heartbeat counter

shm_update_count
  SHM write 횟수

main_loop_count
  firmware main loop/task 쪽 progress indicator

shm_update_period_ms
  목표 SHM 갱신 주기
  현재 구현은 100 ms
```

#### RPMsg / command 관련

```text
rpmsg_rx_count
  R5F가 받은 RPMsg command 수

rpmsg_tx_count
  R5F가 보낸 RPMsg response/event 수

rpmsg_error_count
  RPMsg send/receive error count

last_command_id
  마지막으로 처리한 command ID
  예: 0x0003 = STATUS, 0x0102 = GPIO_SET

last_error
  마지막 command 처리 결과
```

#### GPIO / event 관련

```text
output_gpio_id
  output target GPIO logical id

output_state
  현재 output GPIO cached state
  0 = low, 1 = high

input_gpio_id
  input GPIO logical id

input_state
  현재 input sampled state
  현재 SW1은 active-low라 1=released, 0=pressed

event_count
  button/GPIO event 누적 count

last_event_type
  마지막 event 종류

last_event_gpio_id
  마지막 event source GPIO id

last_event_timestamp_us
  마지막 event timestamp
```

#### 내부 온도센서 관련

```text
soc_temp0_valid / soc_temp1_valid
  R5F가 해당 sensor 값을 정상적으로 읽고 변환했는지
  1이면 유효

soc_temp0_raw / soc_temp1_raw
  R5F가 VTM status register에서 읽은 10-bit raw code

soc_temp0_millicelsius / soc_temp1_millicelsius
  raw code를 Linux kernel driver와 같은 lookup 방식으로 변환한 값

soc_temp0_last_error / soc_temp1_last_error
  OK / UNAVAILABLE / RANGE 등 상태
```

#### A53 Linux 기준값 관련

```text
linux_hwmon name=main0_thermal ...
linux_hwmon name=main1_thermal ...
  A53 Linux가 같은 시점에 /sys/class/hwmon 에서 직접 읽은 값

soc_temp0_delta_millicelsius
soc_temp1_delta_millicelsius
  R5F SHM 값 - A53 hwmon 값
```

### 샘플 해석 예

위 예시는 다음처럼 읽으면 된다.

1. `seq=9772`, `heartbeat=9772`, `shm_update_count=9772`
   - R5F가 SHM을 계속 갱신 중이다.

2. `soc_temp0_valid=1`, `soc_temp1_valid=1`
   - R5F가 sensor0/sensor1 둘 다 정상적으로 읽었다.

3. `soc_temp0_raw=339`, `soc_temp0_millicelsius=43840`
   - R5F가 sensor0 raw code 339를 읽고 43.840C로 변환했다.

4. `linux_hwmon ... main0_thermal ... 43840`
   - A53 Linux도 같은 시점에 main0 thermal을 43.840C로 읽었다.

5. `soc_temp0_delta_millicelsius=0`
   - R5F 변환값과 Linux 기준값이 완전히 같다.

6. `soc_temp1_delta_millicelsius=229`
   - sensor1은 R5F 값이 Linux 값보다 0.229C 높다.
   - 이런 수백 mC 수준 차이는 샘플 시점 차이/연속 샘플 차이로 볼 수 있다.

### 현재 출력에 대한 한 줄 요약

```text
R5F가 internal temperature sensor를 계속 읽어 SHM에 쓰고 있고,
A53 r5ctl shm-status는 그 SHM snapshot과 Linux hwmon 기준값을 함께 출력한다.
```
