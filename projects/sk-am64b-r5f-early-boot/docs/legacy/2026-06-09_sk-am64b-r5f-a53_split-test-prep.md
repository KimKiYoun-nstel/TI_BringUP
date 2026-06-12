# 2026-06-09 SK-AM64B R5F/A53 Split Test Preparation

## 목적

이 문서는 SK-AM64B SBL early boot 문제를
`R5F 영향` 과 `A53 handoff 자체 문제` 로 분리하기 위해 준비한
split-test variant를 기록한다.

## 배경

현재까지 확인된 사실:

- UART uniflash 경로는 정상이다.
- OSPI absolute offset도 맞다.
- local fullchain / verbose OP-TEE chain에서도 boot는 `BL31` 까지 간다.
- 그러나 `U-Boot SPL` / `login:` 은 보이지 않는다.

추가 분석 결과:

- custom R5F heartbeat firmware는 `DebugP_log()` 를 직접 사용한다.
- draft SysConfig도 `debug_log` 모듈을 포함한다.
- Linux / OP-TEE / SBL 역시 같은 콘솔 UART 계열을 순차 공유할 가능성이 높다.

따라서 다음 두 분리 실험을 준비했다.

1. **R5F UART-silent variant**
2. **A53-only SBL variant**

## 1. R5F UART-silent variant

### 수정 내용

다음 source에서 `DebugP_log()` 호출을 제거했다.

- `projects/sk-am64b-r5f-early-boot/r5f/draft/ipc_rpmsg_echo.c`

제거 대상:

- heartbeat start log
- draft build timestamp log
- deferred RPMsg note log

추가로 SysConfig에 아래를 명시했다.

- `debug_log.enableUartLog = false;`

수정 파일:

- `projects/sk-am64b-r5f-early-boot/r5f/draft/ipc_rpmsg_echo.c`
- `projects/sk-am64b-r5f-early-boot/r5f/draft/example.syscfg`

### 재생성 결과

재빌드 및 appimage 재생성 후 산출물:

- raw ELF copy:
  - `out/sk-am64b-r5f-early-boot/am64-main-r5f0_0-fw`
- multicore image:
  - `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`

확인값:

- `am64-main-r5f0_0-fw`
  - size: `405736`
  - sha256: `0929be3f9dc6fe887ec6584b45247d2039fab9fb1246a7d8f9e68da3fae03a37`
- `r5f-early-heartbeat.mcelf.hs_fs`
  - size: `42082`
  - sha256: `fafbdea515082a48a3cc742d00828039b6f91f7a470a182634af5f06a1e02db1`

### flash cfg

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_r5f-silent_optee-verbose.cfg`

의미:

- offset `0x0`: current local SBL OSPI Linux image
- offset `0x80000`: UART-silent custom R5F image
- offset `0x300000`: verbose OP-TEE 기반 local `u-boot.img`
- offset `0x800000`: verbose OP-TEE 기반 local `linux.mcelf.hs_fs`

## 2. A53-only SBL variant

### 준비 방식

원본 example을 별도 경로로 복제했다.

- source root:
  - `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux_a53only/am64x-evm/r5fss0-0_nortos`

### 핵심 수정

복제한 `main.c` 에서 다음을 바꿨다.

1. `App_loadImages()` 호출 제거
2. `App_runCpus()` 호출 제거
3. `Bootloader_runSelfCpu()` 호출 제거
4. 시작 로그를 `Starting linux-only application` 으로 변경

즉 이 variant는
**multicore/R5F app load와 run을 의도적으로 건너뛰고 A53 Linux chain만 시도**한다.

수정 파일:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux_a53only/am64x-evm/r5fss0-0_nortos/main.c`

### 빌드 결과

산출물:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux_a53only/am64x-evm/r5fss0-0_nortos/ti-arm-clang/sbl_ospi_linux.release.hs_fs.tiimage`

확인값:

- size: `327013`

### flash cfg

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_a53-only_optee-verbose.cfg`

의미:

- offset `0x0`: A53-only SBL variant
- offset `0x80000`: silent R5F image를 그대로 유지하지만, SBL이 이를 load/run하지 않도록 함
- offset `0x300000`: verbose OP-TEE 기반 local `u-boot.img`
- offset `0x800000`: verbose OP-TEE 기반 local `linux.mcelf.hs_fs`

## 다음 검증 순서

권장 순서:

1. `r5f-silent_optee-verbose` cfg flash/boot
2. 증상 유지 시 `a53-only_optee-verbose` cfg flash/boot

## 해석 규칙

### case 1

`r5f-silent`에서 증상이 해소되면:

- R5F UART 또는 R5F early runtime side effect 가능성 높음

### case 2

`r5f-silent`은 실패하지만 `a53-only`는 성공하면:

- R5F runtime interaction이 문제

### case 3

`a53-only`도 동일하게 `BL31` 이후 멈추면:

- 핵심 문제는 A53 handoff chain 쪽

## 현재 상태

```text
split-test artifacts prepared: yes
flash/boot validation executed: partial
```

## 2026-06-09 실행 메모

### 1. `r5f-silent_optee-verbose` cfg

flash 결과:

- `uart_uniflash.py` SUCCESS

boot 관찰:

- OSPI boot 시작은 확인됨
- `U-Boot` / `login:` 까지의 가시적 진행은 즉시 확인되지 않음

해석:

- `R5F UART` 사용을 제거했다고 해서 즉시 문제가 닫히는 것은 아직 아님
- 다만 이 시점만으로 `R5F runtime interaction` 가능성을 완전히 배제할 수는 없음

### 2. `a53-only_optee-verbose` cfg

첫 시도:

- UART boot handshake 상태가 아니어서 XMODEM start 단계 실패
- 증상: `expected NAK ... got b'0'`, `got b'2'`

재시도:

- `uart_uniflash.py` SUCCESS

fresh OSPI boot 관찰:

- `DMSC Firmware Version ...` 확인
- 여전히 `Cores present` 에 `r5f0-0` 가 표시됨
- 여전히 `App_loadImages` profile point가 출력됨
- 기대했던 `Starting linux-only application` 문자열은 보이지 않음

해석:

- 현재 A53-only variant는 **실제 부팅 시점에서 multicore/R5F path를 끊는 데 실패했다**
- 즉 이번 단계의 결론은 “A53-only boot 성공/실패” 판정이 아니라,
  **A53-only SBL variant 준비 방식 자체가 불충분했다** 는 쪽에 가깝다

## 현재 열린 판단

```text
R5F silent flash: completed
A53-only flash: completed

R5F silent boot conclusion: inconclusive
A53-only boot conclusion: invalid test setup
```

현재 blocker:

```text
A53-only image는 flash되었으나,
fresh boot에서도 여전히 App_loadImages와 r5f0-0이 보여
현재 A53-only SBL variant가 R5F 경로를 실제로 끊지 못했다.
다음 단계는 'A53-only 판정'이 아니라
'A53-only SBL variant를 더 강하게 분기시키는 수정' 이다.
```
