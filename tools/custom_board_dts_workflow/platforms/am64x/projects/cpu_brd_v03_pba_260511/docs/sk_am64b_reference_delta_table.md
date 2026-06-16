# SK-AM64B Reference Delta Table

## 목적

이 문서는 현재 board project workflow 산출물과 SK-AM64B reference DTS를 비교하여,

- 이미 helper가 만든 층
- workflow 기본값으로 채워진 층
- 아직 수동 통합이 필요한 층

을 구분하기 위한 표다.

## Reference Inputs

Linux reference:

- `inputs/reference_dts/linux/k3-am642-sk.dts`
- `inputs/reference_dts/linux/k3-am642.dtsi`
- `inputs/reference_dts/linux/k3-am64*.dtsi`

U-Boot reference:

- `inputs/reference_dts/uboot/k3-am642-r5-sk.dts`
- `inputs/reference_dts/uboot/k3-am642-sk-u-boot.dtsi`
- `inputs/reference_dts/uboot/k3-am64-ddr.dtsi`
- `inputs/reference_dts/uboot/k3-am64x-binman.dtsi`

## Linux Delta

| Area | SK-AM64B reference | Workflow output | 상태 | 설명 |
|---|---|---|---|---|
| SoC include base | `k3-am642.dtsi` include | 있음 | 자동화됨 | base DTS 조립 가능 |
| chosen/stdout-path | 있음 | 있음 | 자동화됨 | workflow 기본값으로 채움 |
| aliases | 있음 | 있음 | 자동화됨 | workflow 기본값으로 채움 |
| UART0/I2C0/I2C1/OSPI0 pinmux | 있음 | 있음 | 자동화됨 | `.NET + DB` fact 기반 |
| MMC0 controller node | 있음 | 있음 | 자동화됨 | reference precedent 반영, pinctrl 생략 |
| UART2 pinmux | SK에는 기본 board policy로 없음 | 있음 | custom delta 후보 | custom board netlist에서 감지됨 |
| GPMC0 pinmux | SK에는 기본 board policy로 없음 | 있음 | custom delta 후보 | custom board netlist에서 감지됨 |
| CPSW/PRU 관련 pin fact | SK에는 완성 node/pinctrl 존재 | 일부 fact만 있음 | 부분 자동화 | pin fact는 있으나 완성 ethernet policy는 없음 |
| device stub (I2C child) | SK는 실제 주소/compatible 포함 | stub만 있음 | 부분 자동화 | address/policy resolver 필요 |
| memory node | 있음 | 없음 | 미자동화 | board memory/BOM 정보 필요 |
| reserved-memory | 있음 | 없음 | 미자동화 | OP-TEE/R5/shared-dma policy 필요 |
| regulator tree | 있음 | 없음 | 미자동화 | PMIC/power tree 정책 필요 |
| LED / gpio-expander / temp sensor | 있음 | 일부 stub만 | 미자동화/부분 자동화 | 회로도 외 추가 binding/address 정보 필요 |
| Ethernet PHY / cpsw port policy | 있음 | 없음 | 미자동화 | phy-mode, delay, MDIO addr 필요 |
| USB/SERDES board policy | 있음 | 일부 pin fact만 | 미자동화 | PHY/serdes 정책층 필요 |

### Linux 해석

- workflow helper는 `pinmux fact`, `controller candidate`, `기본 aliases/chosen`까지는 이미 만든다.
- SK DTS가 가진 board integration policy 대부분은 아직 자동화 대상이 아니다.
- 따라서 현재 Linux 산출물은 `custom board base candidate`이지 `SK 수준 완성 DTS`는 아니다.

## U-Boot / SPL Delta

| Area | SK-AM64B reference | Workflow output | 상태 | 설명 |
|---|---|---|---|---|
| early console candidate | 있음 | 있음 | 자동화됨 | `main_uart0` default console candidate 생성 |
| early pinmux fact | reference에 분산됨 | 있음 | 자동화됨 | early pinmux facts로 분리 생성 |
| boot media candidate | reference에 SD/OSPI policy 존재 | 있음 | 부분 자동화 | `MMC0`, `OSPI0` 후보 생성 |
| U-Boot base layer | reference는 R5/U-Boot include 체계 | 있음 | 부분 자동화 | base dtsi 생성 가능 |
| DDR include chain | reference에 있음 | 없음 | 미자동화 | `k3-am64-sk-lp4-1600MTs.dtsi`, `k3-am64-ddr.dtsi` 수준 미반영 |
| binman / U-Boot packaging include | reference에 있음 | 없음 | 미자동화 | `k3-am64x-binman.dtsi` 수준 미반영 |
| bootph property | reference에 다수 있음 | 거의 없음 | 미자동화 | U-Boot stage-specific annotation 미구현 |
| U-Boot-only property overrides | reference에 있음 | 없음 | 미자동화 | 예: timer/clock/status override |

### U-Boot 해석

- workflow helper는 현재 `U-Boot 사실층 + 기본 후보층`까지만 만든다.
- SDK U-Boot DTS가 가진 `R5/SPL/DDR/binman/bootph` 통합 구조는 아직 자동 생성하지 않는다.
- 따라서 현재 U-Boot 산출물은 `실제 SDK U-Boot DTS 대체본`이 아니라 `조립 시작용 candidate layer`다.

## 핵심 결론

1. 현재 workflow helper는 custom board의 `.NET`에서 읽히는 **불변 사실층**을 Linux/U-Boot 양쪽에 공급할 수 있다.
2. SK-AM64B DTS와 동일 수준의 완성 board policy까지는 아직 가지 않는다.
3. custom board가 SK-AM64B base라면, 다음 단계는 `workflow output`과 `SK reference DTS`를 결합해 delta를 조립하는 과정이다.
4. 따라서 앞으로 자동화의 초점은 `새 DTS를 임의 생성`하는 것보다 `SK 대비 custom delta synthesis`에 두는 것이 맞다.
