# Phase2 Execution Checklist

## 목적

이 문서는 `task-unit-2` 실행 전 준비 자산을
실제 작업 순서 기준으로 한 장에 묶는 checklist 이다.

현재 단계는 `LPDDR4 clean base`와 `local-fullchain` provenance correction 이후,
OSPI Linux boot를 다시 확인한 상태다.

## 범위

Phase2의 현재 범위는 다음과 같다.

```text
LPDDR4 DDR reginit 적용
canonical local-fullchain build profile 고정
원본 sbl_ospi_linux dual boot 재확인
R5F early-boot heartbeat / RPMsg 다음 단계 준비
```

이 문서는 다음을 아직 하지 않는다.

- own RPMsg endpoint completion 판정
- custom app protocol completion 판정

## 1. 현재 Phase2 상태 확인

시작 전 다음 상태를 기준으로 본다.

- task-unit-1 closeout 완료
- Gate 1-A passed
- project working surface: `projects/sk-am64b-r5f-early-boot/`
- heartbeat first draft source 존재
- linux appimage input inventory / SPL mapping / staging policy 존재
- LPDDR4 reginit 기반 success log 존재
- current local-fullchain success log 존재

참조:

- `docs/plan.md`
- `docs/gates.md`
- `docs/task1-inventory-result.md`
- `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-11_SK-AM64B_sbl-ospi-linux-lp4-first-success.md`
- `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-24_SK-AM64B_sbl-ospi-linux-local-fullchain-success.md`

## 2. authoritative input 문서 확인

Phase2 작업 전에 다음 문서를 한 번씩 확인한다.

### project-side

- `docs/heartbeat-source-selection.md`
- `docs/heartbeat-minimal-feature-set.md`
- `docs/heartbeat-shm-abi.md`
- `r5f/draft/README.md`
- `r5f/draft/early_heartbeat_status.h`

### repo-wide reusable assets

- `/home/nstel/ti/TI_Bringup/sdk-manifest/mcu-plus-sdk.md`
- `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_local_inventory.md`
- `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_appimage_inputs.md`
- `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_spl_staging_mapping.md`
- `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_appimage_staging_policy.md`

## 3. heartbeat draft 정합성 체크

다음 항목이 현재 draft 기준과 맞는지 본다.

### source set

- `r5f/draft/main.c`
- `r5f/draft/example.syscfg`
- `r5f/draft/ipc_rpmsg_echo.c`
- `r5f/draft/early_heartbeat_status.h`

### 체크 포인트

- `main.c`는 canonical entry shell과 크게 다르지 않은가
- `example.syscfg`는 GPIO-free baseline 방향을 유지하는가
- `ipc_rpmsg_echo.c`는 Linux-ready wait / RPMsg endpoint 생성에 의존하지 않는가
- SHM field 집합이 `heartbeat-shm-abi.md` 와 일치하는가

## 4. Linux appimage 입력 후보 확인

실행 전 다음 입력 후보를 확인한다.

### helper

```bash
./tools/build/gen-linux-appimage-for-sbl.sh --print --profile local-fullchain
```

### 기대 확인 항목

- `bl31.bin` 후보
- `bl32.bin` 후보
- `u-boot-spl.bin-am64xx-evm` 기대 이름
- local `tispl.bin` source canonical name
- `u-boot.img` 후보
- override 변수 목록

## 5. staging 정책 확인

실행 전 다음 helper와 정책 문서를 확인한다.

### helper

```bash
./tools/build/dry-run-linux-appimage-staging-for-sbl.sh --dry-run
```

### 기대 확인 항목

- staging dir 경로
- source -> staging file명 매핑
- SPL alias policy (`tispl.bin` -> `u-boot-spl.bin-am64xx-evm`)
- override 변수 값
- validation result

## 6. 현재 성공 자산 확인

현재 실행 기준 자산은 다음처럼 정리한다.

- SBL / R5F / U-Boot / linux appimage는 `local-fullchain` profile 기준으로 rebuild 한다.
- flash offset source of truth는 `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg` 이다.

기준 log:

- `/home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-06-24_SK-AM64B_sbl-ospi-linux-local-fullchain-success.md`

기준 note:

- `/home/nstel/ti/TI_Bringup/bsp/mcu-plus/notes/sbl_ospi_linux_lpddr4_alignment.md`

## 6-1. UART uniflash 실행 경로 확인

참조 문서:

- `docs/phase2-uart-uniflash-runbook.md`

핵심 확인 항목:

- `uartd` stop 필요 여부
- 보드 UART boot mode 필요 여부
- `uart_uniflash.py -p /dev/ttyUSB1 --cfg=...` 실행 경로
- 완료 후 OSPI boot 복귀 절차

## 7. buildable draft 승격 전 gate

buildable draft로 넘어가기 전에 다음 질문에 모두 답할 수 있어야 한다.

1. LPDDR4 reginit 원인이 문서상으로 고정되었는가
2. 성공 log와 provenance가 저장되었는가
3. 원본 `sbl_ospi_linux` 복구에 필요한 최소 delta만 남겼는가
4. 다음 단계가 `A53-only 제거 + R5F/A53 동시 부팅`으로 정리되었는가

모두 yes 이면 다음 단계로 진행한다.

## 8. 다음 실제 작업 순서

현재 checklist 기준으로 다음 실질 작업은 다음 순서가 적절하다.

```text
1. local-fullchain build profile 유지
2. M1 SHM heartbeat 재확인
3. M2 own RPMsg endpoint bring-up
4. M3 own app protocol 정합성 확인
```

board-side 최종 경계는 `docs/phase2-completion-boundary.md`를 따른다.

## 9. 현재 단계에서 하지 않는 것

- 과거 failed trial을 active 실행 기준으로 다시 가져오지 않음
- canonical profile 밖의 cfg/doc를 active 실행 기준으로 사용하지 않음

## 10. guide-aligned write 원칙

현재 project는 TI `default_sbl_ospi_linux.cfg` 가 정의하는
absolute flash offset model을 source of truth로 사용한다.

```text
0x0       : bootloader image
0x80000   : multicore appimage
0x300000  : u-boot.img
0x800000  : linux appimage
```

다음 해석은 금지한다.

- offset model을 partition-relative write로 임의 치환
- `mtd0/mtd2/mtd5` 같은 이름만으로 guide semantics와 동일하다고 간주
