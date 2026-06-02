# Boot Asset Classification Guide

## 목적

이 문서는 TI_Bringup 저장소에서 boot / deploy / rootfs / bring-up 관련 자산을
어떻게 분류하고 유지할지에 대한 **공통 기준**을 정의한다.

이 문서의 목적은 다음과 같다.

1. 실험 중 생긴 자산이 무질서하게 누적되는 것을 막는다.
2. "현재 채택된 경로"와 "과거 실험 흔적"을 구분한다.
3. workspace를 clean baseline으로 되돌린 뒤에도,
   repo 안의 patch/config/docs만으로 다시 시작할 수 있게 한다.

즉 이 문서는 단일 boot issue의 해결 절차가 아니라,
**repo 자산 관리 기준**을 정의하는 문서다.

---

## 1. 자산 3분류

이 저장소의 boot/bring-up 자산은 항상 다음 셋 중 하나로 분류한다.

### A. 채택 유지

현재 기준의 성공 경로, baseline 이해, 또는 clean replay에 직접 필요한 자산.

예:

- 현재 선택된 boot flow를 설명하는 문서
- replay 대상 `patches/series` 안의 patch
- 현재 사용 중인 config fragment
- 현재 성공 경로를 재현하는 deploy/media helper

판단 기준:

1. 지금 다시 clean baseline에서 작업을 시작할 때 필요한가?
2. 현재 성공 경로를 설명하거나 재현하는 데 직접 쓰이는가?
3. 대체 자산이 없고 source of truth 역할을 하는가?

셋 중 두 개 이상 YES면 보통 채택 유지다.

### B. 실험 자산이지만 보관 가치 있음

현재 최종 경로에는 직접 쓰이지 않지만,
원인 분석, 회귀 비교, 재현성 검토, 향후 재도전 가치가 있는 자산.

예:

- case matrix
- 실패/성공 실험 메모
- diagnostic initramfs
- one-off driver experiment provenance
- 중간 단계의 DTS candidate

판단 기준:

1. 지금은 안 쓰지만 나중에 "왜 이렇게 됐지?"를 설명하는 데 중요한가?
2. 삭제하면 같은 실패를 다시 반복할 가능성이 큰가?
3. 최종 채택 여부는 미정이지만 기술적 탐침으로 가치가 있었는가?

두 개 이상 YES면 보통 실험 자산 보관 대상이다.

### C. legacy / 재검토 필요

현재 선택한 경로와 직접 맞지 않거나,
중간 실험 전용이었는데 지금은 사용 의도가 약해진 자산.

예:

- 더 이상 쓰지 않는 `uEnv.txt` override helper
- 최종 채택 경로와 다른 media layout을 전제한 script
- 성공 경로와 무관한 오래된 임시 config
- 문서상 가정이 이미 깨진 setup guide

중요:

`legacy`는 곧바로 삭제를 뜻하지 않는다.

우선은:

1. legacy로 라벨링
2. 왜 현재 경로와 안 맞는지 기록
3. 삭제할지 archive할지 나중에 결정

으로 처리한다.

---

## 2. 파일 종류별 기본 처리 원칙

### patch

- `bsp/*/patches/series`에 들어가면 **채택 유지** 후보
- patch 파일만 있고 series에 없으면 **실험 또는 rehearsal** 후보
- workspace diff를 clean replay하려면 가능한 patch로 승격한다.

### config fragment / DTS candidate

- 현재 성공 경로에서 쓰인 fragment면 **채택 유지**
- 진단용/실험용이면 **실험 자산 보관**
- 더 이상 맞지 않는 가정이면 **legacy**

### helper script

- 지금도 operator가 바로 실행해야 하는 script면 **채택 유지**
- 특정 실험 cycle에서만 유효했다면 **실험 자산 보관**
- 최종 media layout / boot policy와 어긋나면 **legacy**

### 문서

- baseline / current adopted path 설명 문서면 **채택 유지**
- 상세 실험 기록 문서면 **실험 자산 보관**
- 가정이 깨졌는데 수정되지 않았다면 **legacy**

### provenance

- provenance는 원칙적으로 삭제보다 보관을 우선한다.
- 다만 최종 adopted path를 설명하는 문서와 역할이 겹치지 않게,
  provenance는 "무엇을 어떤 상태에서 빌드/배포했는가"에 집중한다.

---

## 3. clean baseline 재시작 관점의 판단 기준

새 작업을 TI SDK baseline clean tree에서 다시 시작한다고 가정했을 때,
각 자산에 다음 질문을 한다.

### 질문 1

```text
이 파일이 없으면 clean baseline에서 현재 성공 경로를 다시 만들 수 없는가?
```

YES면 채택 유지 쪽이다.

### 질문 2

```text
이 파일이 없으면 과거 실패 원인이나 중간 판단 근거를 잃는가?
```

YES면 실험 자산 보관 쪽이다.

### 질문 3

```text
이 파일은 현재 성공 경로와 다른 가정(boot policy/media layout/path)을 전제로 하고 있는가?
```

YES면 legacy 후보다.

---

## 4. 문서화 원칙

자산을 분류할 때는 단순히 폴더 이동만 하지 말고,
반드시 문서에 다음 중 하나를 남긴다.

1. 왜 채택 자산인지
2. 왜 실험 자산으로 남기는지
3. 왜 legacy로 돌리는지

권장 기록 위치:

- project-wide rule: `docs/common/`
- board-specific asset inventory: `docs/research/` 또는 `docs/boards/<board>/`

---

## 5. 실제 운영 순서

새 자산이 생기면 다음 순서로 처리한다.

1. 이 자산의 목적을 한 줄로 적는다.
2. 현재 성공 경로와 직접 연결되는지 판단한다.
3. clean replay에 필요한지 판단한다.
4. 과거 실패/탐침 가치가 있는지 판단한다.
5. A/B/C 중 하나로 분류한다.
6. patch면 `series` 포함 여부를 결정한다.
7. 문서에 분류 이유를 남긴다.

---

## 6. 현재 USB/SD boot 사례에 적용하는 예

다음은 실제 사례다.

### 채택 유지 예

- SD baseline 설명 문서
- USB ROMBOOT media prep helper
- USB-only autoboot 성공 상태 문서
- replay 대상 U-Boot / kernel patch series

이유:

- 현재 성공 경로를 다시 만드는 데 직접 필요

### 실험 자산 보관 예

- USB root case matrix
- N17 initramfs diagnostic source
- USB root next-actions 문서

이유:

- 현재 최종 경로에는 직접 안 쓰여도,
  왜 그런 결론에 왔는지와 회귀 비교에 중요

### legacy 예

- SD FAT `uEnv.txt` override 기반 rehearsal helper
- `sda2` USB-BOOT 중심의 old extlinux rehearsal 가이드

이유:

- 현재 최종 USB-only success path는 `sda1` self-contained extlinux 구조인데,
  저 자산들은 다른 media/policy 가정을 전제로 함

---

## 7. 한 줄 요약

```text
채택 유지 = 지금 성공 경로를 다시 만들 때 필요
실험 보관 = 지금은 안 쓰지만 이유/회귀 분석에 중요
legacy = 다른 가정 위에서 만들어져 현재 경로와 어긋남
```
