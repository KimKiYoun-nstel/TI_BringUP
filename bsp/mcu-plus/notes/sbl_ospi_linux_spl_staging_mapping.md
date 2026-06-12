# SBL OSPI Linux SPL Staging Mapping Note

## 목적

이 문서는 `linuxAppimageGen`가 기대하는 SPL 입력 이름
`u-boot-spl.bin-am64xx-evm` 와,
현재 TI_Bringup local U-Boot build 산출물 이름 `tispl.bin` 사이의
mapping 규칙을 정리한다.

현재 단계는 inventory / naming policy 문서화이며,
실제 파일 rename, copy, staging 실행은 하지 않는다.

## 배경

현재 repo에서 확인된 사실은 다음과 같다.

### `linuxAppimageGen` 기대 이름

근거:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/tools/boot/linuxAppimageGen/config.mak`

확인값:

```text
SPL_BIN_NAME=u-boot-spl.bin-am64xx-evm
```

### local U-Boot build 산출물 이름

근거:

- `tools/build/build-u-boot.sh`
- `out/u-boot/artifacts/build-manifest.txt`

현재 산출물:

```text
out/u-boot/artifacts/tispl.bin
out/u-boot/a53/tispl.bin
out/u-boot/artifacts/u-boot.img
```

즉 local build pipeline은 `u-boot-spl.bin-am64xx-evm`가 아니라 `tispl.bin`을 관리 단위로 사용한다.

## 이름 차이의 의미

이 둘은 역할이 다르지 않고,
**서로 다른 naming convention 아래의 SPL 계열 artifact**로 봐야 한다.

정리하면:

| 관점 | 이름 | 용도 |
|---|---|---|
| MCU+ `linuxAppimageGen` 기대 입력 | `u-boot-spl.bin-am64xx-evm` | tool input 이름 |
| local U-Boot build / deploy artifact | `tispl.bin` | repo-managed build 산출물 이름 |

## 현재 단계의 source of truth

### source of truth for local build result

- `out/u-boot/artifacts/tispl.bin`

이유:

- `build-u-boot.sh`가 최종 artifact manifest에 기록하는 이름이다.
- repo 내부 다른 deploy/review 흐름도 `tispl.bin`을 기준으로 본다.

### source of truth for `linuxAppimageGen` interface expectation

- `u-boot-spl.bin-am64xx-evm`

이유:

- tool이 기대하는 입력 변수 이름이기 때문이다.

## task-unit-2에서의 staging 규칙

실제 Linux appimage generation 단계로 들어갈 때는 다음 규칙을 권장한다.

### 규칙 1. local build 결과는 그대로 `tispl.bin`으로 보관

해석:

- `out/u-boot/artifacts/tispl.bin` 자체를 rename 해서 source of truth를 바꾸지 않는다.
- provenance / manifest / build helper와의 일관성을 유지한다.

### 규칙 2. `linuxAppimageGen` 실행용 staging 이름은 별도로 만든다

권장 개념:

```text
source of truth: out/u-boot/artifacts/tispl.bin
staging alias   : <staging-dir>/u-boot-spl.bin-am64xx-evm
```

이유:

- local build 산출물 naming과 tool interface naming을 분리할 수 있다.
- 이후 provenance에 `source file -> staged alias` 관계를 명시하기 쉽다.

### 규칙 3. staging은 copy 또는 symlink policy를 따로 정한다

현재 단계 판단:

- 아직 copy와 symlink 중 어느 쪽을 채택할지 결정하지 않는다.
- 우선 문서상으로는 `staging alias 필요`까지만 확정한다.

## 권장 provenance 기록 항목

task-unit-2에서 실제 generation을 할 때는 다음을 함께 기록해야 한다.

- source `tispl.bin` path
- staged `u-boot-spl.bin-am64xx-evm` path
- source sha256
- staged file sha256
- staging 방법(copy/symlink)

## 현재 단계 결론

현재 repo 기준으로 다음처럼 정리한다.

```text
local build canonical name     = tispl.bin
linuxAppimageGen expected name = u-boot-spl.bin-am64xx-evm
task-unit-2 execution 시 둘 사이에 별도 staging alias를 둔다
```

이 문서는 naming/mapping policy만 확정하며,
실제 staging 실행은 후속 단계로 남긴다.
