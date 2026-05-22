# shm-status 필드 설명서

## 목적

이 문서는 `r5ctl shm-status`로 출력되는 필드가
각각 **무슨 값인지**, **누가 쓰는 값인지**, **어떻게 해석해야 하는지**를
한 번에 볼 수 있도록 정리한 reference 문서다.

현재 기준 구조는 다음 흐름을 따른다.

```text
R5F firmware
  -> runtime/RPMsg/GPIO/event/VTM temperature 값을 SHM에 주기적으로 write

A53 Linux r5ctl shm-status
  -> SHM snapshot read
  -> Linux hwmon(main0_thermal/main1_thermal)도 read
  -> 둘을 함께 출력
```

즉 `shm-status` 출력에는 두 종류 값이 섞여 있다.

1. **R5F가 SHM에 기록한 값**
2. **A53 Linux가 그 시점에 직접 읽은 기준값**

---

## 예시 출력

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

---

## 필드 분류

### 1. SHM 위치 / ABI 식별 필드

#### `SHM status base=0xa5800000 size=0x1000`

```text
base
  A53이 /dev/mem mmap에 사용한 SHM physical address

size
  reserved-memory 크기
```

해석:

```text
이 값은 A53 reader 쪽 정보다.
R5F와 A53이 같은 SHM 물리 주소를 보고 있는지 확인하는 기준이다.
```

#### `magic=0x52354653`

```text
SHM 구조체 식별값
0x52354653 = ASCII "R5FS"
```

해석:

```text
이 값이 맞아야 A53이 "이 주소에 우리가 기대하는 SHM 구조체가 있다"고 볼 수 있다.
값이 다르면 주소가 틀렸거나 초기화가 안 된 것이다.
```

#### `version=0x00010000`

```text
SHM ABI version
```

해석:

```text
R5F writer와 A53 reader가 같은 구조체 버전을 쓰는지 확인하는 값이다.
나중에 필드를 추가/삭제할 때 호환성 체크 기준이 된다.
```

#### `abi_size=144`

```text
현재 SHM 구조체 크기(byte)
```

해석:

```text
reader가 기대하는 구조체 크기와 writer가 실제로 쓰는 구조체 크기가 같은지 보는 값이다.
```

---

### 2. snapshot consistency / update health 필드

#### `seq`

```text
R5F가 SHM snapshot을 한 번 publish할 때마다 증가하는 sequence 값
```

해석:

```text
값이 계속 증가하면 R5F가 SHM을 계속 갱신 중이라는 뜻이다.
값이 멈추면 writer가 멈췄거나 publish task가 죽었을 가능성을 의심한다.
```

#### `heartbeat`

```text
SHM update heartbeat counter
```

해석:

```text
실질적으로 seq와 같은 방향의 health indicator다.
운영 중에는 seq/heartbeat/shm_update_count가 함께 증가하는지 본다.
```

#### `shm_update_count`

```text
R5F가 SHM을 write한 누적 횟수
```

#### `shm_update_period_ms`

```text
목표 SHM publish 주기
현재 구현은 100 ms
```

해석:

```text
예를 들어 1초 뒤 다시 봤을 때 seq나 heartbeat가 대략 10 전후 증가하면
100 ms 주기로 정상 publish 중이라고 볼 수 있다.
```

---

### 3. R5F runtime 상태 필드

#### `uptime_ms`

```text
R5F firmware uptime (ms)
```

해석:

```text
R5F가 언제 reboot/reload 되었는지 추정할 수 있다.
```

#### `main_loop_count`

```text
firmware main task/loop 진행 상태를 보여주는 내부 progress 값
```

해석:

```text
이 값은 application 내부 구현에 따라 의미가 바뀔 수 있는 field다.
지금은 "main flow가 어디까지 진행되었는지"를 대략 보는 health field로 이해하면 된다.
```

---

### 4. RPMsg / command 처리 필드

#### `core=0x78000000`

```text
이 SHM writer가 어느 remote core인지 나타내는 ID
현재는 main R5F0_0 = 0x78000000
```

#### `rpmsg_endpoint=14`

```text
R5F/A53가 쓰는 RPMsg endpoint 번호
```

#### `rpmsg_rx_count`

```text
R5F가 받은 RPMsg command 수
```

#### `rpmsg_tx_count`

```text
R5F가 보낸 RPMsg response/event 수
```

#### `rpmsg_error_count`

```text
RPMsg send/receive 과정에서 기록한 error count
```

#### `last_command_id`

```text
마지막으로 처리한 command의 내부 ID
예:
  0x0001 = PING
  0x0003 = STATUS
  0x0102 = GPIO_SET
```

해석:

```text
직전에 어떤 종류의 command가 들어왔는지 추적할 때 본다.
```

#### `last_error`

```text
마지막 command 처리 결과
예: OK / ERR_BAD_ARG / ERR_TIMEOUT 등
```

해석:

```text
가장 최근 command 처리 상태를 SHM에서도 볼 수 있게 한 field다.
```

---

### 5. GPIO / event 상태 필드

#### `output_gpio_id=mcu_gpio0_8`

```text
현재 output target GPIO logical id
```

#### `output_state=0`

```text
현재 output GPIO cached state
0 = low
1 = high
```

#### `input_gpio_id=mcu_gpio0_6`

```text
현재 input target GPIO logical id
```

#### `input_state=1`

```text
현재 input sampled state
현재 SW1은 active-low라:
  1 = released
  0 = pressed
```

#### `event_count`

```text
button/GPIO event 누적 count
```

#### `last_event_type`

```text
마지막 event 종류
none / rising / falling / changed
```

#### `last_event_gpio_id`

```text
마지막 event가 발생한 GPIO logical id
```

#### `last_event_timestamp_us`

```text
마지막 event timestamp (us)
```

해석:

```text
button event가 들어왔는지, 마지막 입력 변화가 언제였는지 보는 용도다.
```

---

### 6. R5F 내부 온도센서 결과 필드

이 섹션은 **R5F가 직접 읽어 SHM에 기록한 값**이다.

#### `soc_temp0_valid`, `soc_temp1_valid`

```text
R5F가 해당 sensor 값을 정상적으로 읽고 변환했는지
1 = 유효
0 = invalid
```

#### `soc_temp0_raw`, `soc_temp1_raw`

```text
R5F가 VTM status register에서 읽은 10-bit raw code
```

중요:

```text
raw code 339는 "339도"가 아니다.
온도에 대응되는 가공 전 센서 code 값이다.
```

즉 흐름은 다음과 같다.

```text
실제 칩 온도
  -> VTM 센서 측정
  -> register에 raw code 기록
  -> R5F가 raw code read
  -> raw -> milli-Celsius 변환
```

#### `soc_temp0_millicelsius`, `soc_temp1_millicelsius`

```text
raw code를 Linux thermal driver와 같은 lookup 방식으로 변환한 값
단위는 milli-Celsius

예:
  43840 = 43.840C
```

#### `soc_temp0_last_error`, `soc_temp1_last_error`

```text
R5F temperature read 상태
예:
  OK
  UNAVAILABLE
  RANGE
```

해석:

```text
valid=1, last_error=OK 이면 그 시점 temperature 값은 정상으로 본다.
```

---

### 7. A53 Linux 기준값 필드

이 줄들은 **R5F SHM 값이 아니라 A53 Linux가 그 순간 직접 읽은 값**이다.

#### `linux_hwmon name=main0_thermal ... temp1_input_millicelsius=...`

```text
Linux hwmon의 main0_thermal 기준값
```

#### `linux_hwmon name=main1_thermal ... temp1_input_millicelsius=...`

```text
Linux hwmon의 main1_thermal 기준값
```

해석:

```text
R5F가 읽은 값이 Linux thermal driver 기준값과 어느 정도 맞는지 비교하는 reference line이다.
```

---

### 8. 비교(delta) 필드

#### `soc_temp0_delta_millicelsius`

```text
R5F SHM soc_temp0_millicelsius - Linux main0_thermal 값
```

#### `soc_temp1_delta_millicelsius`

```text
R5F SHM soc_temp1_millicelsius - Linux main1_thermal 값
```

해석:

```text
0이면 완전히 같은 값이다.
양수면 R5F 값이 Linux 기준보다 높다.
음수면 R5F 값이 Linux 기준보다 낮다.
```

실보드에서는 샘플 시점 차이 때문에 수백 mC 정도 차이가 날 수 있다.

---

## 어떻게 읽으면 되나

### 정상 상태의 빠른 체크 순서

1. `magic`, `version`, `abi_size`가 기대값인지 본다.
2. `seq`, `heartbeat`, `shm_update_count`가 계속 증가하는지 본다.
3. `last_error=OK`, `rpmsg_error_count=0`인지 본다.
4. GPIO/event 값이 현재 실험 상태와 맞는지 본다.
5. `soc_temp*_valid=1`, `soc_temp*_last_error=OK`인지 본다.
6. `linux_hwmon ...`와 `soc_temp*_delta_millicelsius`를 같이 본다.

### 한 줄 요약

```text
shm-status는
  "R5F가 SHM에 써 둔 상태 snapshot"
+ "A53 Linux가 그 시점에 직접 읽은 온도 기준값"
을 같이 보여주는 진단 출력이다.
```
