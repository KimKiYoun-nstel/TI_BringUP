# `board_dts_decisions.yaml` 스키마 가이드

## 목적

이 문서는 board별 DTS 판단 입력 파일인 `board_dts_decisions.yaml`의 공용 형식을 정의한다.

이 파일의 역할은 다음과 같다.

- `.NET`만으로 확정되지 않는 board intent를 기록한다.
- PDF 회로도 검토 결과를 재실행 가능한 입력으로 남긴다.
- 다음 실행에서도 같은 판단을 다시 쓰게 한다.

권장 파일명:

- `docs/board_dts_decisions.yaml`

기본 템플릿:

- `templates/ti_board_project/docs/board_dts_decisions.yaml`

## 경로 규칙

- 템플릿은 `templates/ti_board_project/`에 있지만, 실제 사용 위치는 각 `platforms/<soc>/projects/<board-project>/` 디렉터리다.
- 파일 위치 기준 root는 각 `projects/<board-project>/` 디렉터리다.
- `source_documents[*].path`는 가능하면 board project 기준 상대 경로로 적는다.
- PDF는 `inputs/schematic/`, netlist는 `inputs/netlist/`를 사용한다.

## 상위 구조

```yaml
version: 1
board: <board-name>
source_documents: []
rules: {}
mux_decisions: []
controller_decisions: []
external_device_decisions: []
ethernet_phy_decisions: []
report_only: []
```

모든 section이 항상 필수는 아니다. 모르는 영역은 빈 list로 두면 된다.

## 공통 필드

### `version`

- 현재 고정값: `1`

### `board`

- board 식별자
- 예: `am6412_custom_cpu_board`

### `source_documents`

입력 근거 파일 목록이다.

예:

```yaml
source_documents:
  - path: inputs/schematic/BOARD_REV_A.pdf
    role: custom_board_schematic
    revision: "A"
    date: "2026-06-16"
  - path: inputs/netlist/BOARD_REV_A.NET
    role: orcad_connectivity_netlist
  - path: ../../db/am64x_sysconfig_pinmux_db.csv
    role: ti_am64x_pinmux_database
```

권장 `role`:

- `custom_board_schematic`
- `orcad_connectivity_netlist`
- `ti_am64x_pinmux_database`
- 필요 시 board-specific custom role

### `rules`

워크플로우 해석 원칙을 남긴다.

예:

```yaml
rules:
  precedence:
    - board_dts_decisions
    - exact_soc_symbol_pin_match
    - schematic_context_inference
    - unresolved
  workflow_requirements:
    - "Do not use NETNAME as the primary key for pinmux generation."
```

## `status` 권장 값

- `confirmed_by_schematic`
- `derived_from_schematic`
- `needs_hw_confirmation`

의미:

- `confirmed_by_schematic`: 회로도에서 의도가 직접 보임
- `derived_from_schematic`: 회로도 문맥상 강한 추정이지만 추가 확인 권장
- `needs_hw_confirmation`: 회로도만으로는 최종 정책 확정 어려움

## `evidence` 형식

대부분의 decision 항목에는 `evidence`를 붙이는 것을 권장한다.

예:

```yaml
evidence:
  - page: 19
    title: "SoC SYSTEM & I2C & UART"
    notes:
      - "회로도에서 LED 연결 의도가 직접 보인다."
      - "해당 ball과 net이 같은 페이지에서 확인된다."
```

## `mux_decisions`

SoC ball의 실제 기능 선택을 명시한다.

대표 필드:

- `id`
- `status`
- `soc_ref`
- `schematic_unit`
- `ball`
- `symbol_pin_name`
- `net`
- `selected_function`
- `dts_usage`
- `linux_target`
- `evidence`
- `sysconfig_validation_required`

선택 필드:

- `active_level`
- `default_state`

주요 용도:

- GPIO vs alt function 선택
- pinctrl 승격
- gpio-led, reset-gpio, interrupt-gpio 같은 소비자 힌트

## `controller_decisions`

controller node enable/disable 및 board-level 속성을 명시한다.

대표 필드:

- `id`
- `status`
- `controller`
- `peripheral`
- `dts_node`
- `enabled`
- `evidence`

controller별 추가 필드 예:

- MMC: `bus_width`, `non_removable`, `device_ref`, `device_part`
- OSPI: `flash_ref`, `flash_part`, `bus_width`
- CPSW/USB/SERDES: `ports`, `dts_nodes`, `observed_signals`, `policy_required`

## `external_device_decisions`

I2C/MDIO 등 버스에 붙는 외부 device 정보를 명시한다.

대표 필드:

- `id`
- `status`
- `bus`
- `dts_parent`
- `refdes`
- `part`
- `compatible`
- `reg`
- `purpose`
- `evidence`

선택 필드:

- `unresolved`

## `ethernet_phy_decisions`

PHY strap/address/delay 같은 Ethernet 정책 입력을 명시한다.

대표 필드:

- `id`
- `status`
- `phy_ref`
- `part`
- `mdio_bus`
- `mdio_address`
- `reset_net`
- `interrupt_net`
- `tx_clock_skew`
- `rx_clock_skew`
- `auto_negotiation`
- `advertised`
- `evidence`
- `dts_mapping_required`

## `report_only`

현재 Linux DTS 자동화 대상이 아니지만 기록은 필요한 항목을 남긴다.

대표 예:

- DDR
- boot mode strap
- analog-only block
- Linux DTS 범위 밖의 pre-boot hardware

대표 필드:

- `id`
- `status`
- `reason`
- `evidence`

## 작성 원칙

- 회로도에서 확인한 사실과 추정을 구분한다.
- `selected_function`은 SysConfig DB로 검증 가능한 이름을 쓴다.
- DTS 정책이 필요한 항목은 `unresolved` 또는 `policy_required`로 남긴다.
- 같은 판단을 다음 실행에 다시 쓰려면 YAML에 남긴다.

## 현재 예시 파일

- `platforms/am64x/projects/cpu_brd_v03_pba_260511/docs/board_dts_decisions.yaml`
