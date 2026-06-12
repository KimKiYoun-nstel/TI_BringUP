# SBL OSPI Linux Clean Workspace Replay

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` early-boot 작업을
clean workspace에서 다시 재구성할 때의 현재 기준 절차를 정리한다.

이 문서의 목표는 다음 둘이다.

1. LPDDR4 본질 수정 자산을 어떤 순서로 반영할지 고정
2. temporary debug marker 없이 clean source base를 다시 만드는 절차를 남김

## 현재 clean replay 기준

현재 clean replay는 다음 두 자산만 workspace에 반영하는 것을 기준으로 한다.

### 1. LPDDR4 standalone asset

- `bsp/mcu-plus/syscfg/board_ddrReginit_sk_am64b_lpddr4.h`

역할:

- SK-AM64B 실보드 LPDDR4와 일치하는 `board_ddrReginit.h`
- early-boot root cause fix

### 2. clean syscfg delta patch

- `bsp/mcu-plus/patches/0002-am64x-sbl-ospi-linux-keep-lp4-dual-boot-workspace-base.patch`

역할:

- `sbl_ospi_linux` example의 `APPIMAGE` DDR window를
  `NonCached + no-exec`로 유지

## helper script

현재 repo에는 위 두 자산을 workspace에 반영하는 helper가 있다.

```bash
./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh --apply
```

검증만 하려면:

```bash
./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh --check
```

## 권장 replay 순서

### 1. env source

```bash
source tools/env/mcu-plus-sdk-am64x-12.00.00.env
```

### 2. workspace 존재 확인

현재 기준 workspace root:

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27
```

### 3. clean LP4 base 반영

```bash
./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh --apply
```

### 4. SBL example build 확인

```bash
./tools/build/build-mcu-plus-example.sh make \
  examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang \
  release
```

필요 시 artifact 정리:

```bash
make -C workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang scrub \
  MCU_PLUS_SDK_PATH="$MCU_PLUS_SDK_PATH"
```

## replay 후 기대 상태

workspace source diff 기준으로 남아야 하는 것은 다음 둘이다.

1. `source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h`
2. `examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/example.syscfg`

즉 `main.c`, `ddr.c/h`, `bootloader_mcelf.c`, `bootloader_soc.c/h` 같은
temporary debug marker/diag source delta는 clean replay 기준에 포함하지 않는다.

## 현재 해석

현재 `SBL OSPI Linux` early-boot 작업에서 clean replay 기준은 다음과 같다.

```text
LPDDR4 reginit asset
  + clean syscfg delta
  = current clean workspace base
```

이후 R5F firmware behavior 또는 Linux RPMsg app 정합성 작업은
이 clean base 위에서 별도 task로 진행한다.
