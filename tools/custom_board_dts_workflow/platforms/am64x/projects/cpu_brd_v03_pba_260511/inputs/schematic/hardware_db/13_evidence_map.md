# Evidence Map

이 문서는 PDF 회로도 page별로 DTS/Bring-up DB에 반영한 의미를 추적하기 위한 맵이다.

| Page | 회로도 제목 | DB 반영 요약 |
|---:|---|---|
| 1 | Design Summary | 보드 identity, AM6412, LPDDR4, OSPI, eMMC, DP83867, TPM, FPGA 주요 부품 |
| 10 | SoC POWER & GND | SoC rail, SR2.0 note, ADC reference note, VDDSHV/SDIO 전압 관련 note |
| 11 | SoC ANALOG POWER & DECAP | SoC analog/core rail dependency, MMCSD1 voltage note |
| 12 | SoC LPDDR4 | AM6412 DDR signal side, LPDDR4 decap/EMI filter |
| 13 | SoC MMC | MMC0 eMMC 8bit, MMC1 SD Card Not Used, UART2 TXD note |
| 14 | SoC OSPI | MX66UM1G45GXDR00-T, 8-bit DQ, DQS, reset/int, Macronix 변경 note |
| 15 | SoC JTAG | SoC JTAG to VPX/P0 path 후보 |
| 16 | SoC PRG (RGMII) | CPSW RGMII signals, PMIC_STBY, VSEL_SD_SWITCH, UART2 RXD, GPMC address |
| 17 | SoC GPMC BUS | BOOTMODE strap, GPMC AD[15:0], transceiver isolation, FPGA async NOR-like IF |
| 18 | SoC USB & SERDES | USB0 VBUS/ID/DRVVBUS, TPS2051B, SERDES0 PCIe/USB SS note |
| 19 | SoC SYSTEM & I2C & UART | EXTINTN/C19 aggregation note, I2C0/1, UART0/1, MCU UART0, TEST LED |
| 20 | SYSTEM RESET | SYSRESETn, MCU_PORz, PMIC_PGOOD/P0_SYSRESETn 관계 |
| 21 | SYSTEM CLOCK | LMK1C1106 25MHz fanout, CDCE6214 100MHz HCSL clock generator |
| 22 | LPDDR4 | U12 LPDDR4, 16Gbit/2GB/1Gx16, package/part change notes |
| 23 | PCIe Channel Exchange Switch / I2C0 EEPROM | PI3DBS16222Q SerDes switch, AT24C512C EEPROM address 0x51 |
| 24 | I2C1 TPM (for TEST) | U15 AT97SC3205T, address 0x29, reset pulse note |
| 25 | I2C1 Temperature Monitor | TMP235 sensors, ADS1115 address 0x48, AIN0-3 mapping |
| 26 | eMMC | U22 eMMC, MMC0 signals, GPIO_eMMC_RSTn, power rails, part change notes |
| 27 | Ethernet PHY1 | U24 DP83867, RGMII1, reset/int, magnetics, LAN1 VPX path |
| 28 | Ethernet PHY2 | U26 DP83867, RGMII2, reset/int, magnetics, LAN2 VPX path |
| 29 | Ethernet PHY Strap | PHY address 0/1, autoneg, TX/RX clock skew strap summary |
| 30 | DEBUG (UART to USB) | CP2105, SoC UART0, MCU UART0, UART1/2, RS232/RS422 paths |
| 31 | FPGA CONFIG | Artix7 config, QSPI flash, JTAG, DONE/PROGRAM status |
| 32 | FPGA BANK14 | FPGA control/status: PMIC enable, VPP_LDO_EN, CPSW reset, clock OE, LM61460_EN |
| 33 | FPGA BANK15 | GPMC data/address/command to FPGA |
| 34 | FPGA BANK34 | GPIO 8 port, low-active LEDs, PMIC PG/TPS22965_EN monitoring |
| 35 | FPGA BANK216 (GTP) | FPGA SerDes test lanes and refclock |
| 36 | FPGA POWER | FPGA rails and sequence |
| 37 | POWER FPGA PMIC | LTM4668 rails and power sequence |
| 38 | POWER 5V MAIN INPUT | LM61460 5V->3.3V 6A, EN/PG |
| 39 | POWER 5V PMIC | TPS6522053/TPS65220 address 0x30, BUCK/LDO rails, interrupt aggregation |
| 40 | POWER ETC | 3V3 load switch, VDD_1V0, VPP_1V8 strict eFuse sequence |
| 42 | REAR VITA 46.0 P0 | VPX utility, power, geo address, JTAG, SYSRESET, refclock |
| 43 | REAR VITA 46.0 P1 | USB/LAN/SerDes/RS232/RS422 connector paths |
| 44 | REAR VITA 46.0 P2 | GPIO rear/front expansion candidates |
