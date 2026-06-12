# MCU+ SDK Inventory

## 목적

이 문서는 R5F early boot rehearsal 관점에서
현재 repo가 참조하는 AM64x MCU+ SDK local workspace 상태를 정리한다.

이 문서의 목적은 다음과 같다.

- MCU+ SDK install root와 workspace root를 분리해서 기록
- SBL OSPI Linux / RPMsg Linux 예제 존재 여부 확인
- boot image 생성 도구 경로 확인
- 외부 SDK 원본 직접 수정 금지 원칙을 다시 명시

## 현재 확인된 경로

| 항목 | 값 | 비고 |
|---|---|---|
| MCU+ SDK version | `12.00.00` | `tools/env/mcu-plus-sdk-am64x-12.00.00.env` 기준 |
| install root | `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27` | external original, reference-only |
| workspace root | `workspace/mcu_plus_sdk_am64x_12_00_00_27` | editable local workspace |
| env file | `tools/env/mcu-plus-sdk-am64x-12.00.00.env` | local build helper 기준 |
| CCS project dir | `workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects` | headless CCS build/export 용도 |

## 예제 존재 확인

현재 local workspace에서 다음 예제가 확인되었다.

| 항목 | 경로 |
|---|---|
| SBL OSPI Linux | `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux` |
| IPC RPMsg Linux echo | `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/ipc/ipc_rpmsg_echo_linux` |

세부 variant:

- `sbl_ospi_linux/am64x-evm/r5fss0-0_nortos`
- `ipc_rpmsg_echo_linux/am64x-evm/system_freertos`
- `ipc_rpmsg_echo_linux/am64x-evm/r5fss0-0_freertos`

## Boot 도구 존재 확인

현재 local workspace에서 다음 도구가 확인되었다.

| 도구 | 경로 | 용도 |
|---|---|---|
| `out2rprc` | `tools/boot/out2rprc` | `.out` -> `RPRC` 변환 |
| `multicoreImageGen` | `tools/boot/multicoreImageGen` | multicore appimage 생성 |
| `linuxAppimageGen` | `tools/boot/linuxAppimageGen` | Linux appimage 생성 |
| `uart_uniflash.py` | `tools/boot/uart_uniflash.py` | UART 기반 flash helper |
| `sbl_prebuilt` | `tools/boot/sbl_prebuilt` | flash writer / prebuilt SBL 자산 |

## 현재 판단

확정된 사실:

- repo는 이미 MCU+ SDK local workspace 경로를 가지고 있다.
- R5F early boot rehearsal에 필요한 최소 예제군과 boot 도구가 local workspace에 존재한다.
- `tools/env/mcu-plus-sdk-am64x-12.00.00.env`는 install root와 workspace root를 분리해 관리한다.

추정:

- 작업 단위 2의 build helper는 완전 신규가 아니라 현재 env/script 관례를 재사용하는 방향이 적합하다.

확인 필요:

- `sbl_ospi_linux`를 `am64x-evm` 기준으로 재사용할지, SK-AM64B 전용 wrapper/config만 둘지
- Linux appimage 입력에 local U-Boot/SPL build 산출물을 사용할지, TI prebuilt를 임시로 사용할지

## 운영 원칙

- `~/ti/am64x/mcu_plus_sdk_*` 외부 SDK original은 reference-only 이다.
- 재현 가능한 변경이 필요하면 `workspace/mcu_plus_sdk_am64x_12_00_00_27`에서 수행한다.
- 장기 보관 가치가 생긴 변경은 `bsp/mcu-plus/patches/`와 `logs/provenance/`로 승격한다.
- `.appimage`, `.tiimage`, `.mcelf`, `.out` 같은 build artifact는 repo에 commit하지 않는다.
