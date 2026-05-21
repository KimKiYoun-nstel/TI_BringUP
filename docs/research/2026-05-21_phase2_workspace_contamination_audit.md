# 2026-05-21 Phase2 Workspace Contamination Audit

## 목적

이번 문서는 Phase2 진행 중 발생한 형상관리 오염을 **리허설 이력**으로 회수하기 위한 1차 감사 문서다.

핵심 질문:

- 어떤 변경이 Main Repo에 남아 있는가?
- 어떤 변경이 `workspace/`에만 남아 있는가?
- 어떤 변경이 외부 SDK 원본에 직접 들어갔는가?
- 어떤 변경이 최종 custom board output에 포함될 후보인지, 아니면 단순 리허설 참고 자산인지?

## 현재 확인된 오염 지점

### 1. Main Repo 내부

- `projects/am64x-r5f-button-event-lab/` 생성
- `tools/build/build-am64x-r5f-button-event-lab.sh`
- `tools/install/deploy-am64x-r5f-button-event-lab-host.sh`

해석:

- 이 영역은 Main Repo 관리 대상이므로 정상적인 형상관리 대상이다.
- 다만 아직 정식 patch/provenance 체계와 연결되지 않았다.

### 2. U-Boot workspace 내부

- `workspace/ti-u-boot-sdk12/board/ti/am64x/rm-cfg.yaml`
- 현재 diff: `host_id: 12 -> 36`

해석:

- 정책상 workspace 수정 자체는 허용된다.
- 하지만 Main Repo의 `bsp/u-boot/patches/`에 export되지 않았으므로 영구 이력으로는 불충분하다.

### 3. 외부 SDK 원본 직접 수정

- `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm.c`
- `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c`

해석:

- 이 변경은 현재 정책 위반이다.
- 외부 SDK 원본 직접 수정은 금지되어야 하며, 회수 후 원본 복구가 필요하다.

## 이번 사고에서 배운 점

1. `workspace/` 사용 원칙은 있었지만, Main Repo가 workspace 변경을 강제로 소유하는 구조는 약했다.
2. build artifact provenance만으로는 source-of-truth를 대체할 수 없다.
3. 리허설 단계 변경은 누적 baseline이 아니라 **선택 가능한 참고 자산**으로 관리해야 한다.

## 회수 원칙

- 외부 SDK 직접 수정은 그대로 인정하지 않는다.
- 필요한 변경이면 workspace 기준 patch로 재정식화한다.
- patch로 승격되지 않은 리허설 수정은 provenance/research에만 남기고 기본 series에는 넣지 않는다.

## 다음 액션

1. U-Boot workspace diff를 `bsp/u-boot/patches/`로 export할지 결정
2. 외부 SDK 수정분을 `bsp/mcu-plus/patches/` 또는 별도 재현 절차로 회수
3. 외부 SDK 원본 clean baseline 복구
4. `tools/prepare/verify-workspace-state.sh`에 금지 경로 검사를 구현
