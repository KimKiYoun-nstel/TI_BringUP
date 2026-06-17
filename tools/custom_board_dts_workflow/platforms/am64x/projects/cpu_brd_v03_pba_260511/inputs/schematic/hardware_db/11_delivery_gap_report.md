# delivery DTS 보강 Gap Report v0.2

이 문서는 `delivery.zip`의 현재 DTS/DTSI와 `CPU_Brd_V03_PBA_260511.pdf` 기반 hardware semantic DB를 비교해, DTS 생성 AI Agent가 우선 보강해야 할 항목을 정리한다.

## High Priority

### 1. memory node 누락

- 회로도 근거: LPDDR4 U12 `MT53E1G16D1ZW-046 AIT-C`, 16Gbit/2GByte/1Gx16.
- 현재 delivery: `k3-am6412-cpu-brd-v03-pba.dts`에 `memory@80000000` TODO만 존재.
- 조치: DDR size 2GB 기준 `memory@80000000` 추가.

### 2. reserved-memory / IPC policy 누락

- 회로도 근거가 아니라 BSP policy 항목.
- 현재 delivery: reserved-memory 없음.
- 조치: SK-AM64B reference의 OP-TEE/R5F carveout baseline을 복사 후보로 두고 DDR=2GB, remoteproc/RPMsg 사용 여부 확인 후 적용.

### 3. PMIC/regulator tree 누락

- 회로도 근거: U38 TPS6522053RHBR, I2C0, 7-bit address 0x30, BUCK1/2/3 + LDO1/2/3/4 rail 정보.
- 현재 delivery: regulator/PMIC TODO만 존재.
- 조치: PMIC skeleton + regulator nodes 추가. 단 compatible과 constraints는 kernel binding 확인 필요.

### 4. eMMC supply/reset 미완성

- 회로도 근거: U22 MKEMF032GT2E-IE, MMC0 8-bit, VCC_3V3_SYS, VCC1V8, GPIO_eMMC_RSTn.
- 현재 delivery: `sdhci0 okay`, `bus-width=8`, `non-removable`만 존재.
- 조치: vmmc/vqmmc/reset 관련 binding 검토 후 추가.

### 5. OSPI single fallback policy 반영 필요

- 회로도 근거: U2 MX66UM1G45GXDR00-T, DQ0-DQ7, DQS, CS, CLK, RESET, INT.
- bring-up observation: Boot ROM octal boot 실패 후 single mode로 성공.
- 현재 delivery: flash node가 `spi-tx/rx-bus-width=<8>` 방향.
- 조치: 초기 bring-up/SPL용 profile은 single-width로 낮추고, octal profile은 deferred로 분리.

### 6. Ethernet PHY reset/interrupt provider 미확정

- 회로도 근거: U24/U26 DP83867, GPIO_CPSW1_RST/GPIO_CPSW2_RST, CPSW_RGMII1_INTn/CPSW_RGMII2_INTn, RGMII_INTn aggregation.
- 현재 delivery: PHY node는 있으나 reset/interrupt TODO.
- 조치: provider가 SoC GPIO인지 FPGA인지 확인 전까지 개별 reset-gpios/interrupts 확정 금지.

### 7. USB/SERDES policy 미정

- 회로도 근거: USB0, TPS2051B VBUS switch, USB0_ID host/slave note, SERDES0 PCIe Gen2/USB SuperSpeed 가능, PI3DBS16222Q channel switch.
- 현재 delivery: USB/SERDES TODO.
- 조치: USB2-only, USB3, PCIe, FPGA/VITA SerDes 중 사용할 모드 결정 후 DTS 생성.

### 8. GPMC-to-FPGA node enable 금지

- 회로도 근거: GPMC0_AD[15:0], A[10:1], command signals가 FPGA Bank15로 연결, Async Non-Multiplexed 16bit NOR Access I/F.
- 현재 delivery: pinctrl은 있으나 gpmc0 functional node 없음.
- 조치: 현 상태에서는 맞는 방향. FPGA register map/timing/ownership 확정 전 enable 금지.

## Medium Priority

### main_uart2 path review

- page 13/16/30에 TXD/RXD가 나뉘어 표시됨.
- delivery의 disabled/TODO 유지가 안전.

### TPM U15

- page 24에 AT97SC3205T-U3A1C-10, address 0x29 표기.
- for TEST 용도. production enable 여부 및 Linux compatible 검토 필요.

### ADS1115 temperature monitor

- page 25에 ADS1115 address 0x48, TMP235 analog sensors 4개.
- Linux에서 온도 모니터로 사용할 경우 `adc@48` 및 channel node 생성 후보.

### CDCE6214 clock generator

- page 21에 CDCE6214RGET, PCIe/SERDES/FPGA/IOB refclock.
- Linux에서 clock generator를 제어할지, static programmed clock으로 둘지 결정 필요.

## Agent Rule

DTS Agent는 이 DB를 사용할 때 다음 순서를 지켜야 한다.

1. `fact` 항목만으로 pinmux/peripheral existence를 판단한다.
2. `policy` 항목은 사용자가 명시하거나 repo policy 문서가 있을 때만 확정한다.
3. `review_required: true`인 항목은 DTS에 TODO 또는 disabled/review 상태로 남긴다.
4. 최종 DTS 생성 시 이 Gap Report를 업데이트한다.
