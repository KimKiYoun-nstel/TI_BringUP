# AM64x `.NET` 기반 DTS 생성 근거 및 검증 가이드

## 0. 문서 목적

이 문서는 OrCAD 회로도에서 추출한 `.NET` 파일을 AM64x SysConfig pinmux DB와 조합하여 Linux DTS의 `pinctrl` 정보 및 기타 DTS 후보 정보를 생성할 때, `.NET`의 어떤 정보를 신뢰 근거로 사용할 수 있는지와 자동화 툴이 어떤 방식으로 동작해야 하는지를 정의한다.

이 문서는 실제 local repo의 자동화 스크립트가 다음 원칙을 제대로 반영하고 있는지 검증하기 위한 기준 문서다.

핵심 결론은 다음과 같다.

```text
.NET은 회로도 작성자의 NETNAME을 믿기 위한 파일이 아니다.
.NET은 OrCAD가 회로도 connectivity에서 추출한 RefDes-PinNumber-PinName 연결 정보를 사용하기 위한 입력이다.

AM6412 SoC symbol은 TI 제공/레퍼런스 symbol 기반이므로,
U1-<BALL> 및 AM6412-<PIN_NAME>은 net name보다 훨씬 강한 기준 정보로 취급한다.

pinctrl 생성은 NETNAME이 아니라,
U1 ball + AM6412 pin name + SysConfig DB의 ball/function/muxmode/offset 매칭을 기준으로 한다.
```

---

## 1. 전체 흐름에서 이 작업의 위치

AM64x 보드 브링업 전체 흐름에서 `.NET` 기반 DTS 생성은 다음 위치에 있다.

```text
회로도 / OrCAD 프로젝트
  -> .NET connectivity export
  -> board hardware fact 추출
  -> SysConfig DB와 SoC pinmux cross-check
  -> Linux DTS pinctrl fragment 생성
  -> controller/device 후보 DTS 생성
  -> unresolved/TODO/HW-review report 생성
  -> BSP 담당자가 최종 DTS 통합 및 bring-up 검증
```

즉 이 작업은 최종 production DTS를 사람이 검토 없이 완성하는 것이 아니라, 회로도 기반 hardware fact를 추출하고 Linux DTS에 반영 가능한 부분을 자동 생성하는 단계다.

---

## 2. `.NET` 파일의 구조 해석

`.NET`의 net block은 대략 다음 형태로 해석한다.

```text
(
NET_NAME
REFDES-PINNUMBER PARTTYPE-PINNAME ELECTRICAL_TYPE
REFDES-PINNUMBER PARTTYPE-PINNAME ELECTRICAL_TYPE
...
)
```

예시:

```text
(
I2C0_SCL
U1-A18 AM6412-I2C0_SCL PASSIVE
R313-1 0R-1 PASSIVE
R89-2 4.7k-2 PASSIVE
U14-6 AT24C512C-MAHM-E-SCL PASSIVE
)
```

해석:

```text
NET_NAME:
  I2C0_SCL

SoC 연결:
  U1-A18 AM6412-I2C0_SCL

같은 net에 연결된 외부 회로:
  R313-1 0R
  R89-2 4.7k pull-up
  U14-6 AT24C512C EEPROM SCL pin
```

중요한 점은 `NET_NAME`은 회로도 작성자가 붙인 label이고, `U1-A18 AM6412-I2C0_SCL`은 SoC symbol에서 export된 pin connectivity 정보라는 점이다.

---

## 3. `.NET` 정보의 신뢰도 계층

자동화 툴은 `.NET` 내부 정보를 동일한 신뢰도로 취급하면 안 된다. 아래 우선순위를 적용해야 한다.

| 정보 | 예 | 성격 | DTS 생성 신뢰도 |
|---|---|---|---|
| SoC RefDes | `U1` | 프로젝트 내 SoC reference | 높음, 단 SoC 식별 필요 |
| SoC pin number / ball | `A18`, `B21`, `D15` | AM6412 package ball / PCB footprint pad | 매우 높음 |
| SoC symbol pin name | `AM6412-I2C0_SCL`, `AM6412-UART0_RXD` | TI 제공 symbol 기반 pin name | 높음 |
| SysConfig DB | `A18 + I2C0_SCL -> 0x0260/mode0` | TI tool용 machine-readable pinmux DB | 매우 높음 |
| 같은 net의 connectivity | `U1-A18`과 `U14-6`이 같은 net | OrCAD connectivity 결과 | 높음 |
| 외부 부품 part type | `AT24C512C-MAHM-E`, `TPS2051BDBVR` | 부품 library/BOM 기반 | 중간~높음 |
| 외부 부품 pin name | `SCL`, `SDA`, `EN`, `RESETN` | 부품 symbol pin name | 중간~높음 |
| NETNAME | `I2C0_SCL`, `ABC`, `TEST_LED2` | 회로도 작성자 net label | 낮음~보조 |

자동화의 primary key는 반드시 다음 조합이어야 한다.

```text
U1 ball + AM6412 symbol pin name + SysConfig DB
```

`NETNAME`은 주석, evidence, GPIO 용도 추정, report 보조 정보로만 사용한다.

---

## 4. AM6412 SoC symbol 정보에 대한 전제

H/W 담당자 확인 결과:

```text
AM6412 SoC schematic symbol은 TI로부터 제공받은 개발보드/레퍼런스 symbol을 사용한다.
파란 박스 안의 pin number와 pin name은 사용자가 임의 수정하는 대상이 아니다.
```

따라서 다음 정보는 회로도 작성자의 자유 네이밍으로 취급하지 않는다.

```text
U1-A18
U1-B21
U1-D15
AM6412-I2C0_SCL
AM6412-MCU_PORZ
AM6412-UART0_RXD
```

이 정보는 다음 흐름의 결과로 본다.

```text
TI Datasheet pin table
  -> TI/reference OrCAD symbol
  -> board schematic
  -> OrCAD .NET export
```

따라서 local tool은 `NETNAME`이 아닌 SoC symbol line을 기준으로 분석해야 한다.

---

## 5. Datasheet와 SysConfig DB의 관계

AM64x Datasheet의 pin attribute table은 사람이 읽는 공식 pin/ball/mux 정보다.

예:

```text
BALL NUMBER: A18
SIGNAL NAME: I2C0_SCL
MUX MODE: 0
PADCONFIG address: ...
```

SysConfig DB는 이 정보를 자동화 툴이 읽을 수 있는 구조화 데이터로 제공한다.

즉 pinctrl 생성 관점에서 SysConfig DB는 Datasheet pinmux table의 machine-readable 대체 입력으로 사용할 수 있다.

SysConfig DB가 제공해야 하는 핵심 컬럼:

```text
ball
signal_name
mux_mode
control_register_offset / dts_offset
domain
linux_macro
```

예:

```text
A18 + I2C0_SCL -> offset 0x0260, muxmode 0, AM64X_IOPAD
B18 + I2C0_SDA -> offset 0x0264, muxmode 0, AM64X_IOPAD
D15 + UART0_RXD -> offset 0x0230, muxmode 0, AM64X_IOPAD
A9 + MCU_UART0_RXD -> offset 0x0028, muxmode 0, AM64X_MCU_IOPAD
```

단, SysConfig DB가 Datasheet 전체를 대체하는 것은 아니다.

SysConfig DB로 대체 가능한 영역:

```text
package ball
pin function / signal name
mux mode
pad control offset
MAIN/MCU/WKUP domain
Linux pinmux macro selection
```

SysConfig DB만으로 대체하지 않는 영역:

```text
전기적 특성
voltage rail 조건
DDR timing/training
USB/SerDes electrical details
power sequencing
reset timing
boot mode strap
external device behavior
```

---

## 6. pinctrl 생성의 원칙

Linux DTS의 pinctrl line은 다음 세 가지를 필요로 한다.

```text
1. Ball number
2. 선택된 signal/function
3. SysConfig DB에서 찾은 offset/muxmode/macro
```

예:

```text
.NET:
  U1-A18 AM6412-I2C0_SCL PASSIVE

SysConfig DB:
  ball=A18, signal_name=I2C0_SCL, dts_offset=0x0260, mux_mode=0, linux_macro=AM64X_IOPAD

DTS:
  AM64X_IOPAD(0x0260, PIN_INPUT_PULLUP, 0) /* (A18) I2C0_SCL */
```

이때 `I2C0_SCL` net block 첫 줄의 `NETNAME`은 primary source가 아니다. `NETNAME`이 `ABC`여도 아래처럼 SoC line이 유지되면 pinctrl 생성은 가능해야 한다.

```text
(
ABC
U1-A18 AM6412-I2C0_SCL PASSIVE
U14-6 AT24C512C-MAHM-E-SCL PASSIVE
)
```

---

## 7. `.NET` 실제 예시와 DTS 의미

### 7.1 I2C0 SCL/SDA

`.NET` 예시:

```text
(
I2C0_SCL
U1-A18 AM6412-I2C0_SCL PASSIVE
R313-1 0R-1 PASSIVE
R89-2 4.7k-2 PASSIVE
U14-6 AT24C512C-MAHM-E-SCL PASSIVE
)
(
I2C0_SDA
U1-B18 AM6412-I2C0_SDA PASSIVE
R315-1 0R-1 PASSIVE
R91-2 4.7k-2 PASSIVE
U14-5 AT24C512C-MAHM-E-SDA PASSIVE
)
```

자동화 판단:

```text
U1-A18 + AM6412-I2C0_SCL -> SysConfig match -> pinctrl 생성
U1-B18 + AM6412-I2C0_SDA -> SysConfig match -> pinctrl 생성
U14 AT24C512C가 SCL/SDA 모두에 연결 -> I2C0 child device 후보
R89/R91 4.7k -> pull-up 존재 evidence
```

DTS 생성 후보:

```dts
&main_pmx0 {
    main_i2c0_pins_default: main-i2c0-default-pins {
        pinctrl-single,pins = <
            AM64X_IOPAD(0x0260, PIN_INPUT_PULLUP, 0) /* (A18) I2C0_SCL */
            AM64X_IOPAD(0x0264, PIN_INPUT_PULLUP, 0) /* (B18) I2C0_SDA */
        >;
    };
};

&main_i2c0 {
    pinctrl-names = "default";
    pinctrl-0 = <&main_i2c0_pins_default>;
    status = "okay";

    /* STUB: address strap verification required */
    eeprom@51 {
        compatible = "atmel,24c512";
        reg = <0x51>;
    };
};
```

주의:

```text
pinctrl line은 U1 ball + pin name + SysConfig DB로 확정 가능하다.
I2C child node의 compatible/reg는 part DB/address strap resolver가 필요하다.
```

---

### 7.2 MCU_PORZ

`.NET` 예시:

```text
(
MCU_PORZ
U1-B21 AM6412-MCU_PORZ PASSIVE
U9-4 SN74LVC1G11DBVRG4-Y PASSIVE
R102-1 4.7k-1 PASSIVE
R272-1 0R-1 PASSIVE
)
```

자동화 판단:

```text
U1-B21 + AM6412-MCU_PORZ는 TI symbol 기반의 SoC reset pin connectivity다.
그러나 MCU_PORZ는 Linux pinctrl AM64X_IOPAD 생성 대상이 아니다.
이 정보는 reset/power-on-reset hardware fact로 report해야 한다.
```

DTS 처리:

```text
pinctrl.dtsi에 AM64X_IOPAD 생성하지 않는다.
reset/power sequencing 또는 board hardware fact report에 기록한다.
```

---

### 7.3 SOC UART0 RX/TX

`.NET` 예시:

```text
(
SOC_UART0_RXD
U1-D15 AM6412-UART0_RXD PASSIVE
R240-1 33-1 PASSIVE
)
(
SOC_UART0_RXD_ECI
R241-2 33-2 PASSIVE
U30-13 CP2105-F01-GM-TXD_ECI PASSIVE
)
```

주의:

```text
R240/R241 같은 series resistor 때문에 net이 split될 수 있다.
단순 same-net 분석만으로 U1-D15와 U30-13이 직접 같은 net에 있다고 나오지 않을 수 있다.
0R/33R series resistor chain resolver가 있으면 연결을 이어서 해석할 수 있다.
```

pinctrl 판단:

```text
U1-D15 AM6412-UART0_RXD -> SysConfig DB match -> AM64X_IOPAD 생성 가능
```

DTS 후보:

```dts
&main_pmx0 {
    main_uart0_pins_default: main-uart0-default-pins {
        pinctrl-single,pins = <
            AM64X_IOPAD(0x0230, PIN_INPUT, 0)  /* (D15) UART0_RXD */
            AM64X_IOPAD(0x0234, PIN_OUTPUT, 0) /* (C16) UART0_TXD */
        >;
    };
};

&main_uart0 {
    pinctrl-names = "default";
    pinctrl-0 = <&main_uart0_pins_default>;
    status = "okay";
};
```

---

### 7.4 TEST_LED2 / alternate function / GPIO 주의

`.NET` 예시:

```text
(
TEST_LED2
U1-A7 AM6412-MCU_SPI1_CS0 PASSIVE
R96-1 10k-1 PASSIVE
Q2-1 BSS138LT3G-G PASSIVE
)
```

중요한 주의:

```text
SoC symbol pin name이 MCU_SPI1_CS0이라고 해서 실제 DTS function이 반드시 SPI CS라는 뜻은 아니다.
회로 용도가 LED/FET/GPIO이면 해당 ball을 GPIO mux mode로 사용해야 할 수 있다.
```

자동화 정책:

```text
일반 peripheral pin name과 net/external circuit 용도가 일치하면 mode0 또는 해당 signal로 pinctrl 생성 가능.
하지만 LED/RESET/INT/EN 같은 GPIO 용도 후보는 GPIO resolver 또는 board policy 확인 필요.
```

즉 `U1-A7 AM6412-MCU_SPI1_CS0`는 다음 두 후보를 가질 수 있다.

```text
후보 1: MCU_SPI1_CS0 기능으로 사용
후보 2: GPIO 기능으로 사용하여 TEST_LED2 제어
```

이 경우 자동화 툴은 무조건 SPI pinctrl을 생성하면 안 된다. `GPIO_CANDIDATE` 또는 `ALT_FUNCTION_REVIEW`로 분류해야 한다.

---

## 8. NO_OFFSET / non-pinctrl 분류 원칙

SysConfig DB 매칭 결과 `control_register_offset` 또는 `dts_offset`이 없거나 `NO_OFFSET`으로 분류되는 항목은 모두 오류가 아니다.

분류 기준:

```text
PINMUX_DTS:
  AM64X_IOPAD / AM64X_MCU_IOPAD 생성 대상

CONTROLLER_DTS:
  pinctrl line은 만들지 않지만 controller node로 표현되는 대상

NON_PINCTRL_HW:
  Linux pinctrl 대상이 아닌 hardware fact

PRE_LINUX_CONFIG:
  Linux 전에 SPL/U-Boot/firmware에서 처리되는 대상

OUT_OF_SCOPE:
  power/gnd/analog/passive/mechanical 등 DTS 직접 대상 아님

UNMATCHED_OR_CONFLICT:
  공식 DB와 매칭 실패 또는 충돌. 사람 확인 필요
```

예:

```text
DDR0:
  Linux pinctrl 대상 아님. SPL/U-Boot DDR config 영역.

USB0:
  AM64X_IOPAD pinmux line 대상 아님. USB controller/PHY node 영역.

SERDES0:
  일반 pinctrl 대상 아님. SerDes/PHY/protocol 설정 영역.

MCU_OSC0_XI:
  oscillator input. pinctrl 대상 아님. clock hardware fact/report 대상.

MMC0:
  Linux DTS 대상이지만 AM64X_IOPAD pinctrl line 없이 &sdhci0 controller node 중심으로 표현될 수 있음.
```

---

## 9. DTS 정보의 A/B/C 분류

자동화 툴은 DTS 정보를 다음 세 가지로 구분해야 한다.

### A. 회로도 + SysConfig DB로 거의 확정 가능한 정보

```text
SoC ball
SoC pin function
mux mode
pad offset
linux macro
일반 UART/I2C/SPI/MCAN/GPIO 후보 pinctrl
```

출력:

```text
generated/linux/*-pinmux.dtsi
```

### B. 회로도에서 유도 가능하지만 resolver/부품 DB가 필요한 정보

```text
I2C child device compatible/reg
SPI device compatible/chip-select
GPIO active-high/active-low
Ethernet PHY address/reset/interrupt/delay
MMC bus-width/removable/cd/wp
USB maximum-speed/VBUS/connector
regulator voltage/enable GPIO
```

출력:

```text
generated/linux/*-devices.stub.dtsi
reports/b_resolver_required.md
reports/questions_for_hw.md
```

### C. 회로도 사실이 아니라 BSP/Linux 운용 정책인 정보

```text
chosen/stdout-path
aliases
status okay/disabled 정책
I2C clock-frequency
USB dr_mode
regulator always-on/boot-on
remoteproc reserved-memory
boot/rootfs policy
```

출력:

```text
config/board_policy.yaml
reports/policy_decision_log.md
```

---

## 10. 자동화 툴이 반드시 지켜야 할 규칙

### Rule 1. NETNAME을 primary key로 사용하지 말 것

금지:

```text
if NETNAME == "I2C0_SCL": generate I2C0_SCL pinmux
```

허용:

```text
if U1-A18 AM6412-I2C0_SCL and SysConfig has A18/I2C0_SCL:
    generate I2C0_SCL pinmux
```

NETNAME은 evidence/comment/hint로만 사용한다.

---

### Rule 2. U1 SoC 식별을 먼저 할 것

툴은 먼저 SoC reference를 식별해야 한다.

검증 항목:

```text
U1 component PARTTYPE이 AM6412/AM64x 계열인가?
U1 pin numbers가 ALV package ball set과 매칭되는가?
U1 pin names가 SysConfig DB의 signal_name 목록과 높은 비율로 매칭되는가?
```

---

### Rule 3. SysConfig DB와 cross-check할 것

각 SoC pin line에 대해 다음을 수행한다.

```text
Input:
  ball = A18
  symbol_pin_name = I2C0_SCL

Lookup:
  SysConfig DB where ball=A18 and signal_name=I2C0_SCL

If found:
  matched -> pinctrl candidate

If ball found but signal not found:
  conflict_or_alt_function_review

If ball not found:
  invalid_symbol_or_package_mismatch
```

---

### Rule 4. alternate function/GPIO 가능성을 분리할 것

SoC symbol pin name은 신뢰 가능하지만, 항상 최종 mux function을 의미하지는 않는다.

특히 다음 net name 또는 외부 회로는 GPIO/alternate function 후보로 분류한다.

```text
*_LED*
*_RESET*
*_RST*
*_INT*
*_EN*
*_PWR*
*_OE*
*_STAT*
*_FAULT*
```

이 경우 툴은 다음 중 하나를 해야 한다.

```text
- GPIO resolver로 실제 GPIO mux mode를 선택
- board_policy.yaml에서 function override를 요구
- ALT_FUNCTION_REVIEW report에 기록
```

무조건 SoC symbol pin name의 mode0 pinctrl을 생성하면 안 된다.

---

### Rule 5. NO_OFFSET을 오류로만 보지 말 것

`NO_OFFSET` 또는 offset 없음은 다음 중 하나일 수 있다.

```text
정상 non-pinctrl hardware:
  DDR0, USB0, SERDES0, OSC

controller-only DTS 대상:
  MMC0 등

진짜 오류:
  일반 UART/I2C/SPI/GPIO/MCAN pin인데 offset이 없는 경우
```

따라서 prefix/type 기반 재분류가 필요하다.

---

### Rule 6. confidence와 evidence를 출력할 것

각 생성 결과에는 왜 생성했는지 근거를 남겨야 한다.

예:

```text
signal: I2C0_SCL
ball: A18
net: I2C0_SCL
source_line: U1-A18 AM6412-I2C0_SCL PASSIVE
sysconfig_match: A18/I2C0_SCL/0x0260/mode0/AM64X_IOPAD
confidence: HIGH
```

---

## 11. 권장 산출물

local tool은 최소 다음 산출물을 생성해야 한다.

```text
reports/soc_pin_net_table.csv
reports/pinmux_lookup_report.csv
reports/peripheral_inventory.csv
reports/non_pinctrl_hardware_facts.md
reports/alt_function_review.md
reports/unmatched_or_conflict_report.md
reports/questions_for_hw.md

generated/linux/k3-am6412-custom-pinmux.dtsi
generated/linux/k3-am6412-custom-controllers.dtsi
generated/linux/k3-am6412-custom-devices.stub.dtsi
```

---

## 12. soc_pin_net_table.csv 필수 컬럼

```csv
net_name,refdes,ball_or_pin,part_type,pin_name,electrical_type,connected_items,classification,evidence
```

SoC pin 기준으로는 다음 컬럼이 권장된다.

```csv
soc_refdes,soc_part,ball,symbol_pin_name,net_name,connected_parts,connected_pin_names
```

예:

```csv
U1,AM6412,A18,I2C0_SCL,I2C0_SCL,"R313,R89,U14","0R,4.7k,AT24C512C-SCL"
```

---

## 13. pinmux_lookup_report.csv 필수 컬럼

```csv
ball,symbol_pin_name,net_name,sysconfig_signal,offset,mux_mode,linux_macro,domain,result,confidence,reason
```

예:

```csv
A18,I2C0_SCL,I2C0_SCL,I2C0_SCL,0x0260,0,AM64X_IOPAD,MAIN,MATCHED,HIGH,"ball+symbol pin matched SysConfig DB"
B21,MCU_PORZ,MCU_PORZ,,,,,NON_PINCTRL_HW,HIGH,"reset/POR pin, not Linux pinctrl target"
A7,MCU_SPI1_CS0,TEST_LED2,,,,,ALT_FUNCTION_REVIEW,MEDIUM,"net/external circuit indicates LED/GPIO usage"
```

---

## 14. 로컬 툴 검증 체크리스트

### 14.1 SoC symbol quality gate

```text
[ ] U1이 AM6412로 식별되는가?
[ ] U1 pin number가 AM64x ALV package ball 목록과 매칭되는가?
[ ] U1 symbol pin name이 SysConfig DB의 해당 ball signal list와 매칭되는가?
[ ] conflict count가 0 또는 검토 가능한 수준인가?
[ ] NETNAME 없이도 주요 pinctrl 후보가 생성되는가?
```

### 14.2 pinctrl generation gate

```text
[ ] I2C0_SCL A18 -> 0x0260 mode0 AM64X_IOPAD 생성되는가?
[ ] I2C0_SDA B18 -> 0x0264 mode0 AM64X_IOPAD 생성되는가?
[ ] UART0_RXD D15 -> 0x0230 mode0 AM64X_IOPAD 생성되는가?
[ ] UART0_TXD C16 -> 0x0234 mode0 AM64X_IOPAD 생성되는가?
[ ] MCU_UART0_RXD A9 -> 0x0028 mode0 AM64X_MCU_IOPAD 생성되는가?
[ ] MCU_UART0_TXD A8 -> 0x002c mode0 AM64X_MCU_IOPAD 생성되는가?
```

### 14.3 NETNAME independence gate

```text
[ ] workflow helper가 NETNAME 문자열 직접 비교로 pinctrl을 생성하지 않는가?
[ ] U1-<BALL> AM6412-<PIN_NAME> 기반으로 SysConfig lookup을 수행하는가?
[ ] NETNAME이 다르더라도 동일한 SoC line이면 같은 pinctrl을 생성할 수 있는 구조인가?
```

### 14.4 alternate function gate

```text
[ ] TEST_LED2처럼 symbol pin name과 실제 용도가 다를 수 있는 항목을 review로 분류하는가?
[ ] LED/RESET/INT/EN/PWR 계열 net을 무조건 mode0 function으로 생성하지 않는가?
[ ] board_policy.yaml 또는 override rule로 실제 mux function을 지정할 수 있는가?
```

### 14.5 non-pinctrl gate

```text
[ ] DDR0을 Linux pinctrl로 생성하지 않는가?
[ ] MCU_PORZ/RESET/OSC를 pinctrl로 생성하지 않는가?
[ ] USB0/SERDES0를 AM64X_IOPAD pinmux로 생성하지 않고 controller/PHY/report로 분류하는가?
[ ] MMC0는 pinmux line이 아닌 controller node 후보로 분류 가능한가?
```

---

## 15. 툴 동작 판단 기준

툴이 올바르게 구현되었다면 다음 특성을 가져야 한다.

```text
1. NETNAME 변경에 강해야 한다.
2. U1 ball + symbol pin name + SysConfig DB 기반으로 pinctrl을 생성해야 한다.
3. SysConfig DB와 충돌하는 항목은 자동 생성하지 않고 conflict로 분류해야 한다.
4. NO_OFFSET을 단순 오류가 아니라 non-pinctrl/controller-only/pre-linux 영역으로 재분류해야 한다.
5. alternate function/GPIO 후보를 무조건 mode0 pinctrl로 생성하지 않아야 한다.
6. DTS에 생성한 모든 line의 evidence를 report에 남겨야 한다.
7. 확정 불가능한 B/C 항목은 TODO 또는 questions_for_hw.md로 남겨야 한다.
```

---

## 16. 최종 정리

이 프로젝트에서 `.NET`은 다음 의미로 사용한다.

```text
.NET은 회로도 작성자가 지은 NETNAME을 신뢰하기 위한 파일이 아니다.
.NET은 TI 제공 AM6412 symbol에서 나온 U1 ball/pin name과 OrCAD connectivity를 추출하기 위한 파일이다.
```

pinctrl 생성의 핵심 근거:

```text
U1-<BALL> AM6412-<PIN_NAME>
  + SysConfig DB의 ball/signal/muxmode/offset/macro
```

DTS 자동화에서 `.NET`의 가장 신뢰할 수 있는 정보:

```text
U1 SoC pin이 어떤 net에 연결되어 있는가
그 pin의 package ball은 무엇인가
그 pin의 TI symbol pin name은 무엇인가
그 net에 어떤 외부 부품 pin이 연결되어 있는가
```

DTS 자동화에서 가장 조심해야 할 정보:

```text
NETNAME
GPIO/alternate function 용도
I2C address strap
GPIO polarity
PHY strap/delay
USB role
regulator policy
```

따라서 local tool 검증의 핵심은 다음 한 줄이다.

```text
툴이 NETNAME 기반 문자열 매칭기가 아니라,
U1 ball + TI symbol pin name + SysConfig DB cross-check 기반 hardware fact classifier로 동작하는가?
```
