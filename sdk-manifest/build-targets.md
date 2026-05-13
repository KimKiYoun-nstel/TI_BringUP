# Build Targets

## U-Boot / Bootloader

Expected bootloader artifacts for AM64x flow:

```text
tiboot3.bin
tispl.bin
u-boot.img
```

These may depend on:

```text
U-Boot R5 SPL
U-Boot A53 SPL/U-Boot proper
TF-A
OP-TEE
TIFS/SYSFW/DM firmware
prebuilt-images
HS-FS packaging/signing flow
```

## Linux Kernel

Expected kernel artifacts:

```text
arch/arm64/boot/Image
arch/arm64/boot/dts/ti/*.dtb
kernel modules
```

## RootFS

RootFS is not stored as a full tree in this repo. Only overlays and notes are stored.
