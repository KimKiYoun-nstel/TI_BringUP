# 2026-05-21 Workspace Governance Rollout

## 목적

기존의 `workspace/` 사용 원칙을 실제 운영 절차로 승격한다.

핵심은 다음 두 가지다.

1. 외부 SDK 원본 직접 수정 금지
2. workspace 변경을 Main Repo가 patch/manifest/provenance로 소유

## 오늘 반영된 것

- `sdk-manifest/workspaces.yml` 추가
- `bsp/mcu-plus/` 추가
- `bsp/*/patches/series` 추가
- `logs/provenance/README.md` 추가
- `tools/prepare/export-workspace-patches.sh` 구현 시작
- `tools/prepare/verify-workspace-state.sh` 구현 시작
- Phase2 오염 감사 문서 추가

## 아직 남은 것

### 1. U-Boot patch 정식화

- Phase2 U-Boot 변경을 Main Repo patch 자산으로 회수 완료
- `bsp/u-boot/patches/series` 에 replay 대상으로 등록 완료
- 남은 일은 workspace를 reset 후 patch replay 기준 clean 상태로 정리하는 것

### 2. MCU+ SDK workspace 도입 여부 결정

- 외부 SDK 원본을 직접 수정하지 않기 위해
  - `workspace/mcu-plus-sdk-am64x-12.00.00/` 생성
  - 또는 prepare script로 복제/patch 적용 흐름 추가

### 3. 검증 스크립트 강화

- 외부 SDK 원본 수정 탐지를 현재 incident-specific marker에서
  일반 규칙 기반 검사로 확장
- build/deploy 스크립트에서 `verify-workspace-state.sh` 선행 호출

### 4. provenance 자동화

- U-Boot/kernel/MCU+ SDK build 후 provenance 파일 자동 생성

## 운영 원칙

- 리허설 변경은 기본적으로 final output에 자동 누적하지 않는다.
- `series`에 포함된 patch만 replay 대상으로 본다.
- 나머지는 `docs/research/`와 `logs/provenance/`에 참고 자산으로 남긴다.
