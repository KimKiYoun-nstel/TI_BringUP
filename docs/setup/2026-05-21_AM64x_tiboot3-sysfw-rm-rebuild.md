# AM64x tiboot3.bin SYSFW RM Config Rebuild 메모

- Date: 2026-05-21
- Board: AM64x common / SK-AM64B 적용 사례
- Category: `docs/setup/`
- Status: Investigation
- Suggested repo path: `docs/setup/2026-05-21_AM64x_tiboot3-sysfw-rm-rebuild.md`
- Related board note: `docs/boards/SK-AM64B/2026-05-21_SK-AM64B_phase2-sw1-r5f-gpio-irq-sysfw-rm.md`

## Summary

SK-AM64B Phase 2에서 `SW1 -> MCU_GPIO0_6` interrupt를 R5F가 직접 사용하려고 하자 `Sciclient_gpioIrqSet` assert가 발생했다. 원인은 R5F firmware 코드만의 문제가 아니라, boot-time SYSFW RM config에 해당 interrupt route/resource가 R5F host에게 허용되어 있지 않았기 때문이다.

이에 따라 `board/ti/am64x/rm-cfg.yaml`을 수정하고, 이를 반영한 `combined-sysfw-cfg.bin`과 `tiboot3.bin`을 다시 생성해야 했다.

## Context

AM64x boot chain에서 SYSFW config는 일반 Linux rootfs나 R5F firmware file과 별개로, 매우 이른 부팅 단계에서 로드된다. 따라서 SYSFW RM 설정을 바꿨다면 단순히 R5F firmware만 교체해서는 반영되지 않는다.

개념 흐름은 다음과 같다.

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

## Knowledge

### tiboot3.bin의 의미

AM64x에서 `tiboot3.bin`은 Boot ROM 이후 매우 이른 단계에서 사용되는 boot image이다. 이 안에는 R5 SPL과 SYSFW 및 SYSFW configuration이 포함될 수 있다.

이번 이슈에서 핵심은 `u-boot.img` 자체의 command line이나 Linux DTB가 아니라, `tiboot3.bin`에 포함되는 SYSFW RM config였다.

### combined-sysfw-cfg.bin의 의미

`combined-sysfw-cfg.bin`은 SYSFW configuration들을 하나로 묶은 binary로 이해하면 된다.

일반적으로 source는 다음 계열의 YAML config이다.

```text
board-cfg.yaml
pm-cfg.yaml
rm-cfg.yaml
sec-cfg.yaml
```

이번 Phase 2에서 중요한 것은 `rm-cfg.yaml`이다.

### rm-cfg.yaml 수정이 필요한 경우

다음과 같은 상황에서는 R5F firmware만 수정해서는 부족할 수 있다.

```text
R5F가 GPIO interrupt를 직접 받는다
R5F가 peripheral interrupt를 직접 받는다
R5F가 DMA/ring/proxy resource를 직접 사용한다
R5F가 Linux와 resource ownership을 나눠 가진다
Sciclient_* API가 resource/permission 관련 실패를 낸다
```

이때는 `rm-cfg.yaml`을 확인하고, 수정 후 boot image를 다시 만들어야 한다.

## Decision

- `rm-cfg.yaml`이 변경되면 반드시 `combined-sysfw-cfg.bin`과 `tiboot3.bin` 재생성 여부를 확인한다.
- R5F-owned hardware interrupt 개발에서는 `tiboot3.bin`이 실제로 교체되었는지 boot partition과 boot log 기준으로 검증한다.
- `tispl.bin`, `u-boot.img`도 pipeline 일관성을 위해 함께 배포할 수 있지만, 이번 SYSFW RM 이슈의 핵심 산출물은 `tiboot3.bin`이다.

## Assumption

- 현재 빌드 파이프라인은 TI U-Boot tree 또는 Processor SDK 기반으로 `tiboot3.bin`, `tispl.bin`, `u-boot.img`를 생성한다.
- SK-AM64B는 SD card boot partition에 `tiboot3.bin`, `tispl.bin`, `u-boot.img`를 배치하여 부팅한다.
- `rm-cfg.yaml` 변경분이 실제 target boot partition에 반영되지 않으면 동일한 `Sciclient_gpioIrqSet` 실패가 반복될 수 있다.

## Open Question

- 현재 로컬 repo의 정확한 U-Boot build command와 output directory를 문서화해야 한다.
- `combined-sysfw-cfg.bin` 생성 command 또는 build log에서 어떤 config들이 포함되는지 확인해야 한다.
- boot log에서 수정된 `tiboot3.bin` 사용 여부를 판별할 수 있는 timestamp/hash 기준을 정해야 한다.

## Action Item

1. 로컬 U-Boot build pipeline에서 `rm-cfg.yaml` 변경 후 어떤 target을 다시 빌드해야 하는지 명령을 확정한다.
2. 생성된 `tiboot3.bin`, `tispl.bin`, `u-boot.img`의 `sha256sum`을 기록한다.
3. target boot partition에 복사 후 `sync && reboot`를 수행한다.
4. UART boot log에서 U-Boot SPL build timestamp를 확인한다.
5. R5F firmware에서 `Sciclient_gpioIrqSet` assert가 사라졌는지 확인한다.

## Commands

### Build artifact hash 기록

```bash
sha256sum tiboot3.bin tispl.bin u-boot.img
```

### Board로 boot artifact 배포

```bash
scp tiboot3.bin tispl.bin u-boot.img root@<board-ip>:/run/media/boot-mmcblk1p1/
ssh root@<board-ip> "sync && reboot"
```

### Board boot partition 확인

```bash
ssh root@<board-ip> "cd /run/media/boot-mmcblk1p1 && ls -al && sha256sum tiboot3.bin tispl.bin u-boot.img"
```

### R5F trace 확인

```bash
cat /sys/kernel/debug/remoteproc/remoteproc1/trace0
```

## Verification Points

### 성공 기준

```text
1. 수정된 rm-cfg.yaml이 build input으로 사용되었다.
2. combined-sysfw-cfg.bin이 재생성되었다.
3. tiboot3.bin이 재생성되었다.
4. target boot partition의 tiboot3.bin이 새 파일로 교체되었다.
5. 재부팅 후 R5F firmware에서 Sciclient_gpioIrqSet assert가 발생하지 않는다.
6. SW1 입력에 의해 R5F GPIO ISR이 호출된다.
```

### 실패 시 의심 지점

```text
1. rm-cfg.yaml은 수정했지만 tiboot3.bin을 재빌드하지 않음
2. tiboot3.bin은 재빌드했지만 SD boot partition에 복사하지 않음
3. 다른 boot media 또는 다른 partition에서 부팅 중
4. boot partition에 파일명은 같지만 이전 binary가 남아 있음
5. rm-cfg.yaml resource entry가 잘못됨
6. R5F firmware가 예상한 core/host와 rm-cfg.yaml의 host 설정이 다름
```

## Artifact

관련 artifact:

```text
board/ti/am64x/rm-cfg.yaml
combined-sysfw-cfg.bin
tiboot3.bin
tispl.bin
u-boot.img
UART boot log
R5F trace0 log
```

## Suggested Repo Location

```text
docs/setup/2026-05-21_AM64x_tiboot3-sysfw-rm-rebuild.md
```

## Suggested Commit Message

```text
docs: AM64x SYSFW RM 변경 시 tiboot3 재빌드 절차 정리
```
