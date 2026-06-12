# Phase2 UART Uniflash Runbook

## 목적

이 문서는 SK-AM64B R5F early-boot Phase2를
TI `uart_uniflash.py` 경로로 다시 시도할 때의 실행 절차를 정리한다.

이 절차의 목적은 다음이다.

- `uartd` 점유를 해제하고
- 보드를 UART boot mode로 전환한 뒤
- TI flashwriter가 absolute flash offset 기준으로 OSPI에 직접 쓰게 만든다.

## 기준 cfg

현재 기준으로는 다음 두 cfg를 구분해서 본다.

- 초기 guide-aligned 정리본:
  - `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2.cfg`
- 현재 권장 retry cfg:
  - `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl_sdk-spl.cfg`

이 cfg는 다음 offset을 source of truth로 사용한다.

```text
0x0       : SBL OSPI Linux image
0x80000   : R5F multicore appimage
0x300000  : u-boot.img
0x800000  : linux appimage
```

주의:

- UART uniflash 자체는 `am64x-sk` board variant의 flashwriter를 사용한다.
- 현재 retry 기준에서 offset `0x0` 이미지는 plain `sbl_ospi`가 아니라
  **Linux-capable `sbl_ospi_linux.release.hs_fs.tiimage`** 를 사용한다.
- 현재 실패 분석 기준에서는 flashwriter 교체보다
  **offset `0x800000` Linux appimage 내부 chain** 이 더 유력한 점검 대상이다.

## 현재 권장 retry 해석

2026-06-09 기준 현재 권장 retry는 다음 원칙을 따른다.

1. 이미 flash된 최신 artifact는 SD Linux readback hash로 host와 일치함이 확인되었다.
2. 따라서 다음 retry는 flash mechanism 변경이 아니라
   **Linux appimage만 바꾸는 단일 변수 실험** 이어야 한다.
3. 권장 cfg `sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl_sdk-spl.cfg` 는
   offset `0x800000`의 `linux.mcelf.hs_fs` 만 새 variant로 교체한다.

관련 판단 정리:

- `docs/research/2026-06-09_sk-am64b-r5f-early-boot_retry-strategy.md`

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
python3 uart_uniflash.py -p /dev/ttyUSB1 --cfg=/home/nstel/ti/TI_Bringup/bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl_sdk-spl.cfg
```

의미:

- 먼저 `sbl_uart_uniflash.release.hs_fs.tiimage`가 UART로 전송된다.
- 이후 cfg에 적힌 각 file이 absolute flash offset 기준으로 OSPI에 기록된다.

### 4. 완료 후 power cycle

### 5. 보드 boot mode switch를 OSPI/xSPI-SFDP로 변경

### 6. `uartd` 재시작

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

### 7. UART 모니터링

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
