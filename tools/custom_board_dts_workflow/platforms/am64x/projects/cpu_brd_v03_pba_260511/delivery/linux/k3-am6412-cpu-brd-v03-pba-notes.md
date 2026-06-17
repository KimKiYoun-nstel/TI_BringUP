# Linux DTS Handoff Notes

## 왜 이 세트로 정리했는가

이 전달 세트는 workflow 내부 파일을 넘기는 목적이 아니라, DTS/DTSI를 직접 읽고 수정할 사람이 바로 편집할 수 있게 하기 위한 세트다.

그래서 다음만 남겼다.

1. 메인 보드 DTS
2. pinctrl 전용 DTSI
3. peripheral/integration override DTSI
4. 사람이 읽는 선택 이유/보류 항목 메모

## 이번 선택에 포함한 것

1. LED 두 개
   - 회로도에서 GPIO 의도가 명확했다.
2. EEPROM `U14@0x51`
   - 주소와 part가 회로도에서 직접 확인됐다.
3. ADS1115 `U20@0x48`
   - 주소와 part가 회로도에서 직접 확인됐다.
4. eMMC 8-bit / `sdhci0`
   - 회로도에서 eMMC 8bit 구성이 명확했다.
5. `sdhci1` disable
   - MMC1 SD 4bit path가 not used로 명시됐다.
6. OSPI flash generic node
	- flash 존재와 8-bit wiring은 명확하지만, boot 관점에서는 `hardware_db/03_boot_media.yaml` 기준으로 single-SPI safe profile을 우선 적용했다.
7. CPSW dual PHY 기본 연결
	- PHY 두 개, MDIO address, 기본 RX delay는 회로도와 `inputs/schematic/hardware_db/03_interfaces.yaml`, SK reference로 맞출 수 있었다.
8. memory / reserved-memory baseline
	- LPDDR4 2GB 정보와 `hardware_db/02_memory_and_reserved.yaml` 기준으로 memory node를 추가했고, reserved-memory는 SK-AM64B baseline 후보를 같이 넘겼다.

## main_uart2 정리

- 최종 handoff에서는 `K19/UART2_TXD + W6/UART2_RXD` 조합으로 반영했다.
- 이유: `.NET`과 debug path evidence가 `W6/SOC_UART2_RXD`를 직접 가리키고, page 30 DEBUG path가 이를 뒷받침한다.
- 즉 이 항목은 더 이상 막연한 policy issue가 아니라, 기존 해석 불일치를 정정한 결과다.

## 의도적으로 보류한 것

1. TPM `U15`
   - Linux compatible과 production enable 여부가 불명확하다.
2. `U21` PI6ULS5V9509UEX
   - bus address와 Linux 역할이 아직 명확하지 않다.
3. USB0 / SERDES0
   - USB0는 회로와 TI reference 전례를 따라 `USB2-only + OTG`로 넘겼다.
   - 다만 SERDES0를 USB3/PCIe/FPGA/VITA 중 어디에 쓸지는 아직 남아 있다.
4. memory / reserved-memory / regulator / PMIC
	- memory node는 반영했지만 regulator/PMIC binding과 reserved-memory 최종 정책은 여전히 review 대상이다.

## 전달받은 사람이 우선 검토할 항목

1. TPM `U15`를 DTS에 포함할지 여부
2. OSPI flash timing/partition/reset GPIO
3. CPSW reset/interrupt GPIO 연결 방식
4. SERDES0 protocol
5. LPDDR4 memory size와 reserved-memory 정책
6. TPS6522053 Linux binding과 regulator 모델
