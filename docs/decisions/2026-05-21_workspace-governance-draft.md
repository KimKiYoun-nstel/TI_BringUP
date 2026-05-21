# Workspace Governance Draft

Date: 2026-05-21  
Status: Draft

## 배경

`workspace/`는 최종 제품 baseline을 계속 누적하는 저장소가 아니라,
custom board 개발을 위한 리허설/실험을 수행하는 editable source 작업공간이다.

따라서 여기서 발생하는 변경은 모두 최종 산출물에 자동 포함되면 안 된다.
대신 다음 두 성격 중 하나로 분류되어야 한다.

1. 나중에 선택적으로 채택할 수 있는 patch/config 자산
2. 채택은 하지 않지만 판단 근거로 보관할 실험/provenance 자산

## 초안 결정

### 1. 역할 분리

- `workspace/`: 실험/분석/빌드 작업공간
- Main Repo: patch, manifest, provenance, docs의 authoritative owner
- 외부 SDK 원본: read-only reference

### 2. 선택적 채택 모델

- workspace 변경은 기본적으로 자동 누적되지 않는다.
- patch `series`에 등록된 변경만 replay 대상이 된다.
- patch로 승격되지 않은 변경은 provenance/research에만 남긴다.

### 3. 직접 수정 금지 대상

- `~/ti/am64x/...` 아래 외부 SDK 원본
- toolchain/sysroot
- `out/` 산출물
- SD/OSPI/rootfs의 live contents

### 4. 회수 단위

- U-Boot: `bsp/u-boot/patches/`
- Linux: `bsp/linux/patches/`
- MCU+ SDK: `bsp/mcu-plus/patches/`
- 실험 증적: `logs/provenance/`, `docs/research/`

## 후속 구현 필요

- `sdk-manifest/workspaces.yml` 운용 정착
- `tools/prepare/export-workspace-patches.sh` 구현
- `tools/prepare/verify-workspace-state.sh` 구현
- build/deploy 스크립트와 provenance 자동 연결
