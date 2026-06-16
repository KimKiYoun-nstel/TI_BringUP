# 수동 검토 체크리스트

## 목적

이 문서는 `manual_review_report.md`를 실제 DTS 통합 작업으로 이어가기 위한 표준 체크리스트다.

원칙은 단순하다.

- helper가 만든 `facts`는 재검증보다 활용이 우선이다.
- `manual_review_report.md`에 남은 항목만 사람이 판단한다.
- 판단 결과는 다음 실행에서도 재사용할 수 있도록 문서나 `board_dts_decisions.yaml`로 남긴다.

## 먼저 확인할 파일

1. `reports/facts/soc_symbol_quality_report.md`
2. `reports/facts/pinmux_lookup_report.csv`
3. `reports/todo/manual_review_report.md`
4. `docs/sk_am64b_reference_delta_table.md`
5. `generated/linux/base/*.dts`

## 체크리스트

### 1. SoC symbol quality 확인

- SoC refdes가 기대한 심볼과 일치하는가
- ball, symbol pin 이름, net 이름 추출에 깨진 항목이 없는가
- pinmux facts 수가 비정상적으로 급감하지 않았는가

### 2. board decision 입력 정리

- 회로도 PDF에서 명확히 확인된 mux 의도가 있는가
- `.NET`만으로 확정되지 않는 GPIO/alt-function 선택이 있는가
- external device의 `compatible`, `reg`, 목적을 회로도에서 확정할 수 있는가
- 확정한 판단을 `docs/board_dts_decisions.yaml`에 반영했는가

### 3. Non-Pinctrl / Pre-Linux Hardware Facts 검토

`manual_review_report.md`의 다음 섹션을 확인한다.

- `Clock / Reference Input`
- `Controller-Only Linux DTS`
- `DDR / Bootloader Domain`
- `USB / PHY Domain`

검토 포인트:

- Linux pinctrl로 올리면 안 되는 신호가 섞이지 않았는가
- MMC처럼 controller node만 다뤄야 하는 신호가 맞는가
- DDR, bootloader, PHY, SERDES, USB analog 영역을 Linux DTS 자동화 범위 밖으로 유지했는가

### 4. Alternate Function / GPIO Review 검토

- 같은 ball에서 다른 기능으로 써야 하는 의도가 회로도에 드러나는가
- net 이름만 보고 alt function으로 오판한 항목은 없는가
- GPIO candidate가 실제 GPIO 소비자(node, polarity, default state)로 이어지는가
- 확인된 항목은 `board_dts_decisions.yaml`에 남겼는가

### 5. Controller candidate 검토

- `generated/linux/candidates/*controllers*.dtsi`의 enable 후보가 실제 board wiring과 맞는가
- `pinctrl-0`를 붙이면 안 되는 controller가 없는가
- MMC/OSPI/UART/I2C controller 상태가 board intent와 맞는가
- 필요한 `bus-width`, `non-removable`, boot media 관련 속성이 추가됐는가

### 6. Device candidate 검토

- I2C/MDIO child node의 `compatible`이 맞는가
- `reg` 값이 strap/address 설계와 맞는가
- GPIO LED, sensor, EEPROM, PHY 같은 소비자 노드가 실제 연결과 맞는가
- 아직 확정되지 않은 속성은 TODO로 남아 있는가

### 7. Base DTS 통합 검토

- `generated/linux/base/*.dts` include 체인이 의도와 맞는가
- `chosen/stdout-path`와 `aliases`가 실제 debug/boot 경로와 맞는가
- SK/reference DTS에서 가져와야 할 integration policy가 무엇인지 분리됐는가

### 8. U-Boot / SPL 검토

- `generated/uboot_spl/facts/*`가 early pinmux 용도로 충분한가
- `boot-media.candidates.md`의 후보가 실제 부트 미디어와 맞는가
- DDR, binman, bootph, board-specific override는 별도 통합이 필요한 상태로 남아 있는가

## 검토 결과를 남기는 위치

- board-level mux/device/controller 판단: `docs/board_dts_decisions.yaml`
- board별 비교/적용 메모: `docs/sk_am64b_reference_delta_table.md`
- 장기 보관 가치가 있는 절차/판단: `docs/` 아래 워크플로우 문서

새 board project를 시작할 때는 `templates/ti_board_project/`를 복사해 `platforms/<soc>/projects/<board-project>/`로 사용한다.

## 완료 기준

다음 조건을 만족하면 Stage-1 산출물 검토가 끝난 것으로 본다.

- pinmux facts에 들어갈 항목과 아닌 항목이 구분됐다
- alt function / GPIO ambiguity가 정리됐다
- controller/device candidate 중 채택/보류가 구분됐다
- 남은 항목이 `정책 부재`, `추가 HW 확인 필요`, `Linux DTS 범위 밖` 중 어디인지 분류됐다
