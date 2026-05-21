# SK-AM64B Phase 2: SW1 R5F GPIO IRQ 및 SYSFW RM 이슈 정리

- Date: 2026-05-21
- Board: SK-AM64B
- Category: `docs/boards/SK-AM64B/`
- Status: In progress / Investigation
- Suggested repo path: `docs/boards/SK-AM64B/2026-05-21_SK-AM64B_phase2-sw1-r5f-gpio-irq-sysfw-rm.md`
- Related common note: `docs/common/2026-05-21_AM64x_sysfw-rm-resource-ownership.md`
- Related setup note: `docs/setup/2026-05-21_AM64x_tiboot3-sysfw-rm-rebuild.md`

## Summary

Phase 2에서는 SK-AM64B 보드의 내장 Push Button `SW1`을 외부 입력 이벤트로 사용하고, 해당 입력을 R5F firmware가 GPIO interrupt로 감지한 뒤 A53 Linux app으로 RPMsg event를 전달하는 구조를 검증한다.

초기 계획은 R5F firmware와 A53 userspace app 수정 중심이었지만, 실제 구현 중 `Sciclient_gpioIrqSet` assert가 발생했다. 원인은 `SW1 -> MCU_GPIO0_6` 입력 interrupt를 R5F가 사용하려면 SoC 내부 interrupt route/resource가 SYSFW RM 설정에서 R5F host에게 허용되어야 하는데, 기존 boot image의 RM 설정에는 해당 권한이 없었기 때문이다.

따라서 이번 Phase 2는 단순 GPIO input interrupt 실험이 아니라, `SW1` 입력을 R5F-owned interrupt로 가져오기 위해 `rm-cfg.yaml`, `combined-sysfw-cfg.bin`, `tiboot3.bin`까지 포함하는 boot chain 수준의 BSP 리허설이 되었다.

## Context

SK-AM64B User Guide에는 보드에 `1x Push button for Interrupt SoC GPIO`가 있다고 명시되어 있다. Interrupt 섹션에서는 GPIO interrupt용 push button이 Main domain과 MCU domain GPIO pin 양쪽에 연결되어 있다고 설명한다.

이번 Phase 2의 목표 흐름은 다음과 같다.

```text
SW1 내장 버튼
  ↓
MCU_GPIO0_6 입력 변화
  ↓
MCU GPIO interrupt
  ↓
R5F VIM interrupt
  ↓
R5F ISR
  ↓
RPMsg event
  ↓
A53 Linux app 출력
```

이 흐름에서 실제 실패가 발생한 지점은 GPIO register access 자체가 아니라 `MCU_GPIO0_6 interrupt`를 R5F 쪽으로 routing하는 SYSFW RM resource/permission 단계였다.

## Knowledge

### GPIO value read와 GPIO interrupt routing은 다르다

GPIO 값을 polling으로 읽는 것과 GPIO interrupt를 R5F core까지 전달하는 것은 다른 문제다.

```text
GPIO value read:
  R5F firmware가 MCU_GPIO0_6 register 값을 읽음

GPIO interrupt routing:
  MCU_GPIO0_6 edge 발생
    ↓
  GPIO interrupt source
    ↓
  interrupt router / interrupt aggregator
    ↓
  R5F VIM interrupt input
    ↓
  R5F ISR
```

이번 문제는 `MCU_GPIO0_6` 핀 자체가 아니라, 해당 GPIO edge interrupt를 R5F interrupt input으로 연결하기 위한 SoC 내부 interrupt route resource 권한 문제였다.

### SYSFW는 버튼 자체가 아니라 SoC 내부 resource를 관리한다

SYSFW는 보드의 물리 버튼 `SW1`을 직접 아는 것이 아니다. SYSFW가 관리하는 대상은 SoC 내부의 resource이다.

예:

- interrupt router
- interrupt aggregator
- device clock/reset/power
- DMA/ring/proxy resource
- firewall/resource permission
- host별 resource allocation

따라서 더 정확한 표현은 다음과 같다.

```text
SW1의 물리 신호 소유권을 SYSFW가 가진다
```

가 아니라,

```text
SW1이 연결된 MCU_GPIO0_6의 interrupt를 R5F까지 전달하기 위한
SoC 내부 IRQ route/resource를 SYSFW RM이 관리한다
```

이다.

### Sciclient_gpioIrqSet assert의 의미

`Sciclient_gpioIrqSet`은 R5F firmware가 SYSFW에게 GPIO interrupt route 설정을 요청하는 경로로 이해해야 한다.

의미상 요청은 다음과 같다.

```text
R5F firmware:
  MCU_GPIO0_6에서 발생하는 interrupt를 R5F interrupt input으로 연결해줘.

SYSFW/RM:
  현재 boot-time RM 설정상 이 host에게 해당 route/resource를 줄 수 없음.

결과:
  Sciclient_gpioIrqSet 실패 또는 assert
```

즉 R5F firmware의 GPIO ISR 코드만의 문제가 아니라, boot-time SYSFW RM 설정까지 맞아야 동작한다.

### rm-cfg.yaml과 tiboot3.bin의 관계

이번에 핵심적으로 수정된 파일은 다음이다.

```text
board/ti/am64x/rm-cfg.yaml
```

이 파일은 SYSFW Resource Management 설정의 source 역할을 한다. 적용 흐름은 다음과 같다.

```text
rm-cfg.yaml
  ↓
combined-sysfw-cfg.bin
  ↓
tiboot3.bin
  ↓
Boot ROM / R5 SPL 단계에서 SYSFW에 로드
  ↓
부팅 중 실제 resource policy로 적용
```

따라서 `rm-cfg.yaml`만 수정하고 기존 `tiboot3.bin`으로 부팅하면 변경 사항은 실제 보드에 반영되지 않는다.

### Device Tree와 SYSFW RM은 역할이 다르다

```text
Device Tree:
  Linux kernel에게 보드 장치 구성을 설명한다.
  Linux가 어떤 장치를 어떤 driver로 bind할지 결정하는 데 사용된다.

SYSFW RM config:
  SoC 내부 resource를 어떤 host/core가 요청하고 사용할 수 있는지 결정한다.
  R5F interrupt route, DMA, ring, proxy 등 SoC 내부 공유 resource 권한에 영향을 준다.
```

R5F가 직접 peripheral interrupt를 소유하는 구조에서는 Device Tree만 봐서는 부족하다. Linux ownership과 SYSFW RM ownership을 모두 확인해야 한다.

## Decision

- Phase 2 input source는 점퍼선 self-test가 아니라 SK-AM64B 내장 Push Button `SW1`을 primary target으로 사용한다.
- `SW1`의 R5F 측 입력 경로는 `MCU_GPIO0_6` 기준으로 분석한다.
- Phase 2는 단순 firmware/app 수정 작업이 아니라, 필요 시 SYSFW RM 설정과 boot image까지 포함하는 BSP bring-up 작업으로 취급한다.
- R5F-owned input/interrupt를 사용하는 모든 후속 phase에서는 SYSFW/RM ownership 확인을 사전 항목으로 포함한다.

## Assumption

- `SW1`은 보드 회로상 Main domain GPIO와 MCU domain GPIO 양쪽에 연결되어 있으며, R5F에서 사용하려는 경로는 `MCU_GPIO0_6`이다.
- `Sciclient_gpioIrqSet` assert는 R5F firmware logic 자체의 일반 버그라기보다 SYSFW RM 설정상 interrupt route/resource 권한이 없어서 발생한 것으로 본다.
- 현재 수정한 `rm-cfg.yaml`이 반영된 `tiboot3.bin`으로 부팅해야 R5F GPIO interrupt 설정이 정상 동작할 수 있다.

## Open Question

- 현재 running boot image의 `tiboot3.bin`이 실제로 수정된 `rm-cfg.yaml` 기반으로 생성된 것인지 확인 필요.
- `SW1`이 Linux Device Tree에서 `gpio-keys` 또는 다른 input driver로 이미 점유되어 있는지 최종 확인 필요.
- `MCU_GPIO0_6` interrupt route에 필요한 정확한 SYSFW RM resource entry를 문서화할 필요가 있다.
- `SW1`이 active-low인지, debounce 회로가 어떤 방식인지 schematic 기준으로 최종 정리 필요.
- R5F firmware에서 ISR context와 RPMsg event 전송 context가 분리되어 있는지 확인 필요.

## Action Item

1. Phase 2 계획 문서에 `SYSFW/RM ownership pre-check` 절을 추가한다.
2. `resource_ownership.md`에 `SW1 / MCU_GPIO0_6 / R5F / Linux / SYSFW RM` ownership 표를 추가한다.
3. `firmware_deploy.md` 또는 별도 boot artifact 문서에 `rm-cfg.yaml` 변경 시 `tiboot3.bin` 재생성 절차를 추가한다.
4. 보드 부팅 후 Linux가 SW1 관련 GPIO를 점유하고 있는지 확인한다.
5. R5F trace에서 GPIO IRQ route 설정 성공, ISR 진입, RPMsg event 전송을 확인한다.

## Board Note

### SK-AM64B SW1 입력 경로

```text
SW1 Push Button
  ↓
board debounce / pull circuit
  ↓
MCU_GPIO0_6
  ↓
MCU GPIO interrupt
  ↓
R5F VIM
  ↓
R5F ISR
  ↓
RPMsg event
  ↓
A53 Linux app
```

### 보드/SoC/시스템 설계 관점 분리

```text
보드 종속:
  SW1이 어떤 회로와 어떤 SoC pin에 연결되어 있는가

SoC 종속:
  MCU_GPIO, interrupt router, R5F VIM, SYSFW RM 구조

시스템 설계 종속:
  SW1 interrupt를 Linux가 소유할지 R5F가 소유할지

빌드 산출물 종속:
  rm-cfg.yaml 변경 사항이 combined-sysfw-cfg.bin과 tiboot3.bin에 반영되었는지
```

## Commands

### Running Device Tree 확인

```bash
dtc -I fs -O dts /proc/device-tree > /tmp/running.dts
grep -n -i -E "gpio-keys|button|key|MCU_GPIO|GPIO1_59|gpio1" /tmp/running.dts
```

### Linux input/button 점유 확인

```bash
cat /proc/bus/input/devices
dmesg | grep -i -E "gpio-keys|button|key|input"
```

### GPIO line 확인

```bash
gpioinfo | grep -i -E "gpio|button|key|mcu"
```

### Remoteproc / RPMsg 확인

```bash
for r in /sys/class/remoteproc/remoteproc*; do
    echo "== $r =="
    cat $r/name 2>/dev/null
    cat $r/state 2>/dev/null
    cat $r/firmware 2>/dev/null
done

ls -l /dev/rpmsg*
ls -l /sys/bus/rpmsg/devices/
```

### R5F trace 확인

```bash
cat /sys/kernel/debug/remoteproc/remoteproc1/trace0
watch -n 0.5 'cat /sys/kernel/debug/remoteproc/remoteproc1/trace0'
```

## Verification Points

### 성공 기준

```text
1. 수정된 rm-cfg.yaml 기반 tiboot3.bin으로 부팅된다.
2. R5F firmware에서 Sciclient_gpioIrqSet assert가 발생하지 않는다.
3. SW1 버튼 입력 시 R5F GPIO ISR이 호출된다.
4. R5F trace에 pressed/released event가 출력된다.
5. A53 Linux app에서 RPMsg event가 실시간 출력된다.
```

### 실패 시 의심 지점

```text
1. 기존 tiboot3.bin으로 부팅 중
2. rm-cfg.yaml 수정 누락 또는 잘못된 resource entry
3. Linux가 SW1 GPIO를 이미 gpio-keys로 점유
4. pinmux가 GPIO input이 아님
5. interrupt trigger polarity 설정 오류
6. active-low 해석 오류
7. ISR 안에서 RPMsg 직접 전송
8. R5F firmware가 실제 새 이미지로 배포되지 않음
```

## Artifact

관련 source/build artifact:

```text
board/ti/am64x/rm-cfg.yaml
combined-sysfw-cfg.bin
tiboot3.bin
tispl.bin
u-boot.img
R5F firmware image
A53 r5ctl app
```

## Suggested Repo Location

```text
docs/boards/SK-AM64B/2026-05-21_SK-AM64B_phase2-sw1-r5f-gpio-irq-sysfw-rm.md
```

## Suggested Commit Message

```text
docs: SK-AM64B Phase 2 SW1 R5F IRQ와 SYSFW RM 이슈 정리
```
