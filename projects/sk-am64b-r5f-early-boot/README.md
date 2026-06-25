# SK-AM64B R5F Early Boot Project

이 디렉터리는 SK-AM64B에서 다음 흐름을 검증하기 위한
**main working surface** 이다.

```text
SBL early boot
  -> R5F firmware start
  -> A53 Linux boot
  -> Linux attach / RPMsg 검증
```

현재 기준 핵심 진전:

- `LPDDR4 DDR reginit` 반영으로 SK-AM64B 실보드와 맞는 DDR init base를 확보
- 원본 `sbl_ospi_linux` 기본 `dual-boot` 경로로 다시 올라와 OSPI 기준 Linux boot까지 재확인
- `remoteproc1/2 = attached`, `remoteproc3/4 = now up` 관찰까지 확보

현재 남은 후속 과제는 이 project 내부에서만 관리한다.

- custom early-boot R5F firmware의 intended heartbeat/SHM 동작 정합성
- custom A53 checker app 기반 SHM 확인 경로 정리
- 이후 own RPMsg app-to-app 경로 정리

위 항목들은 boot-chain closure 이후의 후속 과제이며,
추후 최종 마무리 단계에서 다시 정리한다.

이 프로젝트의 목적은 early-boot 실험 자산, 판단, draft source, gate를
한 프로젝트 아래에서 따라가기 쉽게 만드는 것이다.

## 범위

- task-unit-1 inventory 결과
- task-unit-2 image/layout 준비와 heartbeat draft
- task-unit-3 attach/RPMsg 준비 문서

## 프로젝트 안에 두는 것

- 이번 실험의 plan / gate / inventory / draft source
- board-specific 실험 판단과 working note
- canonical project surface 로 봐야 하는 early-boot 문서

## repo-wide에 남기는 것

다음은 재사용 / replay 자산이므로 repo-wide에 남긴다.

- `sdk-manifest/`
- `bsp/mcu-plus/`
- `tools/build/`
- `tools/install/`
- `logs/provenance/`

## 빠른 시작

- 계획/진행 개요: `docs/plan.md`
- project asset map: `docs/project-asset-map.md`
- source bootstrap chain: `docs/source-bootstrap-chain.md`
- canonical build profile: `docs/sbl-ospi-linux-local-fullchain-profile.md`
- runtime dependency map: `docs/runtime-boot-dependency-map.md`
- 통신 단계 계획: `docs/communication-plan.md`
- gate 상태: `docs/gates.md`
- M1 SHM checker 시도 결과: `docs/m1-shm-checker-attempt.md`
- Phase2 실행 checklist: `docs/phase2-execution-checklist.md`
- Phase2 UART uniflash runbook: `docs/phase2-uart-uniflash-runbook.md`
- task-unit-1 closeout: `docs/task1-inventory-result.md`
- heartbeat source selection: `docs/heartbeat-source-selection.md`
- heartbeat SHM ABI: `docs/heartbeat-shm-abi.md`

수동 Linux checker app 기준:

- source: `a53/src/main.c`
- build: `./tools/build/build-r5f-early-boot-app.sh a53`
- expected output: `out/sk-am64b-r5f-early-boot/a53/sk_am64b_r5f_early_boot_check`
- first success log: `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-11_SK-AM64B_sbl-ospi-linux-lp4-first-success.md`
- dual-boot success log: `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-12_SK-AM64B_sbl-ospi-linux-lp4-dual-boot-success.md`
- current local-fullchain success log: `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-24_SK-AM64B_sbl-ospi-linux-local-fullchain-success.md`

## 관련 repo-wide 자산

- MCU+ SDK inventory: `/home/nstel/ti/TI_Bringup/sdk-manifest/mcu-plus-sdk.md`
- SBL OSPI Linux local inventory: `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_local_inventory.md`
- appimage input inventory: `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_appimage_inputs.md`
- SPL staging mapping: `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_spl_staging_mapping.md`
- appimage staging policy: `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_appimage_staging_policy.md`
- LPDDR4 alignment note: `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_lpddr4_alignment.md`

## 현재 실행 기준

현재 active 기준은 다음 네 개다.

- 이 `README.md`
- `docs/project-asset-map.md`
- `docs/plan.md`
- `docs/gates.md`
- `docs/sbl-ospi-linux-local-fullchain-profile.md`

초기 failed trial 정리 문서는 project surface에서 제거했다.
