# 2026-06-09 SK-AM64B Full Breadcrumb + BL32 Diagnostic V1 via U-Boot sf write

## 목적

이 문서는 BL31 breadcrumb와 BL32 early-init 완화가 함께 들어간
full diagnostic variant를 build하고, U-Boot `tftp + sf write` 경로로
OSPI에 재기록한 결과를 남긴다.

## 포함된 수정

### SBL

- A53-only branch 유지
- marker prefix: `A53_ATF701C_BL32DIAG_V2`
- `Starting linux-only application [A53_ATF701C_BL32DIAG_V2]`

### BL31

- `NOTICE("[BL31_DIAG_V1] before BL32 init")`
- `NOTICE("[BL31_DIAG_V1] after BL32 init rc=%d")`

### BL32 / OP-TEE

- `init_ti_sci()` bypass
- `secure_boot_information()` bypass
- `tee_otp_get_hw_unique_key()` dummy success
- markers:
  - `[BL32_DIAG_V1] init_ti_sci bypass`
  - `[BL32_DIAG_V1] secure_boot_information bypass`
  - `[BL32_DIAG_V1] HUK bypass`

## TFTP set

위치:

- `tftp/am64x-sbl-ospi-fullbc-v1/`

파일:

- `mtd0-sbl-a53only-composite.bin`
- `u-boot.img`
- `linux.mcelf.hs_fs`

## U-Boot write/verify 결과

보드 상태:

- U-Boot prompt
- `ping ${serverip}` 성공
- `sf probe 0:0` 성공

재기록 결과:

### `0x000000` SBL composite

- TFTP success
- CRC verified
- `sf erase/write/read` success

### `0x300000` `u-boot.img`

- TFTP success
- CRC verified
- `sf erase/write/read` success

### `0x800000` `linux.mcelf.hs_fs`

- TFTP success
- CRC verified
- `sf erase/write/read` success

## 현재 결론

```text
full breadcrumb + BL32 diagnostic V1 set is now correctly written to OSPI,
and U-Boot-side CRC verification passed for all three regions.
```

즉 다음 단계는 deployment 문제가 아니라,
실제 xSPI/OSPI boot에서 다음 marker의 유무를 보는 것이다.

- `A53_ATF701C_BL32DIAG_V2`
- `[BL31_DIAG_V1] before BL32 init`
- `[BL31_DIAG_V1] after BL32 init rc=...`
- `[BL32_DIAG_V1] ...`
