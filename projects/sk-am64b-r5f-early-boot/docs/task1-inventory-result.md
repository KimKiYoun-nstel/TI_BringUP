# 2026-06-02 R5F Early Boot Task 1 Inventory Result

## 목적

이 문서는 `R5F early boot + A53 Linux + RPMsg attach` 상위 로드맵의
**작업 단위 1** 결과를 닫는 closeout 문서다.

이번 단계의 범위는 다음과 같았다.

```text
local repo와 installed SDK가 R5F early boot rehearsal을 수행할 수 있는 상태인지 확인하고,
수정 없이 조사 결과를 repo-managed 문서와 skeleton 구조로 남긴다.
```

중요:

- 이 문서는 inventory / planning closeout 문서다.
- build 실행, appimage 생성, flash, 보드 반영 결과를 주장하지 않는다.
- 작업 단위 2와 3의 성공 여부는 아직 검증하지 않는다.

## 1. 작업 단위 1 완료 조건 점검

### A. MCU+ SDK 경로와 version 확인

상태: 완료

근거:

- `sdk-manifest/mcu-plus-sdk.md`
- `sdk-manifest/workspaces.yml`
- `tools/env/mcu-plus-sdk-am64x-12.00.00.env`

확정 내용:

- MCU+ SDK version: `12.00.00`
- external install root: `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27`
- local workspace root: `workspace/mcu_plus_sdk_am64x_12_00_00_27`

### B. `sbl_ospi_linux` 예제 존재 확인

상태: 완료

근거:

- `sdk-manifest/mcu-plus-sdk.md`
- `bsp/mcu-plus/notes/sbl_ospi_linux_local_inventory.md`

확정 내용:

- local MCU+ workspace에 `examples/drivers/boot/sbl_ospi_linux` 존재
- local MCU+ workspace에 `examples/drivers/ipc/ipc_rpmsg_echo_linux` 존재
- `out2rprc`, `multicoreImageGen`, `linuxAppimageGen` 존재

### C. local Linux workspace의 `ti_k3_r5_remoteproc` IPC-only / attach 관련 코드 존재 여부 확인

상태: 완료

근거:

- `remoteproc-ipc-only-inventory.md`

확정 내용:

- `include/linux/remoteproc.h`에 `attach`, `detach`, `get_loaded_rsc_table`, `RPROC_DETACHED` 존재
- `drivers/remoteproc/ti_k3_r5_remoteproc.c`에 IPC-only mode detection 존재
- local kernel source는 detached/attach 성격의 경로를 이미 가진다

### D. SK-AM64B DTS의 `r5f` node, `reserved-memory`, `mailbox`, `firmware-name` 상태 확인

상태: 완료

근거:

- `sk-am64b-r5f-remoteproc-dt-inventory.md`

확정 내용:

- `k3-am642-sk.dts`는 `k3-am64-ti-ipc-firmware.dtsi`를 include 한다
- `main_r5fss0_core0` 기준 `memory-region`, `mboxes`, `status = "okay"` 구성이 source 상에 존재한다
- baseline `firmware-name`은 `am64-main-r5f0_0-fw` 이다

### E. 신규 repo 구조 확정

상태: 완료

근거:

- `bsp/mcu-plus/configs/`
- `bsp/mcu-plus/notes/`
- `bsp/mcu-plus/syscfg/`
- `firmware/r5f/`
- `logs/provenance/r5f-early-boot/`
- `tools/build/build-r5f-early-boot-app.sh`
- `tools/build/gen-linux-appimage-for-sbl.sh`

해석:

- 작업 단위 2에서 사용할 repo-managed 준비 자산의 기본 위치는 확정되었다.

## 2. 산출물 매핑

작업 계획서의 완료 산출물과 현재 상태를 다음처럼 정리한다.

| 계획 산출물 | 현재 상태 | 경로 |
|---|---|---|
| task1 result 문서 | 완료 | `task1-inventory-result.md` |
| MCU+ SDK inventory | 완료 | `sdk-manifest/mcu-plus-sdk.md` |
| remoteproc IPC-only inventory | 완료 | `remoteproc-ipc-only-inventory.md` |
| SK-AM64B DT inventory | 완료 | `sk-am64b-r5f-remoteproc-dt-inventory.md` |
| MCU+ patch series anchor | 기존 유지 | `bsp/mcu-plus/patches/series` |
| R5F firmware repo area | 완료 | `firmware/r5f/README.md` |

## 3. 이번 단계에서 추가로 확보된 준비 자산

작업 단위 1 범위를 넘지 않는 선에서,
작업 단위 2 진입을 위한 skeleton / draft 자산도 같이 확보했다.

### SBL / OSPI layout / dry-run

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_layout.md`
- `bsp/mcu-plus/notes/sbl_ospi_linux_local_inventory.md`

현재 확인된 local example 기준 offset:

```text
SBL image            : 0x0
R5F multicore image  : 0x80000
Linux appimage       : 0x800000
u-boot.img           : 0x300000
```

주의:

- 이 값은 local MCU+ SDK `default_sbl_ospi_linux.cfg` 기준 inventory 이다.
- 실제 flash 실행이나 보드 성공 결과를 의미하지 않는다.

### R5F heartbeat draft

- `heartbeat-source-selection.md`
- `heartbeat-minimal-feature-set.md`
- `heartbeat-shm-abi.md`
- `r5f/draft/README.md`
- `r5f/draft/ti-arm-clang/README.md`

해석:

- 작업 단위 2에 들어가면 canonical project를 무작정 복사하는 대신,
  어떤 file set과 기능 집합을 최소 baseline으로 삼을지 바로 이어서 결정할 수 있다.

## 4. Gate 판정

작업 단위 1 계획서의 gate 기준으로 현재 판정은 다음과 같다.

```text
Gate 1-A. local kernel에 attach/IPC-only 지원 흔적 있음
  -> 작업 단위 2, 3 모두 진행 가치 높음
```

판정 근거:

1. local kernel source에 `RPROC_DETACHED`, `attach`, `detach`, `get_loaded_rsc_table` 경로가 존재한다.
2. `ti_k3_r5_remoteproc.c`에 IPC-only mode detection이 존재한다.
3. SK-AM64B baseline DTS는 R5F remoteproc + IPC firmware include 경로를 이미 갖는다.
4. 기존 repo bring-up history에는 remoteproc / RPMsg baseline 정상 동작 기록이 이미 있다.

## 5. 작업 단위 2 진입 조건

작업 단위 2로 넘어갈 수는 있지만,
아직 다음은 완료된 것이 아니다.

```text
- R5F heartbeat app build 완료
- multicore appimage 생성 완료
- Linux appimage 생성 완료
- UART log로 SBL -> R5F -> Linux boot 순서 확인
```

따라서 작업 단위 2의 첫 단계는 다음처럼 잡는 것이 적절하다.

1. heartbeat 최소 source set 확정
2. Linux appimage 입력 artifact 출처 확정
3. dry-run 기준 artifact path / sha256 / offset 정리
4. 이후에만 build / image generation / flash 검토

## 6. 이번 단계에서 하지 않은 것

- actual build 실행
- appimage 생성
- OSPI overwrite
- UART boot 실험
- remoteproc stop/start 실험
- rootfs service 추가 검증

## 7. 결론

작업 단위 1의 inventory / planning 목표는 현재 repo 기준으로 충족되었다.

현재 상태를 한 줄로 요약하면 다음과 같다.

```text
repo와 local SDK/kernel은 R5F early boot rehearsal을 진행할 준비가 되어 있고,
작업 단위 2로 넘어가기 위한 문서/구조/skeleton 자산이 정리되었다.
```
