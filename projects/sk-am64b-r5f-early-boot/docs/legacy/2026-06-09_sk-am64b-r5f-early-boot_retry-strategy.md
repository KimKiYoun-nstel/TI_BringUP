# 2026-06-09 SK-AM64B R5F Early Boot Retry Strategy

## 목적

이 문서는 2026-06-09 기준 SK-AM64B R5F early boot Phase2의
**가장 안전한 다음 OSPI retry 전략**을 고정한다.

핵심 목표는 다음과 같다.

- 이미 flash된 OSPI 내용이 host artifact와 일치하는지 검증된 상태를 기준으로
- 불필요한 다변수 변경을 피하고
- **Linux appimage 내부 handoff chain** 에만 집중한 단일 변수 retry를 수행한다.

## 현재 확정된 사실

### 1. SD Linux baseline은 정상

- 현재 보드는 SD card 기준으로 Linux boot와 shell 접근이 가능하다.

### 2. 최신 OSPI flash 내용은 host artifact와 일치

SD Linux에서 readback hash를 확인한 결과 다음 slot은 모두 host 파일과 일치했다.

| absolute offset | Linux MTD readback 위치 | 기대 artifact | 결과 |
|---|---|---|---|
| `0x0` | `mtd0@0x0` | `sbl_ospi_linux.release.hs_fs.tiimage` | 일치 |
| `0x80000` | `mtd0@0x80000` | `r5f-early-heartbeat.mcelf.hs_fs` | 일치 |
| `0x300000` | `mtd2@0x0` | `u-boot.img` | 일치 |
| `0x800000` | `mtd5@0x0` | `linux.mcelf.hs_fs` | 일치 |

해석:

- 현재 문제는 “flash가 잘못 들어갔다”가 아니라
  **flash된 artifact chain 자체가 BL31 이후 멈추는지** 로 좁혀진다.

### 3. 최신 실패 signature는 여전히 BL31 이후 정지

현재 기준 실패 signature:

```text
SBL chain starts
BL31 banner prints
BL31 이후 추가 진행 없음
```

## TI guide와 다시 맞춘 핵심 판단

### 1. source of truth는 SDK cfg/syscfg 쪽이다

다음이 현재 offset 기준 source of truth다.

- `examples/drivers/boot/sbl_ospi_linux/.../default_sbl_ospi_linux.cfg`
- `examples/drivers/boot/sbl_ospi_linux/.../example.syscfg`

이 기준에서는:

```text
0x0       : SBL OSPI Linux image
0x80000   : multicore appimage
0x300000  : u-boot.img
0x800000  : linux appimage
```

주의:

- 일부 TI 웹 문서 본문에는 Linux appimage가 `0x300000`처럼 읽히는 설명이 있지만,
  현재 local SDK source와 default cfg는 `linux appimage -> 0x800000`,
  `u-boot.img -> 0x300000` 으로 정리된다.
- retry 판단 기준은 **문서 본문 요약이 아니라 SDK source/cfg** 로 고정한다.

### 2. Linux appimage helper에는 두 가지 정합성 이슈가 있었다

#### 이슈 A. dry-run 문서와 실제 helper의 SPL source가 달랐다

- dry-run 문서: `tispl.bin`을 local source of truth로 설명
- 실제 helper: `out/u-boot/a53/spl/u-boot-spl.bin`을 staging해서 사용

#### 이슈 B. TI guide는 unsigned A53 input을 요구하는데 provenance가 섞여 있었다

현재 helper는 다음 입력을 사용했다.

- `bl31.bin` : SDK prebuilt
- `bl32.bin` : SDK prebuilt
- `u-boot-spl.bin-am64xx-evm` : local raw `u-boot-spl.bin` alias
- `u-boot.img` : local build output

즉 Linux appimage 내부 체인이
**SDK prebuilt + local A53 output 혼합** 상태였다.

## 가장 안전한 다음 retry 원칙

다음 retry는 반드시 **단일 변수 변경**이어야 한다.

### 유지할 것

- flashwriter: `am64x-sk`
- offset `0x0`: `sbl_ospi_linux.release.hs_fs.tiimage`
- offset `0x80000`: `r5f-early-heartbeat.mcelf.hs_fs`
- offset `0x300000`: `u-boot.img`
- `flash-phy-tuning-data` 비활성 유지

### 바꿀 것

- offset `0x800000`의 Linux appimage만 교체

교체 대상:

- 기존: `out/r5f-early-boot/linux-appimage-build/linux.mcelf.hs_fs`
- 다음 retry용: `out/r5f-early-boot/linux-appimage-build-sdk-spl/linux.mcelf.hs_fs`

## 왜 이 variant를 먼저 시도하는가

이번 variant는 helper 구조를 크게 흔들지 않고,
**Linux appimage 내부 SPL 입력만 TI SDK의 `u-boot-spl.bin-am64xx-evm` 쪽으로 바꾼 실험**이다.

즉 다음을 만족한다.

- 변화량이 작다
- 기존 readback-verified layout을 유지한다
- 실패 시 원인 분리를 계속할 수 있다

## 준비된 retry cfg

다음 cfg를 다음 UART uniflash retry의 기준으로 사용한다.

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl_sdk-spl.cfg`

이 cfg의 의미:

- flashwriter는 `am64x-sk`
- offset `0x0`은 `sbl_ospi_linux`
- offset `0x80000`은 custom heartbeat R5F image
- offset `0x300000`은 동일 `u-boot.img`
- offset `0x800000`만 새 `linux.mcelf.hs_fs` variant 사용

## 실제 retry 전 체크리스트

1. 보드가 여전히 SD Linux baseline으로 정상 부팅되는지 확인
2. `uartd` stop 가능 상태 확인
3. UART boot mode 전환 전 현재 cfg와 artifact sha256 재확인
4. 사용할 cfg가 아래 파일인지 확인
   - `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl_sdk-spl.cfg`
5. 새 boot 판정은 반드시 UART 최신 tail만 기준으로 볼 것

## retry 후 판정 기준

### 성공 쪽 신호

```text
BL31 이후 추가 진행
U-Boot SPL banner
U-Boot proper
Linux console / login prompt
```

### 실패 시 다음 해석

만약 이 variant도 여전히 BL31 직후 멈추면,
다음 유력 원인은 아래 순서로 본다.

1. `bl31.bin` / `bl32.bin` 자체가 TI guide가 말하는 unsigned provenance와 다름
2. local `u-boot.img`와 Linux appimage 내부 SPL/ATF/OPTEE 조합 mismatch
3. custom chain 대신 TI stock example image set으로 더 직접적인 A/B 비교 필요

## 지금 하지 않을 것

- Linux shell에서 `/dev/mtd*`에 직접 쓰기
- `mtd0` composite image 수작업 생성
- 여러 slot을 동시에 바꾸는 다변수 retry
- `sbl_ospi` 를 Linux chain 시작 image 자리에 다시 쓰기

## 현재 권장 결론

```text
Flash path 자체는 검증되었다.
다음 retry는 flash mechanism 변경이 아니라
Linux appimage 내부 chain 검증용 단일 변수 실험이어야 한다.
```
