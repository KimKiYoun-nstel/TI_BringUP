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
   - flash 존재와 8-bit bus는 명확하지만 vendor-specific timing과 partition 정책은 보류했다.
7. CPSW dual PHY 기본 연결
   - PHY 두 개, MDIO address, 기본 RX delay는 회로도와 SK reference로 맞출 수 있었다.

## 의도적으로 보류한 것

1. `main_uart2`
   - TXD는 반영 가능했지만 RXD가 현재 `.NET` evidence와 decision 메모 사이에서 일치하지 않아 disable로 남겼다.
2. TPM `U15`
   - Linux compatible과 production enable 여부가 불명확하다.
3. `U21` PI6ULS5V9509UEX
   - bus address와 Linux 역할이 아직 명확하지 않다.
4. USB0 / SERDES0
   - host/peripheral/otg, PCIe/USB3 같은 정책 선택이 남아 있다.
5. memory / reserved-memory / regulator / PMIC
   - Linux 정책층이라 이번 handoff set에 확정 반영하지 않았다.

## 전달받은 사람이 우선 검토할 항목

1. `main_uart2`를 살릴지 여부
2. TPM `U15`를 DTS에 포함할지 여부
3. OSPI flash timing/partition/reset GPIO
4. CPSW reset/interrupt GPIO 연결 방식
5. USB0 role과 SERDES0 protocol
6. LPDDR4 memory size와 reserved-memory 정책
