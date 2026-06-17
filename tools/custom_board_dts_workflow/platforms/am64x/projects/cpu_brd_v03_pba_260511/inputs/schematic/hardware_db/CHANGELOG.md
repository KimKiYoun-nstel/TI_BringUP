# Changelog

## v0.2

- 기존 v0.1 DB를 회로도 의도 중심으로 재구성.
- schema와 fact/policy/observation 분류 체계 추가.
- Memory/reserved-memory 분리.
- Boot media를 SD/eMMC/OSPI/Bootmode strap 단위로 상세화.
- Power tree를 main 3.3V, system PMIC, etc power, FPGA power로 분리.
- Interface DB에 UART/I2C/Ethernet/USB/SerDes/GPMC-FPGA 반영.
- Reset/interrupt/GPIO provider 미확정 항목을 명시.
- Clocking, FPGA semantics, VPX connector DB 추가.
- delivery DTS gap report 및 evidence map 추가.

## v0.1

- 초기 hardware semantic DB skeleton.
