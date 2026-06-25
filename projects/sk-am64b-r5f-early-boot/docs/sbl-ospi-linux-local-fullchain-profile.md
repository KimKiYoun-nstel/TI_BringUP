# SK-AM64B SBL OSPI Linux Local-Fullchain Profile

## 목적

이 문서는 현재 SK-AM64B `SBL OSPI Linux`를 반복 가능하게 rebuild 하는
repo 기준 build profile과, 이번에 실제로 정리된 문제/보완점을 고정한다.

## 이전 문제

직전 실패 signature는 다음이었다.

```text
App_loadLinuxImages status=-1
Some tests have failed!!
```

이 failure는 LPDDR4 자체보다는 `linux appimage` 생성 lineage가 흔들린 상태에서
발생했다.

핵심 문제는 두 가지였다.

1. `linux appimage` 입력 provenance가 섞여 있었다.
- SDK prebuilt `BL31/BL32`와 local `SPL/U-Boot`가 혼용되었다.
- 이 조합은 `linuxAppimageGen/config.mak` 주석이 요구하는 unsigned local chain 기준과 맞지 않았다.

2. `ATF_LOAD_ADDR`가 stale 값으로 남아 있었다.
- U-Boot build는 `CONFIG_K3_ATF_LOAD_ADDR=0x701c0000`
- 기존 `linuxAppimageGen/config.mak` 기본값은 `0x701a0000`
- 결과적으로 `linux appimage` 내부 A53 chain load address가 build lineage와 어긋나 있었다.

## 이번에 보완한 것

### 1. canonical 입력 profile 고정

`tools/build/gen-linux-appimage-for-sbl.sh`의 기본 profile을
`local-fullchain`으로 고정했다.

입력은 다음 네 개다.

- `BL31`: `workspace/trusted-firmware-a-2.14+git/build/k3/lite/release/bl31.bin`
- `BL32`: `workspace/optee-os-4.9.0+git/out/arm-plat-k3/core/tee-pager_v2.bin`
- `SPL`: `out/u-boot-local-a53chain/a53/spl/u-boot-spl.bin`
- `U-Boot`: `out/u-boot-local-a53chain/a53/u-boot.img`

### 2. `ATF_LOAD_ADDR` drift 제거

helper가 staged `config.mak`를 만들 때,
U-Boot `.config`의 `CONFIG_K3_ATF_LOAD_ADDR`를 읽어서 강제로 반영하도록 수정했다.

현재 canonical 값:

```text
ATF_LOAD_ADDR=0x701c0000
```

### 3. rebuild 호환성 보완

host의 `pyelftools 0.26` 환경에서 `linuxAppimageGen`가 실패하지 않도록,
`multicoreelf.py`에 repo-managed compatibility patch를 추가했다.

즉 현재 rebuild는 host Python package 교체 없이 repo 자산만으로 재현 가능해야 한다.

## 현재 build profile

이 문서는 `deploy image assembly chain` 기준 문서다.

즉 focus는 다음이다.

```text
partial build output을 어떤 canonical final set으로 묶고,
그 set이 실제 board deploy/boot에서 검증되었는가
```

`source bootstrap chain` 전체 구조는 별도 문서에서 본다.

- `docs/project-asset-map.md`

중요:

```text
MCU+ source build는 workspace source tree에서 수행한다.
하지만 최종 flash input 4종은 repo-managed out set으로 다시 stage 한다.
```

즉 profile/cfg가 직접 가리켜야 하는 것은 workspace 중간 산출물이 아니라,
최종적으로 `out/` 아래에 모인 canonical artifact set이다.

workspace prepare:

```bash
./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh --apply
```

전체 build:

```bash
./tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build
```

이 wrapper는 다음 순서를 고정한다.

1. LPDDR4 clean workspace base 적용
2. `linuxAppimageGen` pyelftools compatibility patch 적용
3. `sbl_ospi_linux` SBL rebuild
4. early-boot R5F ELF rebuild
5. signed R5F multicore appimage 생성
6. `local-fullchain` linux appimage 생성
7. 최종 flash input 4종을 `out/sk-am64b-sbl-ospi-linux-local-fullchain/` 아래로 stage

flash cfg:

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg`

staged final set:

- `out/sk-am64b-sbl-ospi-linux-local-fullchain/`

## 현재 wrapper의 정확한 범위

현재 wrapper가 **직접 build 하는 것**:

- MCU+ `sbl_ospi_linux` SBL
- current project의 R5F ELF + signed multicore appimage
- `linux.mcelf.hs_fs` 재생성

현재 wrapper가 **전제로 사용하는 것**:

- local TF-A `bl31.bin`
- local OP-TEE `tee-pager_v2.bin`
- local U-Boot A53 chain output

즉 현재 profile은 다음 수준까지는 닫혀 있다.

```text
workspace source + repo-managed patch/helper로
SK-AM64B SBL / R5F / linux appimage final set을 반복 생성 가능
```

하지만 다음 항목은 아직 wrapper 안에 완전히 편입되지 않았다.

```text
TF-A / OP-TEE / U-Boot A53 자체를 source부터 매번 다시 build 하는 flow
```

따라서 현재 상태를 정확히 표현하면

```text
canonical flash-image generation flow: yes
full A53-chain source-to-image build closure: not yet fully codified in one wrapper
```

즉 이 문서만 보고는 전체 source bootstrap chain이 닫혔다고 주장하면 안 된다.
이 문서는 final deploy set 기준 문서다.

## 현재 verified clean canonical set

현재 board에서 write/readback/reboot까지 다시 확인한 clean canonical set의 hash는 다음과 같다.

- `SBL @ 0x0`
  - `54daa55a9368bc7a4037c11c306ee93be67161b92c46989cb88156b575b29c86`
- `R5F @ 0x80000`
  - `8fe21f4561011ad3df73fde753588968193bc9cbe0a626782d8654b98e438a85`
- `U-Boot @ 0x300000`
  - `3b21ef1da9fcbff4f28e565639c5ba885324ba4f66fa27d03fdf08c2b84cd74c`
- `linux appimage @ 0x800000`
  - `5869d705b366694f30f3ef490bf8b02d8d9b99fe59bedeb6aef6c2cd2e2fcaea`

이 set은 board-side readback hash와 host artifact hash가 일치했고,
reboot 후 raw UART capture에서도 다음이 확인되었다.

- `KPI_DATA: [BOOTLOADER PROFILE] App_loadLinuxImages : 58325us`
- `Starting linux and RTOS/Baremetal applications`
- `Trying to boot from SPI`
- `Starting kernel ...`
- Linux login / root shell 복귀

raw boot log path:

- `projects/sk-am64b-r5f-early-boot/logs/2026-06-25_sbl-ospi-linux-local-fullchain-source-bootstrap-uart.log`

## rebuild repeatability

cleanup 후 현재 canonical profile을 다시 돌려서 local rebuild 자체도 성공했고,
그 산출물을 실제 OSPI에 write/reboot해서 boot success까지 확인했다.

- `SBL`
  - `54daa55a9368bc7a4037c11c306ee93be67161b92c46989cb88156b575b29c86`
- `R5F`
  - `8fe21f4561011ad3df73fde753588968193bc9cbe0a626782d8654b98e438a85`
- `U-Boot`
  - `3b21ef1da9fcbff4f28e565639c5ba885324ba4f66fa27d03fdf08c2b84cd74c`
- `linux appimage`
  - `5869d705b366694f30f3ef490bf8b02d8d9b99fe59bedeb6aef6c2cd2e2fcaea`

즉 현재 repo 기준으로는

```text
clean canonical set rebuild: reproducible
clean canonical set write/readback: verified
clean canonical set OSPI boot: verified
```

## marker 해석

이번에 임시로 추가했던 `LINUX_MCELF_DIAG` marker는
`Bootloader_parseAndLoadMultiCoreELFLinux()` failure-only triage용이었다.

현재 성공 boot에서는 이 marker가 출력되지 않는 것이 정상이다.

정리:

```text
marker가 안 나온 이유 = marker가 실패 경로 전용이었고,
현재 boot는 App_loadLinuxImages가 성공했기 때문
```

그리고 이 marker는 cleanup 과정에서 canonical source/profile에서는 제거했다.

반대로 이전에 보던 `Boot Media : undefined`는
`Bootloader_profile` 출력 문자열 문제로 보이며,
현재 성공/실패 root cause와 직접 연결된 증거는 아니다.

## 운영 원칙

1. build는 항상 `local-fullchain` 기준으로만 재생성한다.
2. write 후 reboot 전에는 반드시 사용자가 boot mode switch 상태를 확인한다.
3. 과거 marker/A53-only/BL32 diag trial은 active 기준으로 다시 사용하지 않는다.
