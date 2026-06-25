# SK-AM64B SBL OSPI Linux Source Bootstrap Chain

## 목적

이 문서는 이 프로젝트에서 말하는 `source bootstrap chain`을 고정한다.

범위:

```text
workspace source tree -> partial build output
```

즉 이 문서는 최종 flash image set 자체보다,
그 전에 재사용 가능한 partial build output을 어떻게 다시 만드는지를 다룬다.

## 현재 source bootstrap 대상

### 1. TF-A `BL31`

source:

- `workspace/trusted-firmware-a-2.14+git`

output:

- `workspace/trusted-firmware-a-2.14+git/build/k3/lite/release/bl31.bin`

현재 project 관점 반영점:

- verified source patch 없음
- verified config delta 없음
- 현재 project는 local unsigned `bl31.bin`을 linux appimage 입력으로 재사용한다.

즉 현재는:

```text
TF-A source code를 project가 바꾼 것이 아니라,
local source build output을 canonical 입력으로 고정한 상태
```

### 2. OP-TEE `BL32`

source:

- `workspace/optee-os-4.9.0+git`

output:

- `workspace/optee-os-4.9.0+git/out/arm-plat-k3/core/tee-pager_v2.bin`

현재 project 관점 반영점:

- verified source patch 없음
- verified project-specific config patch 없음
- 현재 project는 local `tee-pager_v2.bin`을 linux appimage 입력으로 재사용한다.

### 3. U-Boot A53 chain

source:

- dirty user workspace는 직접 사용하지 않음
- project용 clean worktree:
  - `workspace/ti-u-boot-sdk12-sk-am64b-local-fullchain`

partial outputs:

- `out/u-boot-local-a53chain/a53/spl/u-boot-spl.bin`
- `out/u-boot-local-a53chain/a53/u-boot.img`

현재 project 관점 반영점:

- source baseline commit:
  - `ti-u-boot-2026.01` branch의 `bootdelay=10` 상태
- build-time config fragment:
  - `bsp/u-boot/configs/am64x-watchdog.config`
- current linux appimage build에서 중요한 것은 `CONFIG_K3_ATF_LOAD_ADDR=0x701c0000`

즉 현재 project가 U-Boot A53에 반영하는 것은 다음 두 축이다.

1. source baseline 선택
2. watchdog config fragment 적용

validated current flow 기준에서는 별도 source code patch를 project-specific delta로 확정하지 않았다.

현재 실제 validated bootstrap 방식:

- source baseline branch/worktree:
  - `workspace/ti-u-boot-sdk12-sk-am64b-local-fullchain`
  - branch `ti-u-boot-2026.01`
  - `CONFIG_BOOTDELAY=10`
- build-time fragment:
  - `bsp/u-boot/configs/am64x-watchdog.config`

## current helper

print/bootstrap helper:

```bash
./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --print
```

개별 build:

```bash
./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-tfa
./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-optee
./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-uboot-a53
```

일괄 build:

```bash
./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-all
```

실제 검증 결과:

```text
TF-A source build: success
OP-TEE source build: success
U-Boot A53 source build: success
```

주의:

- 기존 `workspace/ti-u-boot-sdk12` 는 custom-board DTS dirty 상태였으므로 직접 사용하지 않았다.
- project는 clean worktree를 따로 만들어 source bootstrap에 사용했다.

## 중요한 경계

이 helper는 최종 flash input 4종을 만들기 전 단계까지만 담당한다.

즉:

```text
source bootstrap chain
  -> bl31.bin
  -> tee-pager_v2.bin
  -> u-boot-spl.bin
  -> u-boot.img

deploy image assembly chain
  -> SBL / R5F / U-Boot / linux appimage final set
```

최종 flash image set 생성은 다음 helper가 맡는다.

```bash
./tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build
```

## 현재 확인된 U-Boot dirty state 해석

기존 `workspace/ti-u-boot-sdk12`의 dirty 상태는
watchdog/bootdelay baseline이 아니라 custom-board DTS 작업 흔적이었다.

따라서 이 project는 dirty user workspace를 직접 build input으로 쓰지 않고,
clean worktree를 별도로 두어 source bootstrap을 수행한다.
