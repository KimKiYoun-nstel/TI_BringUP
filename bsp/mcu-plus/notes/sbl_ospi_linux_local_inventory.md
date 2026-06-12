# SBL OSPI Linux Local Inventory

## 목적

이 문서는 local MCU+ SDK workspace에서
`sbl_ospi_linux` 예제와 관련 boot 도구를 inventory 한 결과를 정리한다.

이 단계에서는 build/flash를 수행하지 않고,
repo-managed 준비 작업에 필요한 경로와 기본값만 정리한다.

## 기준 workspace

- `workspace/mcu_plus_sdk_am64x_12_00_00_27`

## 확인된 예제

### SBL OSPI Linux

경로:

- `examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos`

주요 파일:

- `example.syscfg`
- `default_sbl_ospi_linux.cfg`
- `default_sbl_ospi_linux_hs.cfg`
- `main.c`

### IPC RPMsg Linux echo

경로:

- `examples/drivers/ipc/ipc_rpmsg_echo_linux/am64x-evm/system_freertos`
- `examples/drivers/ipc/ipc_rpmsg_echo_linux/am64x-evm/r5fss0-0_freertos`

## 현재 확인된 기본 flash 배치

`default_sbl_ospi_linux.cfg` 기준 확인값:

| 항목 | offset | 비고 |
|---|---|---|
| SBL image | `0x0` | ROM boot expectation |
| RTOS/Baremetal multicore appimage | `0x80000` | example 주석과 cfg 일치 |
| Linux appimage | `0x800000` | cfg 기준 |
| `u-boot.img` | `0x300000` | cfg 기준 |

주의:

- planning note의 `0x300000 = Linux appimage` 가정은 현재 local SDK cfg와 다르다.
- 후속 문서는 local cfg 기준으로 다시 정리해야 한다.

## source 상 의미

`main.c` 주석은 다음 구조를 설명한다.

```text
한 offset에는 R5/M4 multicore appimage
다른 offset에는 Linux binaries appimage
```

즉 early boot 실험의 기본 topology는 local SDK source와 일치한다.

## 다음 단계에서 필요한 정리

- SK-AM64B용 wrapper config 문서 작성
- Linux appimage 입력 artifact 출처 정리 (`sbl_ospi_linux_appimage_inputs.md` 참고)
- dry-run install script에서 offset / size / sha256 출력
- actual flash 이전에 UART capture / recovery path / SD baseline 준비 확인
