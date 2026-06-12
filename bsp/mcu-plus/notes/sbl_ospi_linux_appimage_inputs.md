# SBL OSPI Linux Appimage Input Inventory

## 목적

이 문서는 `linuxAppimageGen`에 필요한 Linux-side 입력 artifact를
현재 TI_Bringup repo 기준으로 어디서 가져올지 정리한다.

현재 단계는 inventory / documentation 단계이며,
실제 image generation을 수행하지 않는다.

## 기준 source

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/tools/boot/linuxAppimageGen/config.mak`
- `tools/build/build-u-boot.sh`
- `sdk-manifest/source-commits.md`
- `tools/env/sdk-12.00.00.07.04.env`

## `linuxAppimageGen`가 기대하는 입력 이름

`config.mak` 기준 확인값:

| 항목 | 기대 이름 | 비고 |
|---|---|---|
| ATF | `bl31.bin` | unsigned input 기대 |
| OP-TEE | `bl32.bin` | unsigned input 기대 |
| SPL | `u-boot-spl.bin-am64xx-evm` | AM64x 전용 이름 |

추가로 local cfg / flash script 관점에서는 다음 artifact도 같이 봐야 한다.

| 항목 | 역할 |
|---|---|
| `u-boot.img` | OSPI cfg 상 `0x300000` 후보 |
| `linux.appimage` / `linux.mcelf.hs_fs` | `linuxAppimageGen` 최종 산출물 |

## 중요한 주의

`config.mak`에는 다음 기본값이 남아 있다.

```text
PSDK_LINUX_IMAGE_PATH=$(HOME)/ti-processor-sdk-linux-am64xx-evm-10.00.07.04
```

해석:

- local repo가 사용하는 SDK 12 기준과 맞지 않는다.
- 따라서 task-unit-2에서 실제 image generation을 할 때는
  이 경로를 현재 repo / SDK 12 기준으로 명시적으로 override 해야 한다.

## 현재 repo 기준 후보 출처

### 1. `bl31.bin`

1차 후보:

- `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/board-support/prebuilt-images/am64xx-evm/bl31.bin`

근거:

- `tools/build/build-u-boot.sh`는 U-Boot build 입력으로 이 prebuilt directory를 사용한다.
- local 환경에서 실제 파일 존재가 확인되었다.

### 2. `bl32.bin`

1차 후보:

- `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/board-support/prebuilt-images/am64xx-evm/bl32.bin`

근거:

- `tools/build/build-u-boot.sh`는 같은 prebuilt directory에서 `bl32.bin`을 요구한다.
- local 환경에서 실제 파일 존재가 확인되었다.

### 3. `u-boot-spl.bin-am64xx-evm`

1차 후보:

- `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/board-support/prebuilt-images/am64xx-evm/u-boot-spl.bin-am64xx-evm`

근거:

- `linuxAppimageGen/config.mak`가 기대하는 정확한 이름이다.
- local 환경에서 실제 파일 존재가 확인되었다.

2차 후보:

- local U-Boot build 결과에서 `tispl.bin` 또는 동등 artifact를 mapping 하는 방법

현재 상태:

- `out/u-boot/artifacts/tispl.bin` 존재
- `out/u-boot/a53/tispl.bin` 존재
- 하지만 이름이 `u-boot-spl.bin-am64xx-evm`과 직접 일치하지 않는다.

해석:

- task-unit-2 실제 실행 단계에서는
  `local tispl.bin`을 바로 쓸지,
  `u-boot-spl.bin-am64xx-evm` 기대 이름으로 staging 할지
  명확한 mapping 규칙이 필요하다.

추가 참고:

- `sbl_ospi_linux_spl_staging_mapping.md`
- `sbl_ospi_linux_appimage_staging_policy.md`

### 4. `u-boot.img`

1차 후보:

- `out/u-boot/artifacts/u-boot.img`

동등 후보:

- `out/u-boot/a53/u-boot.img`

근거:

- local U-Boot build 결과에서 실제 존재가 확인되었다.
- 현재 MCU+ example cfg 기준으로 `0x300000` offset 후보 artifact 이다.

## 현재 판단

### 즉시 사용할 inventory 기준

| 입력 | 우선 후보 | 상태 |
|---|---|---|
| `bl31.bin` | SDK 12 prebuilt | 존재 확인 |
| `bl32.bin` | SDK 12 prebuilt | 존재 확인 |
| `u-boot-spl.bin-am64xx-evm` | SDK 12 prebuilt | 존재 확인 |
| `u-boot.img` | local `out/u-boot/artifacts/u-boot.img` | 존재 확인 |

### task-unit-2에서 추가 확인할 것

1. unsigned / signed input 요구사항
2. HS-FS / HS device type별 차이
3. local `tispl.bin`과 `u-boot-spl.bin-am64xx-evm`의 사용 정책
4. 실제 `linuxAppimageGen` 실행 시 override 변수와 staging directory 규칙

## 결론

현재 repo 기준으로 Linux appimage 입력 artifact의 후보 출처는 정리되었다.

다만 실제 generation 단계에 들어가기 전에는 다음이 필요하다.

```text
- config.mak 기본 경로 override 정책 확정
- SPL naming / staging mapping 확정
- unsigned/signed input policy 확인
```
