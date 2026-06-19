# 워크플로우 실행 가이드

## 목적

이 문서는 `tools/custom_board_dts_workflow`를 이용해 커스텀 보드 DTS 초안을 만드는 표준 순서를 정의한다.

핵심은 다음 한 줄이다.

- `.NET`, schematic hardware DB, SysConfig DB, reference DTS를 순서대로 결합해 facts -> candidates -> base 층을 만든다.

## 입력 분류

### 1. 사용자가 준비하는 입력

1. `platforms/<soc>/projects/<board-project>/inputs/netlist/*.NET`
2. `platforms/<soc>/projects/<board-project>/inputs/schematic/*.pdf`
3. `platforms/<soc>/projects/<board-project>/inputs/schematic/hardware_db/`
4. `platforms/<soc>/db/*` 아래 SysConfig DB

### 2. 워크플로우가 함께 읽는 참조 입력

1. workspace Linux DTS source
2. `inputs/reference_dts/linux/`
3. `inputs/reference_dts/uboot/`
4. `inputs/reference_headers/`

## 실행 전 확인

기본 설정 파일:

- `config/paths.local.yaml`
- `config/paths.local.yaml.example`
- `config/workflow_defaults.yaml`

선택 입력:

- `config/override.local.yaml`
- `docs/board_dts_decisions.yaml` 같은 board decision YAML

관련 참조 문서:

- `docs/board_dts_decisions_schema.md`
- `templates/ti_board_project/`

`config/paths.local.yaml`에서 먼저 확인할 항목:

- `project_root`
- `platform_dir`
- `board_project_dir`
- `netlist_path`
- `pinmux_db_csv`
- `pinmux_db_json`
- `linux_dts_dir`
- `linux_include_dir`
- `soc_dtsi`
- `reference_board_dts`
- `board_dts_prefix`

## 표준 실행 순서

1. `templates/ti_board_project/`를 복사해 `platforms/<soc>/projects/<board-project>/`를 준비한다.
2. `.NET`은 `inputs/netlist/`, PDF 회로도는 `inputs/schematic/` 아래 넣는다.
3. 반복 작업용 schematic backdata가 있으면 `inputs/schematic/hardware_db/` 아래 정리한다.
4. SysConfig DB가 `platforms/<soc>/db/` 아래 있는지 확인한다.
5. workspace Linux DTS/header 경로가 `paths.local.yaml`에 맞는지 확인한다.
6. 필요하면 board decision YAML로 회로도 판단 결과를 명시한다.
7. Stage-1 helper를 실행한다.
8. facts report와 manual review report를 먼저 검토한다.
9. SK/reference DTS와 비교해 base DTS를 보완한다.

## 실행 명령

repo root에서 실행:

```bash
python3 tools/custom_board_dts_workflow/scripts/run_stage1.py
```

## 결과 해석 순서

처음 결과를 볼 때 권장 순서:

1. `reports/facts/soc_symbol_quality_report.md`
2. `reports/facts/interface_facts.csv`
3. `reports/facts/pinmux_lookup_report.csv`
4. `reports/todo/manual_review_report.md`
5. `docs/review_checklist.md`
6. `docs/sk_am64b_reference_delta_table.md`
7. `generated/linux/base/*.dts`

## facts 층

경로:

```text
platforms/<soc>/projects/<board-project>/generated/linux/facts/
```

의미:

- `.NET + SysConfig DB`만으로 검증된 pinctrl 사실층

대표 파일:

- `k3-am6412-custom-pinmux.facts.dtsi`

## candidates 층

경로:

```text
platforms/<soc>/projects/<board-project>/generated/linux/candidates/
```

의미:

- reference DTS precedent와 기본 규칙으로 만든 후보층

대표 파일:

- `k3-am6412-custom-controllers.candidates.dtsi`
- `k3-am6412-custom-devices.candidates.stub.dtsi`

## base 층

경로:

```text
platforms/<soc>/projects/<board-project>/generated/linux/base/
```

의미:

- facts와 candidates를 조합한 시작 DTS

대표 파일:

- `k3-am6412-custom-base.dts`

## manual review 층

경로:

```text
platforms/<soc>/projects/<board-project>/reports/todo/
```

대표 파일:

- `manual_review_report.md`

이 파일은 다음을 모은다.

- Linux pinctrl offset이 없는 항목
- pinctrl로 확정할 수 없는 board-only 배선
- address, polarity, phy-mode처럼 추가 판단이 필요한 항목

주의:

- `manual_review_report.md`는 stage1 lookup 기준 보고서다.
- `docs/board_dts_decisions.yaml`에 반영된 mux 판단은 다음 regenerate부터 이 보고서에서 해소될 수 있다.
- 반대로 `generated/*/final/`에만 수동 수정하고 decision YAML에 back-annotate하지 않으면, stage1 regenerate 시 같은 항목이 다시 review 대상으로 남을 수 있다.

이 보고서를 읽은 뒤에는 `docs/review_checklist.md` 순서대로 검토를 진행한다.

## board decision YAML을 쓰는 시점

다음 상황이면 board decision YAML을 추가한다.

- `.NET`만으로 intended mux를 확정할 수 없을 때
- 같은 ball에서 GPIO와 alt function 중 하나를 선택해야 할 때
- external device의 `compatible`, `reg`, 목적을 명시해야 할 때
- MMC/OSPI/Ethernet처럼 board 쪽 연결 의도를 명시해야 할 때

권장 파일명:

- `docs/board_dts_decisions.yaml`

## 현재 한계

- 현재 구현 검증은 `platforms/am64x` 기준이다.
- final production DTS를 자동 보장하지 않는다.
- regulator, PHY delay, PMIC policy, DDR training, strap/address 정보는 여전히 추가 근거가 필요하다.
