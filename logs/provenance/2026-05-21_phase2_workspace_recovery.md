# 2026-05-21 Phase2 Workspace Recovery Provenance

## 목적

이 문서는 Phase2 과정에서 발생한 workspace/external SDK 오염 상태를
Main Repo 관점에서 어떻게 회수하고 정상화할지 기록한다.

중요:

- 이 문서는 최종 제품 baseline 선언이 아니다.
- 리허설 변경을 선택 가능한 자산으로 회수하기 위한 provenance 기록이다.

## 관찰된 상태

### Main Repo

- `projects/am64x-r5f-button-event-lab/` 추가
- Phase2 build/deploy helper 추가

### U-Boot workspace

- `workspace/ti-u-boot-sdk12/board/ti/am64x/rm-cfg.yaml`
- 현재 dirty diff 존재
- Main Repo patch로 회수됨:
  - `bsp/u-boot/patches/0001-am64x-rm-cfg-assign-mcu-gpio-router-to-main-0-r5-1.patch`

### 외부 MCU+ SDK 원본

- `sciclient_defaultBoardcfg_rm.c`
- `sciclient_defaultBoardcfg_rm_linux.c`
- 직접 수정 흔적을 Main Repo patch로 회수 완료:
  - `bsp/mcu-plus/patches/0001-am64x-boardcfg-route-mcu-gpiomux-output-to-main-0-r5-1.patch`
- 이후 외부 SDK 원본은 clean baseline으로 복구 완료

## 검증 결과

`tools/prepare/verify-workspace-state.sh` 현재 결과:

- U-Boot workspace dirty 경고/차단
- 외부 MCU+ SDK 원본 오염 없음
- Linux workspace clean

즉, 현재 상태는 **외부 SDK 오염은 해소됐고, U-Boot workspace만 아직 정리되지 않은 상태**다.

## 정상화 순서

1. U-Boot workspace 변경을 patch 기준으로 재검토한다.
   - patch를 유지할지
   - 폐기할지 결정

2. 외부 MCU+ SDK 직접 수정분을 재현 가능한 workspace 흐름으로 옮긴다.
   - 가능하면 `workspace/mcu-plus-*` 도입
   - 또는 patch 적용 절차 문서화

3. U-Boot workspace는 다음 둘 중 하나로 정리한다.
    - patch를 공식 채택하고 workspace reset 후 patch replay
    - 실험 폐기 후 workspace reset

4. `verify-workspace-state.sh` 가 clean pass 하는지 확인한다.

## 즉시 후속 액션

- `export-workspace-patches.sh` 를 실제 운영에 사용해 추가 dirty diff를 export
- `bsp/*/patches/series` 에서 채택 patch와 실험-only patch를 구분
- build/deploy 전에 provenance 문서를 남기는 습관을 강제
