# 2026-06-09 SK-AM64B BL32 Diagnostic Variant via U-Boot sf write

## 목적

이 문서는 BL32 suspicious early init 경로를 완화한 diagnostic variant를
U-Boot `tftp + sf write` 경로로 OSPI에 기록하고 검증한 결과를 기록한다.

## 적용한 BL32 diagnostic 변경

진단용 OP-TEE workspace:

- `workspace/optee-os-4.9.0+git-bl32diag`

완화한 경로:

- `init_ti_sci()` -> bypass success
- `secure_boot_information()` -> bypass success
- `tee_otp_get_hw_unique_key()` -> dummy success

삽입 marker:

- `[BL32_DIAG_V1] init_ti_sci bypass`
- `[BL32_DIAG_V1] secure_boot_information bypass`
- `[BL32_DIAG_V1] HUK bypass`

## 빌드 결과

### OP-TEE

- output: `out/optee-bl32diag/core/tee-pager_v2.bin`
- size: `754432`

### A53 chain

- `out/u-boot-a53-bl32diag/a53/u-boot.img`
- `out/u-boot-a53-bl32diag/a53/spl/u-boot-spl.bin`

### linux appimage

- `out/r5f-early-boot/linux-appimage-build-bl32diag/linux.mcelf.hs_fs`
- `out/r5f-early-boot/linux-appimage-build-bl32diag/u-boot.img`

## TFTP root 배치

위치:

- `tftp/am64x-sbl-ospi-bl32diag/`

파일:

- `mtd0-sbl-a53only-composite.bin`
- `u-boot.img`
- `linux.mcelf.hs_fs`

## U-Boot write/verify 결과

보드 상태:

- U-Boot prompt
- `sf probe 0:0` 성공
- TFTP host ping 성공

기록 결과:

### `0x000000` SBL composite

- TFTP success
- CRC before/after match
- `sf erase/write/read` success

### `0x300000` `u-boot.img`

- TFTP success
- CRC before/after match
- `sf erase/write/read` success

### `0x800000` `linux.mcelf.hs_fs`

- TFTP success
- CRC before/after match
- `sf erase/write/read` success

## 현재 결론

```text
BL32 diagnostic variant image set is now correctly written to OSPI,
and U-Boot-side readback CRC verification passed for all three written regions.
```

즉 다음 단계는 배포 경로 검증이 아니라,
실제 xSPI/OSPI boot에서 `BL32_DIAG_V1` marker가 보이는지 여부를 통해
BL32 early init bypass가 증상에 영향을 주는지 확인하는 것이다.

## 추가 재기록: V2 proof chain

이후 proof chain을 더 명확히 하기 위해,
SBL marker를 `A53_ATF701C_BL32DIAG_V2` 로 변경한 세트를 다시 구성했고,
U-Boot `tftp + sf write` 경로로 다시 기록했다.

재기록 대상:

- `0x000000` : `mtd0-sbl-a53only-composite.bin`
- `0x300000` : `u-boot.img`
- `0x800000` : `linux.mcelf.hs_fs`

U-Boot-side 검증:

- `0x000000` CRC verified
- `0x300000` CRC verified
- `0x800000` CRC verified

즉 현재 OSPI에는
**A53-only + ATF701c + BL32 diagnostic + V2 SBL marker** 세트가
U-Boot absolute offset write 기준으로 다시 기록된 상태다.
