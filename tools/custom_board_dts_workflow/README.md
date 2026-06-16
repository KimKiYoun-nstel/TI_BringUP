# 커스텀 보드 DTS 생성 가이드 워크플로우

이 디렉터리는 `custom board`용 Linux/U-Boot DTS를 만들기 위한 **워크플로우 템플릿**이다.

목표는 최종 DTS를 자동 생성하는 것이 아니다. 목표는 누구든지 준비 가능한 back data를 같은 순서로 검토하고, 필요한 사실층과 후보층을 빠르게 만들 수 있게 하는 것이다.

## 워크플로우 관점

이 워크플로우는 다음 원칙을 따른다.

- `.NET`은 board wiring fact의 1차 입력이다.
- PDF 회로도는 `.NET`만으로 확정되지 않는 board intent를 확인하는 1차 근거다.
- SysConfig DB는 SoC pinmux 사실 검증용 2차 생성물이다.
- SoC reference DTS/DTSI와 header는 사실 소스가 아니라 integration precedent다.
- 자동화 helper는 **신뢰도가 높은 사실 추출**에만 사용한다.
- 나머지 DTS 내용은 사람이 review하고 결정하는 워크플로우로 남긴다.

즉, 이 디렉터리는 `generator`가 아니라 `DTS 생성 가이드 워크플로우 + 보조 helper` 세트다.

## 사용 가능한 입력

사용자가 준비 가능한 대표 입력:

1. 회로도 기반 `.NET`
2. PDF 회로도
3. SysConfig DB

워크플로우 안에서 함께 활용하는 참조 입력:

1. SoC reference DTS/DTSI
2. DTS header
3. 필요 시 reference board DTS

## 현재 디렉터리 구조

```text
tools/custom_board_dts_workflow/
  config/                  # 워크플로우 기본 설정
  docs/                    # 실행 가이드, 자동화 근거
  platforms/
    am64x/
      config/              # SoC별 node map, compatible map
      db/                  # SysConfig 기반 pinmux DB
      docs/                # SoC별 DB 준비 가이드
      projects/
        <board-project>/
          inputs/          # .NET, reference DTS/header, board input
          docs/            # board별 delta, decision 문서
          generated/       # facts/candidates/base 산출물
          reports/         # facts report, manual review report
  scripts/                 # 워크플로우 helper 실행점
  src/dts_workflow/        # 보조 helper 코드
  tests/
```

## 핵심 산출물

Stage-1 helper는 다음 층을 만든다.

```text
generated/linux/
  facts/
    <board>-pinmux.facts.dtsi
  candidates/
    <board>-controllers.candidates.dtsi
    <board>-devices.candidates.stub.dtsi
  base/
    <board>-base.dts

generated/uboot_spl/
  facts/
    <board>-early-pinmux.facts.dtsi
  candidates/
    <board>-boot-media.candidates.md
    <board>-ddr.candidates.md
  base/
    <board>-u-boot-spl.dtsi
    <board>-u-boot-spl.md

reports/
  facts/
    soc_symbol_quality_report.md
    soc_pin_net_table.csv
    pinmux_lookup_report.csv
    interface_facts.csv
    peripheral_inventory.csv
  todo/
    manual_review_report.md
```

의미는 다음과 같다.

- `facts`: `.NET + SysConfig DB`만으로 확인된 불변 사실층
- `candidates`: reference DTS precedent와 기본 규칙으로 만든 후보층
- `base`: facts와 candidates를 조합한 시작점
- `todo`: 사람이 추가 판단해야 하는 항목

## 자동화 가능한 영역

현재 신뢰도 높게 helper에 맡길 수 있는 영역:

- SoC symbol/ball 기반 pin usage 정리
- SysConfig DB 검증을 통과한 pinmux facts 생성
- MAIN vs MCU/WKUP pinctrl macro 선택
- controller enable 후보층 생성
- 일부 external device stub 생성

## 자동화로 끝낼 수 없는 영역

다음은 workflow review가 필요하다.

- PHY address, `phy-mode`, internal delay
- regulator / PMIC 정책
- GPIO polarity
- DDR training / include chain
- boot order / alias / chosen 최종 정책
- reserved-memory / remoteproc / memory size
- USB / SERDES / Ethernet 같은 board integration 정책

## 현재 작업 원칙

- 워크플로우는 root repo 내부 자산만으로 재실행 가능해야 한다.
- Linux reference는 `workspace/ti-linux-kernel-sdk12`만 사용한다.
- 외부 SDK 원본 `~/ti/am64x/.../board-support/...`는 직접 참조 대상으로 삼지 않는다.
- board별 수동 판단은 문서나 YAML input으로 남겨 다음 실행에 재사용한다.

## 먼저 읽을 문서

- 실행 절차: `docs/workflow_guide.md`
- 새 사용자 온보딩: `docs/onboarding.md`
- 자동화 신뢰 근거: `docs/automation_basis.md`
- decision YAML 스키마: `docs/board_dts_decisions_schema.md`
- 수동 검토 절차: `docs/review_checklist.md`
- SK-AM64B 비교 기준: `platforms/am64x/projects/<board-project>/docs/sk_am64b_reference_delta_table.md`

새 project 시작 템플릿:

- `templates/ti_board_project/`

## 현재 실행 명령

```bash
python3 tools/custom_board_dts_workflow/scripts/run_stage1.py
```
