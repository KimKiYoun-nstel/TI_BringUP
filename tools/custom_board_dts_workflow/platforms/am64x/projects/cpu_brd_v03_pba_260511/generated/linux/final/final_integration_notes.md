# Linux Final Candidate Notes

## 포함된 것

- 명시적 board decision이 있는 controller enable/disable
- LED, EEPROM, ADS1115 같은 확정 device node
- eMMC 8-bit / MMC1 disable 결정
- LPDDR4 2GB 기준 memory node
- SK-AM64B baseline을 바탕으로 한 reserved-memory / IPC firmware include 후보
- OSPI flash generic node with single-SPI safe profile
- CPSW dual PHY 기본 연결과 DP83867 delay 기본값

## 의도적으로 보류한 것

1. `main_uart2`
   - 보강된 검토 기준으로 `K19/UART2_TXD + W6/UART2_RXD` 조합을 final candidate에 반영했다.
   - 초기 decision YAML의 `K18 UART2_RXD`는 회로도 MMC page 해석이었지만, 실제 `.NET`과 debug path evidence는 `W6`를 지지한다.

## 의도적으로 보류한 것

1. TPM `U15`
   - `compatible`과 production enable 정책이 확정되지 않았다.
2. `U21` PI6ULS5V9509UEX
   - 주소와 Linux 쪽 역할이 확정되지 않았다.
3. USB0 / SERDES0
   - Linux는 `USB2-only + OTG`로 올렸고, unresolved는 사실상 SERDES0 routing policy다.
4. memory / reserved-memory / regulator / PMIC
   - memory node는 반영했지만 regulator/PMIC binding과 reserved-memory 최종 정책은 아직 정리되지 않았다.

## 다음 사용자 결정이 필요한 항목

1. LPDDR4 size와 Linux memory node
2. OP-TEE / R5 / shared memory carveout 최종 유지 여부
3. TPM `U15` 채택 여부와 compatible
4. CPSW reset GPIO / interrupt GPIO 연결 방식
5. TPS6522053 Linux binding 및 regulator model
