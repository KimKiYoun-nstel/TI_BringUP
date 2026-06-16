# Tests

권장 smoke test:

1. Load DB and find UART0_RXD at D15 offset 0x0230.
2. Load DB and find UART0_TXD at C16 offset 0x0234.
3. Load DB and find I2C0_SCL/A18 and I2C0_SDA/B18.
4. Load DB and find MCU_UART0_RXD/A9 and MCU_UART0_TXD/A8.
5. Parse `.NET` and extract U1 SoC pins.
6. Generate pinmux DTSI and verify `AM64X_IOPAD` / `AM64X_MCU_IOPAD` usage.
7. Generate maximal DTS and verify it includes `k3-am642.dtsi` but not `k3-am642-sk.dts`.
8. Verify unresolved external device properties are emitted with TODO comments.
