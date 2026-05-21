# Resource Ownership

## 목적

이 문서는 SK-AM64B에서 A53 Linux와 R5F firmware가 동시에 동작하는 상황에서, 어떤 장치를 누가 소유하고 있는지 Phase 1 기준으로 정리한다.

R5F가 H/W를 직접 제어하려면 Linux가 이미 해당 peripheral 또는 pin을 사용하고 있지 않은지 확인해야 한다. 동일 peripheral을 A53 Linux와 R5F가 동시에 직접 제어하면 충돌 가능성이 있다.

## 현재 확인된 Resource Ownership

| Resource | 현재 상태 | 소유자 판단 | Phase 1 사용 여부 |
|---|---|---|---|
| `remoteproc` / `78000000.r5f` | running | R5F 실험 대상 | 사용 |
| RPMsg `rpmsg_chrdev` | 생성됨 | A53 ↔ R5F 통신 | 사용 |
| `trace0` | 존재 | R5F log 확인 | 사용 |
| `ttyS2` / `2800000.serial` | Linux console | A53 Linux | R5F 사용 금지 |
| `ttyS3` / `30028000.serial` | Linux serial device 가능성 | A53 Linux 가능성 | 보류 |
| I2C0 | EEPROM/PMIC/Board ID 관련 | A53 Linux | 사용 금지 |
| I2C1 | LED driver, IO expander, temp sensor | A53 Linux | 직접 사용 금지 |
| TPIC2810 LED driver | Linux LED subsystem | A53 Linux | Phase 1 제외 |
| PCA9538 IO expander | Ethernet reset, SD enable, RPI power 등 | A53 Linux / regulator | 사용 금지 |
| CPSW Ethernet | `eth0` up | A53 Linux | Phase 1 제외 |
| MCU GPIO0 | MCU domain GPIO | R5F 후보 | Phase 1 사용 |
| PRU Header | PRU_ICSSG 신호 | 미사용/추후 후보 | Phase 1 제외 |
| User Expansion Header | MAIN domain 확장 신호 | Linux와 충돌 가능성 | 보류 |
| cTI Header | JTAG debug | 디버깅용 | H/W 제어용 아님 |
| Test Automation Header | 전원/리셋/부트모드 자동 제어 | 테스트 장비용 | 건드리지 않음 |

## Phase 1에서 안전하게 사용할 후보

아래 표는 **회로도/기존 문서 기준 후보 정리**이며, 최종 실측 전까지는 connector-level 확정값으로 단정하지 않는다.

| MCU Connector Pin 후보 | Net Name | 용도 |
|---:|---|---|
| 5 | `MCU_GPIO0_8` | 1차 GPIO output target 후보 |
| 10 | `MCU_GPIO0_6` | 대체 GPIO output target 후보 |
| 11 | `MCU_GPIO0_7` | GPIO input/output 후보 |
| 14 | `MCU_GPIO0_9` | GPIO input/output 후보 |
| 9 | `TEST_LED2` / `MCU_GPIO0_5` 가능성 | 회로도 확인 후 사용 여부 판단 |

## 사용 금지 또는 보류 대상

### 내장 Industrial LED

현재 Linux LED subsystem이 소유하고 있으므로 R5F 직접 제어는 Phase 1에서 제외한다.

R5F가 직접 제어하려면 다음 작업이 필요하다.

```text
1. Linux Device Tree에서 LED driver 제거 또는 disable
2. I2C1 bus ownership을 R5F로 이전
3. R5F firmware에서 TPIC2810 제어 코드 구현
4. Linux와 I2C1 충돌이 없는지 검증
```

### Ethernet

현재 `eth0`가 A53 Linux에서 사용 중이다. R5F Ethernet/LwIP/TSN 실험은 다음 조건을 만족할 때 별도 Phase로 진행한다.

```text
1. A53 Linux의 CPSW 사용 중지 또는 port 분리
2. R5F가 사용할 Ethernet peripheral 명확화
3. CPSW/ICSSG ownership 결정
4. PHY reset, MDIO, pinmux, DMA 설정 확인
```

### Test Automation Header

전원, POR, warm reset, bootmode control 신호가 포함되어 있다. 실수로 건드리면 보드가 reset/powerdown될 수 있으므로 Phase 1에서는 사용하지 않는다.

## 추가 확인 명령

```bash
cat /proc/cmdline
dmesg | grep -iE "tty|serial|uart|i2c|gpio|led|pwm|cpsw|mdio|phy|remoteproc|rpmsg"
ls -l /dev/rpmsg*
ls -l /sys/bus/rpmsg/devices/
ls /sys/kernel/debug/remoteproc/
gpioinfo
ls /sys/class/leds/
ls /sys/bus/i2c/devices/
```
