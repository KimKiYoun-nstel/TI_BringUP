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
