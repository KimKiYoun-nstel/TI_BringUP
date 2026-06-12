# SBL OSPI Linux Appimage Staging Policy

## 목적

이 문서는 `linuxAppimageGen` 실행 전에
어떤 staging directory를 사용하고,
어떤 변수만 override 할지에 대한 repo 기준 정책을 정리한다.

현재 단계는 policy 문서화 단계이며,
실제 `make` 실행은 포함하지 않는다.

## 배경

현재 확인된 `linuxAppimageGen` 구조는 다음과 같다.

1. `config.mak`에서 기본 입력 이름과 `PSDK_LINUX_PREBUILT_IMAGES`를 정의한다.
2. `makefile`은 `$(PSDK_LINUX_PREBUILT_IMAGES)/$(ATF_BIN_NAME)`,
   `$(PSDK_LINUX_PREBUILT_IMAGES)/$(OPTEE_BIN_NAME)`,
   `$(PSDK_LINUX_PREBUILT_IMAGES)/$(SPL_BIN_NAME)`를 직접 읽어 ELF/RPRC로 변환한다.
3. `u-boot.img`도 `$(PSDK_LINUX_PREBUILT_IMAGES)/u-boot.img`에서 현재 작업 디렉터리로 복사한다.

즉 이 도구는 현재 구조상
**입력 파일이 하나의 prebuilt/staging 디렉터리 안에 함께 존재한다는 전제**를 가진다.

## 현재 repo 기준 문제

현재 입력 후보는 두 계열로 나뉜다.

| 입력 | 현재 우선 후보 |
|---|---|
| `bl31.bin` | SDK 12 prebuilt |
| `bl32.bin` | SDK 12 prebuilt |
| `u-boot-spl.bin-am64xx-evm` | SDK 12 prebuilt |
| `u-boot.img` | local `out/u-boot/artifacts/u-boot.img` |

따라서 실제 generation 단계에선 다음 둘 중 하나가 필요하다.

1. 전부 SDK prebuilt 기준으로 맞춘다
2. 필요한 파일을 별도 staging directory로 모은다

현재 repo 방향은 2번이 더 적합하다.

이유:

- local U-Boot build 결과를 선택적으로 반영할 수 있다.
- prebuilt와 local artifact를 섞을 때 provenance를 분리해 기록하기 쉽다.
- source of truth와 tool input directory를 분리할 수 있다.

## 권장 staging directory

task-unit-2 실제 실행 시 권장 staging root:

```text
out/r5f-early-boot/linux-appimage-staging/
```

권장 예시 구조:

```text
out/r5f-early-boot/
  linux-appimage-staging/
    bl31.bin
    bl32.bin
    u-boot-spl.bin-am64xx-evm
    u-boot.img
```

해석:

- 이 디렉터리는 source of truth가 아니라 `linuxAppimageGen` 입력 staging area 이다.
- 실제 원본은 SDK prebuilt directory 또는 `out/u-boot/artifacts/`에 남는다.

## 권장 source -> staging 매핑

| staging 파일명 | 권장 source |
|---|---|
| `bl31.bin` | `SDK_ROOT/board-support/prebuilt-images/am64xx-evm/bl31.bin` |
| `bl32.bin` | `SDK_ROOT/board-support/prebuilt-images/am64xx-evm/bl32.bin` |
| `u-boot-spl.bin-am64xx-evm` | `out/u-boot/artifacts/tispl.bin` 또는 SDK prebuilt SPL |
| `u-boot.img` | `out/u-boot/artifacts/u-boot.img` |

중요:

- SPL은 local canonical name이 `tispl.bin` 이므로,
  staging 시에만 `u-boot-spl.bin-am64xx-evm` alias를 준다.

## 권장 override 변수

현재 단계에서 문서상으로 우선 확정할 override는 다음이다.

### 필수

- `MCU_PLUS_SDK_PATH`
- `PSDK_LINUX_IMAGE_PATH`
- `PSDK_LINUX_PREBUILT_IMAGES`

권장 해석:

```text
MCU_PLUS_SDK_PATH        -> local MCU+ workspace
PSDK_LINUX_IMAGE_PATH    -> current SDK 12 root 또는 staging policy 설명용 기준 경로
PSDK_LINUX_PREBUILT_IMAGES -> 실제 실행 시 staging directory
```

여기서 핵심은 `PSDK_LINUX_PREBUILT_IMAGES`를
SDK 원본 prebuilt-images가 아니라
**staging directory로 override** 할 수 있게 잡는 것이다.

### 조건부

- `DEVICE_TYPE`

이유:

- makefile은 `DEVICE_TYPE=HS` 여부에 따라 생성 대상(`.hs`, `.hs_fs`, MCELF sign path)가 달라진다.
- 현재 단계에서는 inventory만 하고,
  실제 device policy는 후속 실행 단계에서 확정한다.

## 현재 단계 권장 실행 개념

실제 실행은 아직 하지 않지만,
개념상 다음 순서를 권장한다.

```text
1. source artifact 확인
2. staging directory 생성
3. source -> staged input 파일 배치
4. PSDK_LINUX_PREBUILT_IMAGES=<staging-dir> override
5. linuxAppimageGen 실행
6. source/staged path와 sha256 provenance 기록
```

## provenance에 남길 항목

- staging directory path
- staging 생성 시각
- source file path 4종
- staged file path 4종
- 각 source/staged sha256
- override 변수 값

## 현재 단계 결론

현재 repo 기준으로는 다음 정책이 가장 일관적이다.

```text
source of truth는 SDK prebuilt / out/u-boot/artifacts 에 유지하고,
linuxAppimageGen 실행은 out/r5f-early-boot/linux-appimage-staging/ 같은 별도 staging directory를 통해 수행한다.
```

이 문서는 실행 정책만 정의하며,
실제 staging script나 `make` 실행은 후속 단계로 남긴다.
