# 온보딩 가이드

## 목적

이 문서는 처음 이 워크플로우를 사용하는 사람이 `custom board DTS` 작업을 시작할 때 따라야 할 최소 절차를 정리한다.

핵심은 다음 두 줄이다.

- 새 board project는 `templates/ti_board_project/`에서 시작한다.
- `.NET`, schematic hardware DB, SysConfig DB, reference DTS를 넣고 `facts -> candidates -> final candidate` 순서로 올린다.

## 먼저 읽을 문서

1. `README.md`
2. `docs/workflow_guide.md`
3. `docs/board_dts_decisions_schema.md`
4. `docs/review_checklist.md`

## 준비물

필수 입력:

1. board `.NET`
2. board PDF 회로도
3. 회로도 기반 `hardware_db`
4. target SoC용 SysConfig pinmux DB

권장 참조 입력:

1. SoC reference DTS/DTSI
2. reference board DTS
3. DTS header 복사본

## 새 board project 시작

1. `templates/ti_board_project/`를 `platforms/<soc>/projects/<board-project>/`로 복사한다.
2. `inputs/netlist/`에 `.NET`을 넣는다.
3. `inputs/schematic/`에 회로도 PDF를 넣는다.
4. 반복 작업용 schematic backdata가 있으면 `inputs/schematic/hardware_db/`에 넣는다.
5. 필요하면 `inputs/reference_dts/`, `inputs/reference_headers/`에 비교용 복사본을 넣는다.
6. `docs/board_dts_decisions.yaml`의 `source_documents`를 실제 파일명으로 맞춘다.
7. `config/paths.local.yaml.example`를 `config/paths.local.yaml`로 복사하고 로컬 경로를 채운다.

## 설정 수정

`config/paths.local.yaml.example`를 복사한 뒤 `config/paths.local.yaml`에서 최소한 다음을 맞춘다.

- `board_project_dir`
- `netlist_path`
- `platform_dir`
- `pinmux_db_csv`
- `pinmux_db_json`
- `linux_dts_dir`
- `linux_include_dir`
- `soc_dtsi`
- `reference_board_dts`
- `board_dts_prefix`

## Stage-1 실행

repo root에서 실행:

```bash
python3 tools/custom_board_dts_workflow/scripts/run_stage1.py
```

주요 산출물:

- `generated/linux/facts/`
- `generated/linux/candidates/`
- `generated/linux/base/`
- `generated/uboot_spl/facts/`
- `generated/uboot_spl/candidates/`
- `generated/uboot_spl/base/`
- `reports/facts/`
- `reports/todo/manual_review_report.md`

## 첫 검토 순서

1. `reports/facts/soc_symbol_quality_report.md`
2. `reports/facts/pinmux_lookup_report.csv`
3. `reports/todo/manual_review_report.md`
4. `docs/board_dts_decisions.yaml`
5. `docs/sk_am64b_reference_delta_table.md`

## 판단 입력 보강

Stage-1 결과만으로 확정되지 않는 항목은 `docs/board_dts_decisions.yaml`에 반영한다.

회로도 PDF를 이미 `hardware_db`로 구조화했다면, 우선 그 DB를 읽고 필요한 부분만 PDF 원문으로 역추적한다.

대표 예:

- GPIO vs alt function 선택
- controller enable/disable
- I2C child `compatible`, `reg`
- Ethernet PHY address/delay
- USB/SERDES policy 메모

## Final Candidate 작성

이 워크플로우의 현실적인 최종 목표는 `production DTS 자동 생성`이 아니라, `generated/` 아래 공식 산출물 계층을 준비하는 것이다.

그 안에서:

1. Stage-1 facts/candidates/base
2. 사람이 판단을 반영한 `generated/*/final/`

권장 원칙:

- 확정된 내용만 final candidate에 올린다.
- 미확정 정책은 TODO comment나 별도 notes 문서로 남긴다.
- Stage-1 자동 산출물과 final candidate를 분리한다.

`reports/`는 공식 산출물이 아니라 review 보조 자료로 본다.

## 완료 기준

다음 조건을 만족하면 한 board project의 1차 온보딩이 끝난 것으로 본다.

- Stage-1 실행이 성공했다.
- `board_dts_decisions.yaml` 기본 skeleton이 실제 입력 파일명으로 채워졌다.
- `manual_review_report.md`의 주요 unresolved 항목이 분류됐다.
- `generated/linux/final/` 또는 `generated/uboot_spl/final/`에 첫 final candidate가 생겼다.
