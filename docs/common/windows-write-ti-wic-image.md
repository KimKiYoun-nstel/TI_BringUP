# Windows에서 TI `.wic.xz` 이미지를 microSD에 기록하기

## 목적

TI Processor SDK Linux 이미지는 `.wic.xz` 형식으로 배포될 수 있습니다.

AM64x EVM/SK bring-up 관점에서 이 파일은 압축된 raw SD 카드 이미지입니다.

```text
.wic.xz
  -> 압축된 raw 디스크 이미지

.wic
  -> SD 카드에 직접 기록하는 raw 디스크 이미지
```

## 시도한 도구

### balenaEtcher

입력:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

결과:

```text
writer process ended unexpectedly
```

판단:

- 이번 Windows 환경에서는 실패했습니다.
- Windows에서 boot 파티션이 보여도 SD 카드를 신뢰하지 않는 편이 좋습니다.

### Raspberry Pi Imager

입력:

```text
Use custom image
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

결과:

```text
기록은 완료되었지만 99~100% 부근에서 검증 실패
```

판단:

- 검증 실패로 봐야 합니다.
- 결과물을 신뢰 가능한 상태로 취급하면 안 됩니다.

### Rufus

입력:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic
```

결과:

```text
기록 성공
SK-AM64B 부팅 성공
root 로그인 성공
```

판단:

- 이번 구성에서 실제로 동작한 방법입니다.

## 권장 절차

### 1. TI 이미지 다운로드

예시:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

### 2. 필요하면 파일 해시 확인

PowerShell 예시:

```powershell
Get-FileHash .\tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz -Algorithm SHA256
```

확인된 해시:

```text
C6214B81E8D2C8CFD911CE2C41F1729B033A2A5FB6EACBC8F4016E931A2E173A
```

### 3. `.wic.xz` 압축 해제

7-Zip 또는 xz를 지원하는 다른 도구를 사용합니다.

입력:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz
```

출력:

```text
tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic
```

### 4. Rufus로 `.wic` 기록

Rufus 설정:

```text
Device: 대상 microSD
Boot selection: .wic 파일
Write mode: 물어보면 DD image / raw image mode 선택
```

중요:

```text
ISO 모드로 기록하지 말 것
기록 후 Windows가 Linux 파티션 포맷을 요구해도 포맷하지 말 것
```

## 기록 후 Windows에서 보일 수 있는 동작

Windows에는 `boot` 파티션만 보일 수 있습니다.

rootfs 파티션은 Linux ext4라서 Windows가 읽지 못할 수 있으므로 정상 동작입니다.

Windows가 알 수 없는 파티션 포맷을 요구해도 진행하지 않습니다.

## 실패 해석

기록 도구가 validation 실패를 보고하면:

```text
bring-up 용도로 그 SD 카드를 신뢰하지 말 것
```

가능한 원인:

```text
SD 카드 문제
SD 카드 리더 문제
USB 허브/포트 불안정
기록 도구 문제
이미지 압축 해제 또는 기록 경로 문제
```

이후 rootfs mount나 systemd 기동 부근에서 부팅 실패가 나면 SD 카드 무결성을 가장 먼저 다시 확인합니다.
