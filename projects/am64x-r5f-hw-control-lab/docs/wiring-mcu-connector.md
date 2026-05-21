# MCU Connector Wiring Guide

## 목적

이 문서는 SK-AM64B의 MCU Connector 후보 pin에 외부 LED 또는 측정 장비를 연결하여 R5F GPIO control 결과를 확인하는 방법을 정리한다.

## MCU Connector 주요 Pin 후보

아래 표는 **현재 문서/회로도 기준 후보 정리**이다. 실제 배선 전에는 보드 silkscreen, User Guide, 회로도를 다시 대조한다.

| Pin 후보 | Net Name | 설명 |
|---:|---|---|
| 1 | `VCC_3V3_SYS` | 3.3V 전원, 100mA 제한 주의 |
| 5 | `MCU_GPIO0_8` | Phase 1 1차 GPIO output 후보 |
| 7 | `DGND` | GND 후보 |
| 10 | `MCU_GPIO0_6` | 대체 GPIO target 후보 |
| 11 | `MCU_GPIO0_7` | 대체 GPIO target 후보 |
| 14 | `MCU_GPIO0_9` | 대체 GPIO target 후보 |
| 15 | `DGND` | GND 후보 |
| 20 | `DGND` | GND 후보 |
| 27 | `DGND` | GND 후보 |

## 권장 확인 방법 1: 멀티미터

가장 안전한 첫 확인 방법이다.

```text
멀티미터 빨간 probe → GPIO target pin 후보
멀티미터 검은 probe → DGND 후보 pin
```

명령:

```bash
r5ctl gpio set 1
# 기대값: 약 3.3V

r5ctl gpio set 0
# 기대값: 약 0V
```

## 권장 확인 방법 2: 외부 LED

필요 부품:

```text
일반 LED 1개
저항 330Ω~1kΩ 1개
점퍼 와이어
```

연결:

```text
GPIO target pin 후보
  ── 저항 330Ω~1kΩ
  ── LED Anode
  ── LED Cathode
  ── DGND 후보 pin
```

명령:

```bash
r5ctl gpio set 1
# LED ON 기대

r5ctl gpio set 0
# LED OFF 기대

r5ctl gpio blink 5
# LED 5회 blink 기대
```

## 주의사항

- 저항 없이 LED를 GPIO와 GND 사이에 직접 연결하지 않는다.
- 3.3V 전원은 외부 부하 연결에 주의한다.
- LED 방향이 반대이면 켜지지 않을 수 있다.
- Pin 번호를 잘못 잡지 않도록 connector 방향을 반드시 확인한다.
- 전원/GND short가 발생하지 않도록 전원 OFF 상태에서 배선을 먼저 확인한다.

## 해석

이 연결을 통해 확인하는 것은 다음이다.

```text
A53 App command
  ↓
RPMsg
  ↓
R5F Firmware
  ↓
MCU GPIO Controller
  ↓
MCU Connector pin 후보 voltage change
```

즉, R5F가 실제 보드 외부 pin을 제어할 수 있는지 검증한다.
