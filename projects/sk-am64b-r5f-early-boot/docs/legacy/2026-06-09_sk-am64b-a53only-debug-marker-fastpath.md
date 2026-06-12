# 2026-06-09 SK-AM64B A53-only Debug Marker Fast Path

## 목적

이 문서는 corrected A53-only SBL에 추가 debug marker를 넣고,
UART uniflash 대신 Linux MTD fast path로 OSPI에 직접 기록한 결과를 남긴다.

## 적용한 변경

대상 source:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux_a53only/am64x-evm/r5fss0-0_nortos/main.c`

추가 marker:

- `A53_ONLY_MARKER_V1 before App_loadLinuxImages`
- `A53_ONLY_MARKER_V1 App_loadLinuxImages status=%d`
- `A53_ONLY_MARKER_V1 ATF_LOAD_ADDR=... OPTEE_LOAD_ADDR=... SPL_LOAD_ADDR=...`
- `A53_ONLY_MARKER_V1 before App_runLinuxCpu`
- `A53_ONLY_MARKER_V1 App_runLinuxCpu status=%d`

그리고 기존 A53-only branch의 visible runtime proof:

- `Starting linux-only application`

## artifact proof

rebuilt final artifact에서 다음이 확인되었다.

- `Starting linux-only application`

즉 source 수정이 stale artifact가 아니라 final SBL artifact에 실제 반영된 상태다.

## 사용한 fast path artifact set

local deploy root:

- `out/r5f-early-boot/image-sets/a53-only-debug-marker/`

구성:

- `mtd0-sbl-a53only-composite.bin`
- `0x300000_u-boot.img`
- `0x800000_linux.mcelf.hs_fs`

주의:

- 이번 A53-only fast path에서는 `ospi.tiboot3` partition의 `0x80000` 이후 영역을 `0xFF` padding으로 두었다.
- 즉 R5F appimage는 composite에 포함하지 않았다.

## Linux MTD fast path write 결과

board 상태:

- SD Linux boot 완료
- `/dev/mtd/by-name/*` 확인
- `flashcp` 존재 확인

실행 경로:

- `/dev/mtd/by-name/ospi.tiboot3`
- `/dev/mtd/by-name/ospi.u-boot`
- `/dev/mtd/by-name/ospi.rootfs`

write 결과:

- `flashcp -v mtd0-sbl-a53only-composite.bin /dev/mtd/by-name/ospi.tiboot3` 성공
- `flashcp -v 0x300000_u-boot.img /dev/mtd/by-name/ospi.u-boot` 성공
- `flashcp -v 0x800000_linux.mcelf.hs_fs /dev/mtd/by-name/ospi.rootfs` 성공

## readback/cmp 검증 결과

다음 세 항목 모두 board-side readback 후 `cmp` 성공:

- `MTD0_CMP_OK`
- `UBOOT_CMP_OK`
- `LINUXAPP_CMP_OK`

해석:

```text
이번 fast path write는 단순 write success가 아니라,
실제 board-side readback/cmp까지 일치가 확인된 상태다.
```

## 현재 상태

```text
A53-only debug marker variant built: yes
fast path Linux MTD write: yes
readback/cmp verification: yes
OSPI boot runtime proof: pending
```

## 2026-06-09 추가 단일변수 교정

### 목적

기존 A53-only debug marker variant runtime marker에서는 다음 값이 관측되었다.

```text
ATF_LOAD_ADDR=0x701a0000
OPTEE_LOAD_ADDR=0x9e800000
SPL_LOAD_ADDR=0x80080000
```

하지만 local U-Boot A53 defconfig와 TI 문서 기준 ATF load address는
`0x701c0000` 이다.

근거:

- `configs/am64x_evm_a53_defconfig`
  - `CONFIG_K3_ATF_LOAD_ADDR=0x701c0000`

따라서 다음 단일 변수 실험으로,
**A53-only chain에서 ATF load address만 `0x701c0000` 으로 교정한 linux appimage** 를 생성했다.

### 생성 결과

linux appimage build dir:

- `out/r5f-early-boot/linux-appimage-build-a53only-atf701c/`

image set dir:

- `out/r5f-early-boot/image-sets/a53only-atf701c/`

구성:

- `mtd0-sbl-a53only-composite.bin`
- `0x300000_u-boot.img`
- `0x800000_linux.mcelf.hs_fs`

sha256:

- `mtd0-sbl-a53only-composite.bin`
  - `075deeb2780ed532f50b4a35abcd2a7d2bc0fd4ba32cd85f7cdac9199079e048`
- `0x300000_u-boot.img`
  - `7d66b5d228ef52474f1ec035d7181fc8e2d80d9d658b635204e1eedf5d055b0f`
- `0x800000_linux.mcelf.hs_fs`
  - `4ff12f34959c7913ba845166c28197388c6e0938f9ff4c3470722e25916d6d7f`

### Linux MTD fast path 적용 결과

board 상태:

- SD Linux boot 정상
- `/dev/mtd/by-name/*` 확인 완료
- `flashcp` 존재 확인 완료

write:

- `ospi.tiboot3` 성공
- `ospi.u-boot` 성공
- `ospi.rootfs` 성공

readback/cmp:

- `MTD0_CMP_OK`
- `UBOOT_CMP_OK`
- `LINUXAPP_CMP_OK`

해석:

```text
ATF load address를 0x701c0000으로 교정한 A53-only chain이
Linux fast path로 OSPI에 기록되었고,
board-side readback/cmp까지 일치가 확인되었다.
```

## U-Boot TFTP + sf write 적용 결과

동일 A53-only `ATF_LOAD_ADDR=0x701c0000` image set을
U-Boot prompt에서 다시 absolute offset 기준으로 기록했다.

사용 파일:

- `tftp/am64x-sbl-ospi/sbl_ospi_linux.release.hs_fs.tiimage`
- `tftp/am64x-sbl-ospi/u-boot.img`
- `tftp/am64x-sbl-ospi/linux.mcelf.hs_fs`

host/server:

- TFTP server root: `TI_Bringup/tftp`
- server IP: `192.168.0.246`
- board U-Boot IP: `192.168.0.110`

U-Boot write/verify 결과:

- SBL @ `0x000000`
  - TFTP success
  - CRC before/after match
  - `sf erase/write/read` success
- `u-boot.img` @ `0x300000`
  - TFTP success
  - CRC before/after match
  - `sf erase/write/read` success
- `linux.mcelf.hs_fs` @ `0x800000`
  - TFTP success
  - CRC before/after match
  - `sf erase/write/read` success

해석:

```text
현재 A53-only + ATF 0x701c0000 image set은
Linux MTD fast path와 U-Boot sf write path 양쪽 모두에서
write/verify 성공이 확인된 상태다.
```
