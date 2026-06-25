# Phase2 UART Uniflash Runbook

## 목적

이 문서는 현재 canonical `local-fullchain` set을
TI `uart_uniflash.py` 경로로 OSPI에 기록할 때의 실행 절차를 정리한다.

이 절차의 목적은 다음이다.

- `uartd` 점유를 해제하고
- 보드를 UART boot mode로 전환한 뒤
- TI flashwriter가 absolute flash offset 기준으로 OSPI에 직접 쓰게 만든다.

## 기준 cfg

현재 active cfg는 다음 하나만 사용한다.

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg`

이 cfg는 다음 offset을 source of truth로 사용한다.

```text
0x0       : SBL OSPI Linux image
0x80000   : R5F multicore appimage
0x300000  : u-boot.img
0x800000  : linux appimage
```

주의:

- UART uniflash 자체는 `am64x-sk` board variant의 flashwriter를 사용한다.
- offset `0x0` 이미지는 plain `sbl_ospi`가 아니라
  **Linux-capable `sbl_ospi_linux.release.hs_fs.tiimage`** 를 사용한다.
- write 완료 후 reboot 전에 **사용자가 boot mode switch를 OSPI로 전환했는지 확인하는 gate** 를 반드시 둔다.

## 현재 실행 기준

현재 build lineage는 다음 문서를 따른다.

- `docs/sbl-ospi-linux-local-fullchain-profile.md`

## 사전 조건

1. artifact set 존재
   - `sbl_ospi_linux.release.hs_fs.tiimage`
   - `r5f-early-heartbeat.mcelf.hs_fs`
   - `u-boot.img`
   - `linux.mcelf.hs_fs`
2. host에서 `/dev/ttyUSB1` 접근 가능
3. `uartd`가 현재 UART port를 점유 중이면 정지할 것
4. 보드를 **UART boot mode** 로 전환할 것

## 절차

### 1. `uartd` 정지

```bash
./tools/uart/uartctl.py stop
```

이유:

- `uart_uniflash.py` 가 `/dev/ttyUSB1`를 직접 열어야 한다.

### 2. 보드 boot mode switch를 UART boot로 변경

주의:

- 이 단계는 사용자 조작이 필요하다.
- boot mode switch는 현재 repo의 `uartd`/MCP가 대신 바꿀 수 없다.

### 3. host에서 TI flashwriter/uniflash 실행

```bash
cd /home/nstel/ti/TI_Bringup/workspace/mcu_plus_sdk_am64x_12_00_00_27/tools/boot
python3 uart_uniflash.py -p /dev/ttyUSB1 --cfg=/home/nstel/ti/TI_Bringup/bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg
```

의미:

- 먼저 `sbl_uart_uniflash.release.hs_fs.tiimage`가 UART로 전송된다.
- 이후 cfg에 적힌 각 file이 absolute flash offset 기준으로 OSPI에 기록된다.

### 4. 완료 후 사용자 gate

- 여기서 Agent는 멈추고 사용자에게 boot mode switch 확인을 요청한다.
- 사용자가 보드를 **OSPI/xSPI-SFDP boot mode** 로 바꿨다고 확인한 뒤에만 다음 단계로 간다.

### 5. `uartd` 재시작

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

### 6. UART 모니터링

다음 둘 중 하나로 확인한다.

```bash
./tools/uart/uartctl.py tail
```

또는

```bash
tail -f logs/runtime_log
```

## 기대 확인 포인트

1. SBL banner
2. `Starting linux and RTOS/Baremetal applications`
3. BL31 이후 추가 진행
4. U-Boot SPL / U-Boot / Linux 진입 여부

## 실패 시

- `uartd`를 다시 start 하지 않은 상태로 두지 말 것
- boot mode switch를 SD baseline으로 복귀할 것
- 필요 시 기존 SD Linux 경로로 복구 후 다시 분석한다
