# AM64x SysConfig DB Validation Report

## Row Count Sanity

- devicePins: `441`
- pinCommonInfos: `441`
- peripheralPins: `1079`
- generated rows: `1271`
- pinCommonInfos with at least one pinModeInfo: `295`
- pinCommonInfos with zero pinModeInfo: `146`
- peripheralPins referenced by generated rows: `1079`

## Template Check

- Domain split template rule: interface name containing `WKUP` or `MCU`, plus explicit `wkupPinsExc` signals, goes to MCU/WKUP output.
- Offset template rule: `getOffset()` returns `assignment.devicePin.controlRegisterOffset` as lowercase hex text.

### Relevant Template Lines

- `4: var groupedAssignmentsWKUP = {};`
- `9: 	// exception for pins with no MCU/WKUP domain prefix in the names, they should still go in the Wkup array`
- `10: 	var wkupPinsExc = {`
- `24: 	if( "NOT FOUND" !== assignment.devicePin.controlRegisterOffset ) {`
- `25: 		if ( _.includes(assignment.interfaceName, "WKUP") || _.includes(assignment.interfaceName, "MCU") || (assignment.devicePin.designSignalName.toUpperCase() in wkupPinsExc)) {`
- `26: 			groupedAssignmentsWKUP[ assignment.interfaceName ] = groupedAssignmentsWKUP[ assignment.interfaceName ] || {};`
- `27: 			groupedAssignmentsWKUP[ assignment.interfaceName ][ requirementName ] = groupedAssignmentsWKUP[ assignment.interfaceName ][ requirementName ] || [];`
- `28: 			groupedAssignmentsWKUP[ assignment.interfaceName ][ requirementName ].push( assignment );`
- `40: var getOffset = function( assignment ) {`
- `41: 	return ( assignment.devicePin.controlRegisterOffset ).toString( 16 ).toLowerCase();`
- `127: 			AM64X_IOPAD(`getOffset( assignment )`, `getPinConfig( assignment )`, `getPinMuxMode( assignment )`) `getPinComment( assignment )``
- `136: % if( !_( groupedAssignmentsWKUP ).isEmpty() ) {`
- `138: %	_( groupedAssignmentsWKUP ).each( function( iFace ) {`
- `143: 			AM64X_MCU_IOPAD(`getOffset( assignment )`, `getPinConfig( assignment )`, `getPinMuxMode( assignment )`) `getPinComment( assignment )``

## Required Signal Lookup

### UART0_RXD
- result: FOUND (1 hit(s))
- PASS: ball=D15, offset=0x0230, mode=0, interface=USART0, signal=UART0_RXD, macro=AM64X_IOPAD, ioDir=

### UART0_TXD
- result: FOUND (1 hit(s))
- PASS: ball=C16, offset=0x0234, mode=0, interface=USART0, signal=UART0_TXD, macro=AM64X_IOPAD, ioDir=

### I2C0_SCL
- result: FOUND (1 hit(s))
- PASS: ball=A18, offset=0x0260, mode=0, interface=I2C0, signal=I2C0_SCL, macro=AM64X_IOPAD, ioDir=

### I2C0_SDA
- result: FOUND (1 hit(s))
- PASS: ball=B18, offset=0x0264, mode=0, interface=I2C0, signal=I2C0_SDA, macro=AM64X_IOPAD, ioDir=

### I2C1_SCL
- result: FOUND (1 hit(s))
- PASS: ball=C18, offset=0x0268, mode=0, interface=I2C1, signal=I2C1_SCL, macro=AM64X_IOPAD, ioDir=

### I2C1_SDA
- result: FOUND (1 hit(s))
- PASS: ball=B19, offset=0x026c, mode=0, interface=I2C1, signal=I2C1_SDA, macro=AM64X_IOPAD, ioDir=

### MCU_UART0_RXD
- result: FOUND (1 hit(s))
- PASS: ball=A9, offset=0x0028, mode=0, interface=MCU_USART0, signal=MCU_UART0_RXD, macro=AM64X_MCU_IOPAD, ioDir=

### MCU_UART0_TXD
- result: FOUND (1 hit(s))
- PASS: ball=A8, offset=0x002c, mode=0, interface=MCU_USART0, signal=MCU_UART0_TXD, macro=AM64X_MCU_IOPAD, ioDir=

## SDK DTS Cross-check

- dts_path: `/home/nstel/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/board-support/ti-linux-kernel-6.18.13+git-ti/arch/arm64/boot/dts/ti/k3-am642-sk.dts`
- UART0_RXD: PASS at line 220: `AM64X_IOPAD(0x0230, PIN_INPUT, 0) /* (D15) UART0_RXD */`
- UART0_TXD: PASS at line 221: `AM64X_IOPAD(0x0234, PIN_OUTPUT, 0) /* (C16) UART0_TXD */`
- I2C0_SCL: PASS at line 245: `AM64X_IOPAD(0x0260, PIN_INPUT_PULLUP, 0) /* (A18) I2C0_SCL */`
- I2C0_SDA: PASS at line 246: `AM64X_IOPAD(0x0264, PIN_INPUT_PULLUP, 0) /* (B18) I2C0_SDA */`
