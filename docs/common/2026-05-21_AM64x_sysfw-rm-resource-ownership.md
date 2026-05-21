# AM64x SYSFW RM Resource Ownership 메모

- Date: 2026-05-21
- Board: AM64x common
- Category: `docs/common/`
- Status: Investigation
- Suggested repo path: `docs/common/2026-05-21_AM64x_sysfw-rm-resource-ownership.md`

## Summary

AM64x/K3 계열에서 R5F, M4F, A53 Linux가 SoC 내부 resource를 함께 사용하는 경우, 단순히 회로도와 Device Tree만 확인해서는 충분하지 않다. R5F가 GPIO interrupt, peripheral interrupt, DMA, ring, proxy 등 SoC 내부 공유 resource를 사용하려면 SYSFW Resource Management 설정에서 해당 host에게 resource가 허용되어야 한다.

이번 Phase 2의 `SW1 -> MCU_GPIO0_6 -> R5F GPIO interrupt` 이슈는 이 구조를 실제로 드러낸 사례다.

## Knowledge

### SYSFW / DMSC

SYSFW(System Firmware)는 TI K3 계열 SoC에서 system controller 역할을 하는 firmware 계층이다. AM64x에서는 DMSC-L이 SoC system controller로 동작하며 boot, security, clock/reset/power management 같은 핵심 서비스를 관리한다.

SYSFW binary 자체는 TI가 제공한다. 사용자는 일반적으로 SYSFW 내부 코드를 수정하지 않는다.

하지만 다음과 같은 SYSFW config는 보드와 시스템 설계에 따라 달라질 수 있다.

```text
board-cfg.yaml
pm-cfg.yaml
rm-cfg.yaml
sec-cfg.yaml
```

### RM config

`rm-cfg.yaml`은 Resource Management 설정이다.

이 파일은 다음과 같은 질문에 영향을 준다.

```text
어떤 host/core가 어떤 interrupt route를 요청할 수 있는가?
어떤 DMA/ring/proxy resource를 사용할 수 있는가?
어떤 peripheral resource range가 어떤 host에게 열려 있는가?
```

따라서 R5F가 GPIO interrupt를 사용하려면 R5F firmware 코드뿐 아니라 SYSFW RM 설정도 맞아야 한다.

### SoC 종속 / 보드 종속 / 시스템 설계 종속

```text
SoC 종속:
  interrupt router 구조
  GPIO controller instance
  R5F VIM
  SYSFW/TISCI API
  host ID / device ID / interrupt source ID

보드 종속:
  특정 신호가 어떤 SoC pin에 연결되었는가
  pull-up/pull-down 회로
  active-high/active-low
  debounce 회로

시스템 설계 종속:
  Linux가 해당 입력을 처리할지
  R5F가 해당 입력을 처리할지
  shared observation만 할지
  어떤 core가 interrupt owner가 될지
```

### Device Tree와 SYSFW RM의 차이

```text
Device Tree:
  Linux kernel에게 보드 장치 구성을 설명한다.
  Linux driver bind, pinctrl, interrupt property 등에 사용된다.

SYSFW RM config:
  SoC 내부 공유 resource 권한과 route allocation 정책에 관여한다.
  R5F/M4F/A53 등 host별 resource 사용 가능 여부에 영향을 준다.
```

R5F가 직접 peripheral 또는 interrupt를 소유하는 구조에서는 다음 세 가지를 모두 확인해야 한다.

```text
1. Linux가 이미 점유하고 있지 않은가?
2. SYSFW RM이 R5F host의 resource 요청을 허용하는가?
3. R5F firmware가 실제 pinmux/peripheral/interrupt를 올바르게 설정하는가?
```

## Decision

R5F-owned peripheral 또는 interrupt를 구현할 때는 항상 다음을 사전 확인한다.

```text
Board schematic
Device Tree / Linux ownership
SYSFW RM ownership
Boot image 반영 여부
R5F firmware 설정
```

## Assumption

- TI 기본 EVM boot image는 일반 Linux/SDK demo 중심 resource allocation을 기준으로 구성되어 있을 수 있다.
- 특정 board input을 R5F-owned interrupt로 가져오는 것은 기본 EVM 설정과 다를 수 있으므로 RM config 변경이 필요할 수 있다.
- `Sciclient_*` API 실패는 단순 driver bug가 아니라 SYSFW resource/permission 문제일 가능성을 항상 열어둬야 한다.

## Open Question

- 현재 사용 중인 SDK/U-Boot tree에서 `rm-cfg.yaml`의 resource entry가 어떤 host ID 기준으로 구성되어 있는지 별도 정리가 필요하다.
- R5F0_0, R5F0_1, R5F1_0, R5F1_1별 host ID와 interrupt route resource 범위를 정리해야 한다.
- GPIO interrupt, UART/I2C/SPI interrupt, DMA 사용 시 각각 어떤 RM entry를 확인해야 하는지 공통 체크리스트가 필요하다.

## Action Item

- `resource_ownership.md`에 Linux/R5F/SYSFW 관점 ownership 표를 추가한다.
- 각 Phase 문서에 SYSFW RM pre-check 항목을 포함한다.
- `rm-cfg.yaml` 변경 시 `combined-sysfw-cfg.bin`과 `tiboot3.bin` 재생성 및 boot partition 교체 절차를 문서화한다.
- `Sciclient_*` 실패 로그 패턴과 원인 분류표를 만든다.

## Commands

### U-Boot/SYSFW config source 확인 후보

```bash
find . -path '*am64x*' -name 'rm-cfg.yaml' -o -name 'board-cfg.yaml' -o -name 'pm-cfg.yaml' -o -name 'sec-cfg.yaml'
grep -R "MCU_GPIO\|GPIO\|intr\|irq\|host" board/ti/am64x/ -n
```

### Running DT에서 Linux ownership 확인

```bash
dtc -I fs -O dts /proc/device-tree > /tmp/running.dts
grep -n -i -E "gpio-keys|button|key|interrupt|mcu_gpio|gpio" /tmp/running.dts
```

## Verification Points

SYSFW/RM 관련 문제가 해결되었는지 판단할 때는 다음을 확인한다.

```text
1. 수정된 rm-cfg.yaml 기반 boot image로 부팅했는가?
2. R5F firmware의 Sciclient_gpioIrqSet 또는 유사 Sciclient API가 성공하는가?
3. interrupt route 설정 성공 로그가 R5F trace에 남는가?
4. 실제 hardware event에서 R5F ISR이 호출되는가?
```

## Suggested Repo Location

```text
docs/common/2026-05-21_AM64x_sysfw-rm-resource-ownership.md
```

## Suggested Commit Message

```text
docs: AM64x SYSFW RM resource ownership 개념 정리
```
