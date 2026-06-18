---
name: custom-board-dts-workflow
description: Use when the user asks to build, regenerate, review, integrate, or select DTS for a custom AM64x board using hardware_db, .NET, SysConfig DB, generated/final DTS, or delivery DTS. Do not use for SK-AM64B-only work.
---

# Custom Board DTS Workflow

이 skill은 root repo에서 커스텀 보드 DTS를 만들거나, 이미 만든 DTS를 build 입력으로 연결해야 할 때 사용한다.

## 언제 사용하나

- 사용자가 `custom board`, `cpu_brd_v03_pba_260511`, `hardware_db`, `.NET`, `SysConfig DB`, `generated/linux/final`, `delivery/linux`, `board_dts_decisions.yaml` 같은 키워드로 DTS 생성/재구성/빌드 연동을 요청할 때
- 다음 세션에서 커스텀 보드용 kernel/U-Boot 이미지를 빌드하려고 할 때
- SK-AM64B reference만으로는 부족하고, board 고유 배선/정책을 반영해야 할 때

## 사용하지 말아야 할 경우

- SK-AM64B, TMDS64EVM 같은 TI reference board만 대상으로 한 작업
- 단순 UART 로그 확인이나 rootfs/service 문제처럼 DTS workflow와 무관한 작업

## 기본 원칙

1. 커스텀 보드 DTS의 1차 사실 입력은 TI SDK가 아니라 board project 입력이다.
2. 사실 우선순위는 `hardware_db` -> `.NET` -> SysConfig DB -> reference DTS precedent 순서다.
3. PDF는 원천 증적 확인이 필요할 때만 본다. 반복 작업에서는 `hardware_db`를 우선 사용한다.
4. `generated/*/final/`은 workflow 내부 최종 산출물이다.
5. 실제 build 입력은 root repo가 소유하는 `bsp/*/dts/custom-board/.../sets/<purpose>/` 아래 DTS set다.
6. `delivery/`는 사람이 읽고 넘기기 쉬운 handoff DTS 세트다.
7. build를 시작하기 전에는 어떤 root-managed DTS set를 workspace source of truth로 쓸지 먼저 명시한다.

## 먼저 확인할 파일

1. `docs/common/CUSTOM_BOARD_DTS_WORKFLOW.md`
2. `tools/custom_board_dts_workflow/README.md`
3. `tools/custom_board_dts_workflow/docs/workflow_guide.md`
4. `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/README.md`
5. `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/docs/board_dts_decisions.yaml`
6. `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/inputs/schematic/hardware_db/`
7. `bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/`
8. `bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/`

## DTS 재구성 작업 절차

1. 현재 board project 입력이 최신인지 확인한다.
2. `hardware_db`와 `board_dts_decisions.yaml`에서 이미 확정된 판단을 먼저 읽는다.
3. 필요하면 `python3 tools/custom_board_dts_workflow/scripts/run_stage1.py`를 실행해 facts/candidates/base를 재생성한다.
4. `generated/linux/final/`과 `generated/uboot_spl/final/`을 workflow 최종 산출물로 검토한다.
5. 실제 target build에 쓸 DTS는 `bsp/linux/dts/custom-board/.../sets/<purpose>/`와 `bsp/u-boot/dts/custom-board/.../sets/<purpose>/` 아래에 별도 세트로 승격한다.
6. DTS 변경이 build로 이어질 경우, Linux/U-Boot workspace 반영 경로와 대상 파일을 명시한다.

## build 연동 절차

커스텀 보드 image build 요청을 받으면 다음을 먼저 정리한다.

1. workflow 최종 산출물 기준: `generated/linux/final/`, `generated/uboot_spl/final/`
2. root-managed build DTS set 기준: `bsp/linux/dts/custom-board/.../sets/<purpose>/`, `bsp/u-boot/dts/custom-board/.../sets/<purpose>/`
3. workspace 반영 대상 경로: `workspace/ti-linux-kernel-sdk12/...`, `workspace/ti-u-boot-sdk12/...`
4. build helper 사용 경로: `tools/build/build-kernel.sh`, `tools/build/build-u-boot.sh`
5. provenance와 문서 업데이트 위치

## 산출물 해석 규칙

- `inputs/`: board 사실 입력
- `docs/board_dts_decisions.yaml`: board 정책/판단 입력
- `generated/linux/base/`: helper가 만든 시작 DTS
- `generated/*/final/`: workflow가 관리하는 최종 산출물
- `bsp/*/dts/custom-board/.../sets/<purpose>/`: root repo가 관리하는 실제 build 입력 DTS 세트
- `delivery/`: handoff 중심의 readable DTS 세트
- `reports/`: 증적과 검토 보조 자료

## 주의

- SK-AM64B DTS를 그대로 커스텀 보드 build 기준으로 가정하지 않는다.
- `hardware_db`에 이미 반영된 판단을 PDF-only 상태로 되돌리지 않는다.
- workflow 내부 파일을 그대로 build source of truth로 가정하지 않는다. build에 쓸 세트는 root repo 쪽으로 승격해 관리한다.
- build 직전에는 DTS 사실층과 정책층이 어디서 왔는지 분리해서 설명한다.
- workspace source 수정이 필요하면 topic branch와 provenance 기록까지 함께 생각한다.
