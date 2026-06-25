# SK-AM64B R5F Early Boot Gates

## Gate 1

상태: Passed

판정:

```text
Gate 1-A. local kernel에 attach/IPC-only 지원 흔적 있음
```

근거 문서:

- `docs/task1-inventory-result.md`
- `docs/remoteproc-ipc-only-inventory.md`
- `docs/sk-am64b-r5f-remoteproc-dt-inventory.md`

## Gate 2

상태: Passed

목표:

- `LPDDR4 DDR reginit` 기반 clean workspace base 정리
- 원본 `sbl_ospi_linux` 기본 dual-boot 경로 재확인
- OSPI write 후 Linux boot 재확인

working checklist:

- `docs/phase2-execution-checklist.md`

이미 확인된 것:

- `BL31/BL32/BL33 DDR destination` 적재 성공
- `dual-boot` 기준 `U-Boot SPL -> U-Boot -> Linux` 진입 성공
- 원인 핵심이 MCU+ SDK 기본 `DDR4 board_ddrReginit.h`였음을 확인
- clean replay 자산으로 LPDDR4 standalone asset + syscfg delta 정리 완료
- `local-fullchain` linux appimage provenance와 `ATF_LOAD_ADDR=0x701c0000` 교정 기준을 canonical profile로 고정 완료
- board-side readback hash와 host artifact hash가 다시 일치하는 OSPI set 확인 완료

후속으로 남겨 둔 것:

- custom early-boot R5F firmware behavior 정합성
- custom A53 checker / own RPMsg app 경로 정합성
- 위 항목들은 project 내부 follow-up으로만 유지

boundary note:

- `docs/phase2-completion-boundary.md`

local image generation provenance:

- `/home/nstel/ti/TI_Bringup/logs/provenance/r5f-early-boot/2026-06-04_phase2_local-image-generation.md`
- `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-11_SK-AM64B_sbl-ospi-linux-lp4-first-success.md`
- `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-24_SK-AM64B_sbl-ospi-linux-local-fullchain-success.md`

## Gate 3

상태: In progress

예상 범위:

- M1: custom A53 checker app으로 SHM heartbeat 확인
- M2: own RPMsg endpoint bring-up
- M3: own app protocol 정합성 확인

현재 판정:

- boot-chain scope는 닫혔다.
- Gate 3의 첫 체크포인트는 `R5F firmware started before Linux and remains alive`를
  custom Linux checker app이 SHM으로 확인하는 것이다.
- M1 custom Linux checker app 경로는 확보되었고, 현재 source 기준 재검증에서도 PASS를 확인했다.
- `0xA5800000` SHM checkpoint는 explicit non-cached MPU region 반영 후 정상화되었다.

현재 남은 것:

- M2: own RPMsg endpoint bring-up
- M3: own app protocol 정합성 확인
