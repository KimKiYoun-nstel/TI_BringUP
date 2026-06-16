# AM64x SysConfig DB Extraction Report

- source_json: `/home/nstel/ti/ccs2040/ccs/utils/sysconfig_1.26.0/dist/deviceData/AM64x/AM64x.json`
- source_metadata: `/home/nstel/ti/ccs2040/ccs/utils/sysconfig_1.26.0/dist/deviceData/AM64x/metadata.bundle`
- output_dir: `/home/nstel/ti/ccs2040/ccs/utils/sysconfig_1.26.0/out`
- package: `ALV`
- devicePins: `441`
- peripheralPins: `1079`
- pinCommonInfos: `441`
- packagePin rows: `441`
- generated pinmux rows: `1271`
- missing ball rows by device pin: `0`
- pinCommonInfos with zero pinModeInfo entries: `146`

## Notes

- All generated artifacts were written under `out/` only.
- Source metadata under `dist/deviceData/AM64x/` was read-only.
- `dts_offset` currently mirrors `control_register_offset`.
- SysConfig metadata uses raw interface names such as `USART0` and `MCU_USART0` for some UART records.
- Flatten row count is driven by total `pinModeInfo` entries, which is larger than `peripheralPins` in this dataset.
