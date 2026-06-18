# Evidence Map v0.3

이 문서는 PDF 45 page 전체를 DTS 목적 DB에 1:1로 대응시키기 위한 coverage map이다.

| Page | 회로도 제목 | DTS relevance | DB 반영 요약 |
|---:|---|---|---|
| 1 | DESIGN SUMMARY | dts_relevant | Board identity and primary BOM: AM6412BSCGHAALV, LPDDR4, OSPI, eMMC, DP83867IRRGZ, AT97SC3205T, XC7A15T.; Page index is the master page coverage source. |
| 2 | DESIGN HISTORY | indirect_or_supporting | Revision changes include component substitutions and nets added; DTS impact is indirect except changed parts/nets must be treated as latest revision. |
| 3 | BLOCK DIAGRAM | dts_relevant | Block diagram identifies system-level data paths: AM6412 to DDR, OSPI, eMMC, Ethernet PHY, FPGA, TPM, temp monitor, PMIC, UART/USB debug, VPX. |
| 4 | POWER DIAGRAM | indirect_or_supporting | Power diagram visually summarizes rail producers/consumers; captured as power-tree source, but exact rail graph should be cross-checked from pages 37-40. |
| 5 | POWER SEQUENCE | indirect_or_supporting | Power sequence shows rail order and reset release timing; DTS implication is boot-on/always-on regulator ordering, not direct Linux sequencing. |
| 6 | GPIO MAPPING | indirect_or_supporting | GPIO mapping page is blank; no PDF facts to extract except absence of mapping table. |
| 7 | I2C TREE | indirect_or_supporting | I2C TREE page says content to be added and I2C ADDRESS; actual I2C device/address facts must come from pages 23-25 and 39. |
| 8 | BLANK | not_dts_relevant_blank | Blank page; no DTS-relevant facts. |
| 9 | BLANK | not_dts_relevant_blank | Blank page; no DTS-relevant facts. |
| 10 | SoC POWER & GND | dts_relevant | SoC power pins and rails listed: VDD_CORE, VDD_LPDDR4, VDDAR_CORE, SoC_DVDD3V3, SoC_DVDD1V8, VDDSHV_SD_IO, VDD_DLL_MMC0, VDD_MMC1, VDDA rails.; ADC0_REFP/REFN D-Note captured; ADC reference is hardware fact, not a Linux thermal sensor node by itself.; MMCSD1_HOST_CONTROL2 V1P8_SIGNAL_ENA note captured; relevant only if MMC1/SDIO is used. |
| 11 | SoC ANALOG POWER & DECAP | dts_relevant | SoC analog/core rail decoupling and rail names captured; DTS impact mostly regulator supply naming and always-on constraints. |
| 12 | SoC LPDDR4 | dts_relevant | AM6412 DDR0 signal side and LPDDR4 signal groups captured; DTS impact is memory node only, DDR training belongs to bootloader DDR config. |
| 13 | SoC MMC | dts_relevant | MMC0 is eMMC 8-bit. MMC1 SD Card 4-bit is Not Used. SoC UART2 TXD note points to page 30. |
| 14 | SoC OSPI | dts_relevant | OSPI flash is Macronix MX66UM1G45GXDR00-T, capacity changed 512Mb to 1Gb, Infineon to Macronix.; OSPI is wired DQ0-DQ7 plus DQS, CLK, CSn, RESET#, INT#.; D-Note: external loopback clock series resistors DNI when DQS is connected.; GPIO0_13/GPIO0_14 labels imply GPIO-based reset/int candidates, requiring mapping cross-check. |
| 15 | SoC JTAG | dts_relevant | SoC JTAG pins EMU0/1, TCK/TDI/TDO/TMS/TRSTN; DTS impact low, debug hardware path to VPX/JTAG. |
| 16 | SoC PRG (RGMII) | dts_relevant | CPSW RGMII1/RGMII2 signal breakout, MDIO/MDC shared.; RGMII/PMIC interrupt pin setting note points to EXTINTN/C19.; PMIC_STBY and VSEL_SD_SWITCH are exposed from SoC PRG pins.; GPMC address[10:1] and UART2 RXD are muxed/represented here. |
| 17 | SoC GPMC BUS / BOOTMODE | dts_relevant | GPMC0_AD[15:0] are used as 16-bit boot mode straps and as FPGA async non-multiplexed 16-bit NOR access interface.; Bootmode values are printed: BOOTMODE0=1,1=1,2=0,3=1,4=0,5=0,6=0,7=0(OSPI CS0n),8=1(internal clock), 9/13/14/15 reserved, 10/11/12 none.; SN74AVC8T245 transceiver isolation after reset; DTS must not enable GPMC blindly without FPGA memory-map/timing policy. |
| 18 | SoC USB & SERDES | dts_relevant | USB0 DP/DM, VBUS detect/divider, USB0_ID, USB0_DRVVBUS with TPS2051B power switch.; USB0_ID GND=host, float=slave note captured.; SERDES0 may be PCIe Gen2 or USB SuperSpeed; future PCIe switch PI7C9X2G304EV note.; DTS mode remains policy because schematic shows capability, not final product mode. |
| 19 | SoC SYSTEM & I2C & UART | dts_relevant | EXTINTN C19 is used for RGMII & PMIC interrupt setting: GPIO1_70 note.; I2C0/I2C1, UART0/1, MCU_UART0/1, reset status/request pins, TEST_LED1/2 are shown.; SoC reset-status and MCU reset-domain explanatory notes captured. |
| 20 | SYSTEM RESET | dts_relevant | System reset and power-on reset: SYSRESETn, MCU_PORz, PMIC_PGOOD, P0_SYSRESETn, MAX6816 debounce, gates.; DTS impact is mostly reset-controller/GPIO documentation; SoC reset itself is board hardware. |
| 21 | SYSTEM CLOCK | dts_relevant | System clock: LMK1C1106 25MHz fanout to MCU_CLK_25MHz, CPSW PHY clocks, FPGA_CLK_25MHz.; CDCE6214RGET HCSL 100MHz clock generator on I2C1 with outputs to SERDES/FPGA/IO board refs.; GPIO1-4 output enable notes captured; Linux clock control decision requires policy/binding. |
| 22 | LPDDR4 | dts_relevant | LPDDR4 U12 MT53E1G16D1ZW-046 AIT-C, 16Gbit/2GByte, 1Gx16, package/revision change notes.; DTS memory size fact: 2GB candidate; DDR configuration remains bootloader asset. |
| 23 | PCIe Channel Exchange Switch / I2C0 EEPROM | dts_relevant | I2C0 Board ID EEPROM U14 AT24C512C-MAHM-E address 0x51, write 0xA2/read 0xA3.; PCIe/SERDES channel switch U13 PI3DBS16222Q between AM6412, FPGA, and VITA path. |
| 24 | I2C1 TPM (for TEST) | dts_relevant | I2C1 TPM U15 AT97SC3205T-U3A1C-10 address 0x29, reset pulse width minimum 2us, RC delay 2ms.; TPM is marked for TEST; DTS status should follow product policy. |
| 25 | I2C1 Temperature Monitor | dts_relevant | I2C1 temperature monitor: ADS1115QNKSRQ1 address 0x48 with TMP235A2DBZR sensors on AIN0-3 through PI6ULS5V9509UEX level translator. |
| 26 | eMMC | dts_relevant | eMMC schematic page labels U22 as MKEMF032GT2E-IE, MMC0 DAT0-7, DS, CMD, CLK, RST_N; part/capacity history: 4GB->32GB latest note.; Actual assembled-board override tracked in DB: MX52LM04A11XSI.; GPIO_eMMC_RSTn/MMC0_RSTn reset logic shown; reset provider must be mapped with netlist or GPIO page. |
| 27 | ETHERNET PHY1 | dts_relevant | Ethernet PHY1 U24 DP83867IRRGZ, RGMII1, shared MDIO/MDC, 25MHz clock, reset GPIO_CPSW1_RST, interrupt CPSW_RGMII1_INTn/RGMII_INTn, magnetics to LAN1 VPX. |
| 28 | ETHERNET PHY2 | dts_relevant | Ethernet PHY2 U26 DP83867IRRGZ, RGMII2, shared MDIO/MDC, 25MHz clock, reset GPIO_CPSW2_RST, interrupt CPSW_RGMII2_INTn, magnetics to LAN2 VPX. |
| 29 | ETHERNET PHY STRAP | dts_relevant | PHY strap summaries: PHY1 address 0000, PHY2 address 0001; autoneg enable; TX skew 001 listed as 0ns; RX skew 000 listed as 2.0ns; mirror disabled.; LED strap mode notes captured. |
| 30 | DEBUG (UART to USB) | dts_relevant | CP2105 debug USB bridge: SoC UART0 enhanced comm, MCU UART0 standard comm.; UART to RS232 via MAX3222 and UART to RS422 via MAX33048 paths to VPX.; SoC UART1/UART2 signals are present but final Linux enable policy depends on intended external use. |
| 31 | FPGA CONFIG | dts_relevant | FPGA config: Artix-7 XC7A15T, config Bank0 3.3V, JTAG, QSPI NOR flash MX25L25645GZNI, DONE/PROGRAM status LEDs, no used notes. |
| 32 | FPGA BANK14 | dts_relevant | FPGA Bank14 control/status: GEO address, SoC_PORz_OUT, SoC_RESET_REQz, SoC_RESETSTATz, PMIC_PGOOD, SYSRESETn, TPS22965_EN, VPP_LDO_EN, GPIO_CPSW1_RST, GPIO_CPSW2_RST, CDC_OE1/OE4, LM61460_EN/PG, TPS6522053_EN.; This page is key for GPIO/reset provider semantics; many signals are FPGA-mediated, not direct SoC Linux GPIO. |
| 33 | FPGA BANK15 | dts_relevant | FPGA Bank15 maps GPMC data[15:0], address[10:1], and commands CLK, CS0n, BE0_n, OEn, WEn, BE1_n to FPGA. |
| 34 | FPGA BANK34 | dts_relevant | FPGA Bank34 GPIO 8 Port to VPX P2, FPGA_CLK_25MHz, test LEDs low active, PMIC power good/TPS22965_EN monitoring. |
| 35 | FPGA BANK216 (GTP) | dts_relevant | FPGA Bank216 GTP SERDES test lanes: FPGA_SERDES_RX/TX and FPGA_REFCLK_P/N; AC coupling/resistor notes. |
| 36 | FPGA POWER | indirect_or_supporting | FPGA power rails and sequence: VCCINT/VCCBRAM/MGTAVCC 1.0V, MGTAVTT 1.2V, VCCAUX 1.8V, VCCO 3.3V. |
| 37 | POWER FPGA PMIC | indirect_or_supporting | FPGA PMIC uses LTM4668AEY rails: +1.0V_FPGA, +1.2V_FPGA, +1.8V_FPGA, +3.3V_FPGA, +1.0V_GTP; sequence delays 0/10/20/30ms. |
| 38 | POWER 5V MAIN INPUT | dts_relevant | Main 5V input to 3.3V system buck LM61460, output VCC3V3SYS_EXT, EN LM61460_EN, PG LM61460_PG, 6A/400kHz notes. |
| 39 | POWER 5V PMIC | dts_relevant | SoC PMIC TPS6522053RHBR/TPS65220-class, I2C0 address 0x30, interrupt PMIC_INTn into RGMII/PMIC interrupt aggregation.; Rail table: BUCK1 0.75V VDD_CORE, BUCK2 1.8V VCC1V8/SoC_DVDD1V8, BUCK3 1.1V VDD_LPDDR4, LDO1 3.3V/1.8V SD/IO, LDO2 0.85V VDDAR_CORE, LDO3 1.8V VDDA_1V8, LDO4 2.5V VDD_PHY_2V5. |
| 40 | POWER 5V ETC | dts_relevant | Power ETC: TPS22965 3V3 load switch, TLV75510 VDD_1V0 for Ethernet PHY, TLV75518 VPP_1V8 with strict eFuse programming warning. |
| 41 | FRONT INTERFACE | indirect_or_supporting | Front panel: USB debug Type-C to CP2105 USB_DEBUG_DP/DN, FPGA JTAG header. Mechanical footprint warning. |
| 42 | REAR VITA 46.0 P0 | dts_relevant | VPX P0 utility connector: power rails, geo address, SoC JTAG, P0_SYSRESETn, IOB_REFCLK_P/N. |
| 43 | REAR VITA 46.0 P1 | dts_relevant | VPX P1 data/control plane: USB0 DP/DM/VBUS, LAN1/LAN2 MDI pairs, VITA_SERDES TX/RX, RS232/RS422, ESD protection. |
| 44 | REAR VITA 46.0 P2 | dts_relevant | VPX P2 GPIO 8 Port from FPGA Bank34; connector differential template mostly unused for DTS except GPIO exported path. |
| 45 | HOLE | indirect_or_supporting | PCB holes, VITA guide/screw holes; mechanical/GND note. No direct DTS node, but chassis/frame ground note captured for hardware docs. |
