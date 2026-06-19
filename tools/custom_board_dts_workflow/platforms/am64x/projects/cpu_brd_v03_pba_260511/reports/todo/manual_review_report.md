# Manual Review Report

이 파일은 stage1 lookup 기준으로 facts/candidates/base 출력만으로 확정할 수 없는 항목을 모은다.
`board_dts_decisions.yaml`로 explicit override된 항목은 다음 regenerate부터 이 보고서에서 해소될 수 있다.
반대로 `generated/*/final/`에서만 수동 편집하고 decision YAML로 back-annotate하지 않은 항목은 이 보고서에 다시 남을 수 있다.

- unmatched soc pins: 0
- out-of-scope non-mux pins: 146
- conflicting DB lookups: 0
- non-pinctrl or pre-Linux hardware facts: 68
- alternate function or GPIO review items: 15
- explicit board mux decisions loaded: 9

## Non-Pinctrl / Pre-Linux Hardware Facts
### Clock / Reference Input
- count: 1
- C21 MCU_OSC0_XI source=`U1-C21 AM6412-MCU_OSC0_XI PASSIVE` note=soc_pin_name:MCU_OSC0_XI; system/reset/debug/clock hardware fact

### Controller-Only Linux DTS
- count: 12
- F18 MMC0_CALPAD source=`U1-F18 AM6412-MMC0_CALPAD PASSIVE` note=soc_pin_name:MMC0_CALPAD; controller-only DTS path without padconfig
- G17 MMC0_DAT7 source=`U1-G17 AM6412-MMC0_DAT7 PASSIVE` note=soc_pin_name:MMC0_DAT7; controller-only DTS path without padconfig
- G18 MMC0_CLK source=`U1-G18 AM6412-MMC0_CLK PASSIVE` note=soc_pin_name:MMC0_CLK; controller-only DTS path without padconfig
- G19 MMC0_DS source=`U1-G19 AM6412-MMC0_DS PASSIVE` note=soc_pin_name:MMC0_DS; controller-only DTS path without padconfig
- H17 MMC0_DAT4 source=`U1-H17 AM6412-MMC0_DAT4 PASSIVE` note=soc_pin_name:MMC0_DAT4; controller-only DTS path without padconfig
- H18 MMC0_DAT6 source=`U1-H18 AM6412-MMC0_DAT6 PASSIVE` note=soc_pin_name:MMC0_DAT6; controller-only DTS path without padconfig
- H19 MMC0_DAT5 source=`U1-H19 AM6412-MMC0_DAT5 PASSIVE` note=soc_pin_name:MMC0_DAT5; controller-only DTS path without padconfig
- J17 MMC0_DAT3 source=`U1-J17 AM6412-MMC0_DAT3 PASSIVE` note=soc_pin_name:MMC0_DAT3; controller-only DTS path without padconfig
- J18 MMC0_DAT2 source=`U1-J18 AM6412-MMC0_DAT2 PASSIVE` note=soc_pin_name:MMC0_DAT2; controller-only DTS path without padconfig
- J20 MMC0_DAT1 source=`U1-J20 AM6412-MMC0_DAT1 PASSIVE` note=soc_pin_name:MMC0_DAT1; controller-only DTS path without padconfig
- J21 MMC0_CMD source=`U1-J21 AM6412-MMC0_CMD PASSIVE` note=soc_pin_name:MMC0_CMD; controller-only DTS path without padconfig
- K20 MMC0_DAT0 source=`U1-K20 AM6412-MMC0_DAT0 PASSIVE` note=soc_pin_name:MMC0_DAT0; controller-only DTS path without padconfig

### DDR / Bootloader Domain
- count: 35
- A2 DDR0_DQ1 source=`U1-A2 AM6412-DDR0_DQ1 PASSIVE` note=soc_pin_name:DDR0_DQ1; pre-Linux controller or PHY domain
- A3 DDR0_DQ0 source=`U1-A3 AM6412-DDR0_DQ0 PASSIVE` note=soc_pin_name:DDR0_DQ0; pre-Linux controller or PHY domain
- A4 DDR0_DQ3 source=`U1-A4 AM6412-DDR0_DQ3 PASSIVE` note=soc_pin_name:DDR0_DQ3; pre-Linux controller or PHY domain
- B1 DDR0_DQS0_n source=`U1-B1 AM6412-DDR0_DQS0_N PASSIVE` note=soc_pin_name:DDR0_DQS0_N; pre-Linux controller or PHY domain
- B2 DDR0_DM0 source=`U1-B2 AM6412-DDR0_DM0 PASSIVE` note=soc_pin_name:DDR0_DM0; pre-Linux controller or PHY domain
- B3 DDR0_DQ4 source=`U1-B3 AM6412-DDR0_DQ4 PASSIVE` note=soc_pin_name:DDR0_DQ4; pre-Linux controller or PHY domain
- B4 DDR0_DQ7 source=`U1-B4 AM6412-DDR0_DQ7 PASSIVE` note=soc_pin_name:DDR0_DQ7; pre-Linux controller or PHY domain
- B5 DDR0_DQ2 source=`U1-B5 AM6412-DDR0_DQ2 PASSIVE` note=soc_pin_name:DDR0_DQ2; pre-Linux controller or PHY domain
- C1 DDR0_DQS0 source=`U1-C1 AM6412-DDR0_DQS0 PASSIVE` note=soc_pin_name:DDR0_DQS0; pre-Linux controller or PHY domain
- C2 DDR0_DQ6 source=`U1-C2 AM6412-DDR0_DQ6 PASSIVE` note=soc_pin_name:DDR0_DQ6; pre-Linux controller or PHY domain
- C4 DDR0_DQ5 source=`U1-C4 AM6412-DDR0_DQ5 PASSIVE` note=soc_pin_name:DDR0_DQ5; pre-Linux controller or PHY domain
- C5 DDR0_A1 source=`U1-C5 AM6412-DDR0_A1 PASSIVE` note=soc_pin_name:DDR0_A1; pre-Linux controller or PHY domain
- D2 DDR0_A0 source=`U1-D2 AM6412-DDR0_A0 PASSIVE` note=soc_pin_name:DDR0_A0; pre-Linux controller or PHY domain
- D3 DDR0_A4 source=`U1-D3 AM6412-DDR0_A4 PASSIVE` note=soc_pin_name:DDR0_A4; pre-Linux controller or PHY domain
- D4 DDR0_A3 source=`U1-D4 AM6412-DDR0_A3 PASSIVE` note=soc_pin_name:DDR0_A3; pre-Linux controller or PHY domain
- D5 DDR0_RESET0_n source=`U1-D5 AM6412-DDR0_RESET0_N PASSIVE` note=soc_pin_name:DDR0_RESET0_N; pre-Linux controller or PHY domain
- E1 DDR0_CK0_n source=`U1-E1 AM6412-DDR0_CK0_N PASSIVE` note=soc_pin_name:DDR0_CK0_N; pre-Linux controller or PHY domain
- E2 DDR0_A2 source=`U1-E2 AM6412-DDR0_A2 PASSIVE` note=soc_pin_name:DDR0_A2; pre-Linux controller or PHY domain
- E3 DDR0_CS0_n source=`U1-E3 AM6412-DDR0_CS0_N PASSIVE` note=soc_pin_name:DDR0_CS0_N; pre-Linux controller or PHY domain
- E4 DDR0_CS1_n source=`U1-E4 AM6412-DDR0_CS1_N PASSIVE` note=soc_pin_name:DDR0_CS1_N; pre-Linux controller or PHY domain
- F1 DDR0_CK0 source=`U1-F1 AM6412-DDR0_CK0 PASSIVE` note=soc_pin_name:DDR0_CK0; pre-Linux controller or PHY domain
- F2 DDR0_A5 source=`U1-F2 AM6412-DDR0_A5 PASSIVE` note=soc_pin_name:DDR0_A5; pre-Linux controller or PHY domain
- F4 DDR0_CKE0 source=`U1-F4 AM6412-DDR0_CKE0 PASSIVE` note=soc_pin_name:DDR0_CKE0; pre-Linux controller or PHY domain
- H5 DDR0_CAL0 source=`U1-H5 AM6412-DDR0_CAL0 PASSIVE` note=soc_pin_name:DDR0_CAL0; pre-Linux controller or PHY domain
- L2 DDR0_DQ10 source=`U1-L2 AM6412-DDR0_DQ10 PASSIVE` note=soc_pin_name:DDR0_DQ10; pre-Linux controller or PHY domain
- L4 DDR0_DQ9 source=`U1-L4 AM6412-DDR0_DQ9 PASSIVE` note=soc_pin_name:DDR0_DQ9; pre-Linux controller or PHY domain
- M1 DDR0_DQS1_n source=`U1-M1 AM6412-DDR0_DQS1_N PASSIVE` note=soc_pin_name:DDR0_DQS1_N; pre-Linux controller or PHY domain
- M2 DDR0_DM1 source=`U1-M2 AM6412-DDR0_DM1 PASSIVE` note=soc_pin_name:DDR0_DM1; pre-Linux controller or PHY domain
- M3 DDR0_DQ11 source=`U1-M3 AM6412-DDR0_DQ11 PASSIVE` note=soc_pin_name:DDR0_DQ11; pre-Linux controller or PHY domain
- M4 DDR0_DQ14 source=`U1-M4 AM6412-DDR0_DQ14 PASSIVE` note=soc_pin_name:DDR0_DQ14; pre-Linux controller or PHY domain
- N1 DDR0_DQS1 source=`U1-N1 AM6412-DDR0_DQS1 PASSIVE` note=soc_pin_name:DDR0_DQS1; pre-Linux controller or PHY domain
- N2 DDR0_DQ15 source=`U1-N2 AM6412-DDR0_DQ15 PASSIVE` note=soc_pin_name:DDR0_DQ15; pre-Linux controller or PHY domain
- N3 DDR0_DQ13 source=`U1-N3 AM6412-DDR0_DQ13 PASSIVE` note=soc_pin_name:DDR0_DQ13; pre-Linux controller or PHY domain
- N4 DDR0_DQ12 source=`U1-N4 AM6412-DDR0_DQ12 PASSIVE` note=soc_pin_name:DDR0_DQ12; pre-Linux controller or PHY domain
- N5 DDR0_DQ8 source=`U1-N5 AM6412-DDR0_DQ8 PASSIVE` note=soc_pin_name:DDR0_DQ8; pre-Linux controller or PHY domain

### Manual Review Required
- count: 14
- A12 TDO source=`U1-A12 AM6412-TDO OUTPUT` note=soc_pin_name:TDO; system/reset/debug/clock hardware fact
- A20 MCU_SAFETY_ERRORn source=`U1-A20 AM6412-MCU_SAFETY_ERRORN PASSIVE` note=soc_pin_name:MCU_SAFETY_ERRORN; system/reset/debug/clock hardware fact
- B11 TCK source=`U1-B11 AM6412-TCK INPUT` note=soc_pin_name:TCK; system/reset/debug/clock hardware fact
- B12 MCU_RESETz source=`U1-B12 AM6412-MCU_RESETZ PASSIVE` note=soc_pin_name:MCU_RESETZ; system/reset/debug/clock hardware fact
- B13 MCU_RESETSTATz source=`U1-B13 AM6412-MCU_RESETSTATZ PASSIVE` note=soc_pin_name:MCU_RESETSTATZ; system/reset/debug/clock hardware fact
- B21 MCU_PORz source=`U1-B21 AM6412-MCU_PORZ PASSIVE` note=soc_pin_name:MCU_PORZ; system/reset/debug/clock hardware fact
- C11 TDI source=`U1-C11 AM6412-TDI INPUT` note=soc_pin_name:TDI; system/reset/debug/clock hardware fact
- C12 TMS source=`U1-C12 AM6412-TMS PASSIVE` note=soc_pin_name:TMS; system/reset/debug/clock hardware fact
- D10 EMU0 source=`U1-D10 AM6412-EMU0 PASSIVE` note=soc_pin_name:EMU0; system/reset/debug/clock hardware fact
- D11 TRSTn source=`U1-D11 AM6412-TRSTN PASSIVE` note=soc_pin_name:TRSTN; system/reset/debug/clock hardware fact
- E10 EMU1 source=`U1-E10 AM6412-EMU1 PASSIVE` note=soc_pin_name:EMU1; system/reset/debug/clock hardware fact
- E17 PORz_OUT source=`U1-E17 AM6412-PORZ_OUT PASSIVE` note=soc_pin_name:PORZ_OUT; system/reset/debug/clock hardware fact
- E18 RESET_REQz source=`U1-E18 AM6412-RESET_REQZ PASSIVE` note=soc_pin_name:RESET_REQZ; system/reset/debug/clock hardware fact
- F16 RESETSTATz source=`U1-F16 AM6412-RESETSTATZ PASSIVE` note=soc_pin_name:RESETSTATZ; system/reset/debug/clock hardware fact

### USB / PHY Domain
- count: 6
- AA19 USB0_DP source=`U1-AA19 AM6412-USB0_DP PASSIVE` note=soc_pin_name:USB0_DP; pre-Linux controller or PHY domain
- AA20 USB0_DM source=`U1-AA20 AM6412-USB0_DM PASSIVE` note=soc_pin_name:USB0_DM; pre-Linux controller or PHY domain
- E19 USB0_DRVVBUS source=`U1-E19 AM6412-USB0_DRVVBUS PASSIVE` note=soc_pin_name:USB0_DRVVBUS; pre-Linux controller or PHY domain
- T14 USB0_VBUS source=`U1-T14 AM6412-USB0_VBUS PASSIVE` note=soc_pin_name:USB0_VBUS; pre-Linux controller or PHY domain
- U16 USB0_ID source=`U1-U16 AM6412-USB0_ID PASSIVE` note=soc_pin_name:USB0_ID; pre-Linux controller or PHY domain
- U17 USB0_RCALIB source=`U1-U17 AM6412-USB0_RCALIB PASSIVE` note=soc_pin_name:USB0_RCALIB; pre-Linux controller or PHY domain

## Alternate Function / GPIO Review
- AA2 PRG0_PRU0_GPO4 net=GPMC0_A1 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO4 reason=soc_pin_name:PRG0_PRU0_GPO4; alternate function hinted by net name on same ball
- R18 GPMC0_OEN_REN net=GPMC0_OEN result=GPIO_CANDIDATE db_signal=GPMC0_OEn_REn reason=soc_pin_name:GPMC0_OEN_REN; net or connected circuit suggests GPIO-style usage
- T2 PRG0_PRU0_GPO8 net=GPMC0_A2 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO8 reason=soc_pin_name:PRG0_PRU0_GPO8; alternate function hinted by net name on same ball
- T21 GPMC0_WEN net=GPMC0_WEN result=GPIO_CANDIDATE db_signal=GPMC0_WEn reason=soc_pin_name:GPMC0_WEN; net or connected circuit suggests GPIO-style usage
- T6 PRG0_PRU1_GPO13 net=GPMC0_A8 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU1_GPO13 reason=soc_pin_name:PRG0_PRU1_GPO13; alternate function hinted by net name on same ball
- U15 PRG1_PRU0_GPO9 net=CPSW_RGMII1_TX_CTRL result=GPIO_CANDIDATE db_signal=PRG1_PRU0_GPO9 reason=soc_pin_name:PRG1_PRU0_GPO9; net or connected circuit suggests GPIO-style usage
- U4 PRG0_PRU0_GPO16 net=GPMC0_A4 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO16 reason=soc_pin_name:PRG0_PRU0_GPO16; alternate function hinted by net name on same ball
- U5 PRG0_PRU1_GPO15 net=GPMC0_A10 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU1_GPO15 reason=soc_pin_name:PRG0_PRU1_GPO15; alternate function hinted by net name on same ball
- U6 PRG0_PRU1_GPO14 net=GPMC0_A9 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU1_GPO14 reason=soc_pin_name:PRG0_PRU1_GPO14; alternate function hinted by net name on same ball
- V1 PRG0_PRU0_GPO18 net=GPMC0_A5 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO18 reason=soc_pin_name:PRG0_PRU0_GPO18; alternate function hinted by net name on same ball
- V4 PRG0_PRU0_GPO14 net=GPMC0_A3 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO14 reason=soc_pin_name:PRG0_PRU0_GPO14; alternate function hinted by net name on same ball
- W1 PRG0_PRU0_GPO19 net=GPMC0_A6 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO19 reason=soc_pin_name:PRG0_PRU0_GPO19; alternate function hinted by net name on same ball
- W6 PRG0_PRU0_GPO9 net=SOC_UART2_RXD result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU0_GPO9 reason=soc_pin_name:PRG0_PRU0_GPO9; alternate function hinted by net name on same ball
- Y11 PRG1_PRU1_GPO15 net=CPSW_RGMII2_TX_CTRL result=GPIO_CANDIDATE db_signal=PRG1_PRU1_GPO15 reason=soc_pin_name:PRG1_PRU1_GPO15; net or connected circuit suggests GPIO-style usage
- Y4 PRG0_PRU1_GPO12 net=GPMC0_A7 result=ALT_FUNCTION_REVIEW db_signal=PRG0_PRU1_GPO12 reason=soc_pin_name:PRG0_PRU1_GPO12; alternate function hinted by net name on same ball

## Out Of Scope Summary
### Analog / Reference
- count: 10
- sample: H10:CAP_VDDS_MCU, H12:CAP_VDDS0, J15:ADC0_REFP, J16:ADC0_REFN, K15:CAP_VDDSHV_MMC1, L13:CAP_VDDS5, M16:CAP_VDDS4, N14:CAP_VDDS3

### PHY / Analog Reference
- count: 7
- sample: AA16:SERDES0_TX0_N, AA17:SERDES0_TX0_P, T13:SERDES0_REXT, W16:SERDES0_REFCLK0N, W17:SERDES0_REFCLK0P, Y15:SERDES0_RX0_N, Y16:SERDES0_RX0_P

### Power / Ground / Monitor
- count: 129
- sample: A1:VSS_P, A21:VSS_P, A5:VSS_P, A6:VSS_P, AA1:VSS_P, AA15:VSS_P, AA18:VSS_P, AA21:VSS_P
