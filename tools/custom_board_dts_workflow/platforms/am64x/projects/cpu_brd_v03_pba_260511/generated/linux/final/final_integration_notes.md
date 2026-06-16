# Linux Final Candidate Notes

## 포함된 것

- 명시적 board decision이 있는 controller enable/disable
- LED, EEPROM, ADS1115 같은 확정 device node
- eMMC 8-bit / MMC1 disable 결정
- OSPI flash generic node
- CPSW dual PHY 기본 연결과 DP83867 delay 기본값

## 의도적으로 보류한 것

1. `main_uart2`
   - TXD는 확인되지만 RXD 경로가 현재 `.NET` evidence와 decision YAML 사이에서 일치하지 않는다.
2. TPM `U15`
   - `compatible`과 production enable 정책이 확정되지 않았다.
3. `U21` PI6ULS5V9509UEX
   - 주소와 Linux 쪽 역할이 확정되지 않았다.
4. USB0 / SERDES0
   - `dr_mode`, VBUS 표현, PCIe vs USB3 선택이 남아 있다.
5. memory / reserved-memory / regulator / PMIC
   - board boot 정책과 Linux carveout 정책이 아직 정리되지 않았다.

## 다음 사용자 결정이 필요한 항목

1. LPDDR4 size와 Linux memory node
2. OP-TEE / R5 / shared memory carveout
3. USB0 host/peripheral/otg 최종 정책
4. SERDES0 protocol 선택
5. TPM `U15` 채택 여부와 compatible
6. CPSW reset GPIO / interrupt GPIO 연결 방식
