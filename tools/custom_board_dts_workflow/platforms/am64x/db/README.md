# DB Folder

Place generated AM64x SysConfig DB artifacts here. This template intentionally does not include generated DB data.

Required:

```text
platforms/am64x/db/am64x_sysconfig_pinmux_db.csv
platforms/am64x/db/am64x_sysconfig_pinmux_db.json
```

Recommended optional references:

```text
platforms/am64x/db/am64x_package_pins.csv
platforms/am64x/db/am64x_pin_common_infos.csv
platforms/am64x/db/extraction_report.md
platforms/am64x/db/validation_report.md
platforms/am64x/db/am64x_linux_dt_template.txt
```

## Required CSV Columns

`am64x_sysconfig_pinmux_db.csv` must contain at least:

```csv
soc,package,ball,device_pin_id,device_pin_name,control_register_offset,interface_name,signal_name,peripheral_pin_id,peripheral_pin_name,mux_mode,io_dir,power_domain_id,domain,linux_macro,dts_offset,source
```

Known validated examples should include:

```text
UART0_RXD      D15  0x0230  mode 0  AM64X_IOPAD
UART0_TXD      C16  0x0234  mode 0  AM64X_IOPAD
I2C0_SCL       A18  0x0260  mode 0  AM64X_IOPAD
I2C0_SDA       B18  0x0264  mode 0  AM64X_IOPAD
I2C1_SCL       C18  0x0268  mode 0  AM64X_IOPAD
I2C1_SDA       B19  0x026c  mode 0  AM64X_IOPAD
MCU_UART0_RXD  A9   0x0028  mode 0  AM64X_MCU_IOPAD
MCU_UART0_TXD  A8   0x002c  mode 0  AM64X_MCU_IOPAD
```

## Meaning

This DB is the stable AM64x/ALV pinmux source. It is generated from SysConfig metadata and should not change often. The custom board `.NET` changes per board and is joined against this DB.
