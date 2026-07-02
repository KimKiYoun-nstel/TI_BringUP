# AM64x TSN C Case C5 Path B Bootstrap Parity A/B 재검증

## 목적

`gptp_icssg_switch` donor bootstrap 순서를 Path B에 일부 복원한 뒤,

- A. remoteproc load
- B. firmware boot trace

만 다시 검증한다.

이번 재검증에서는 C/D/E/F 단계는 진행하지 않는다.

## 이번 source 수정 요약

대상 project:

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
```

수정 파일:

- `main.c`
- `ipc_rpmsg_echo.c`

### 반영 내용

1. `main task priority`를 donor `gptp_icssg_switch`와 같은 `2`로 조정
2. `main stack`은 기존 Path B의 `16 KiB` 유지
3. `freertos_main()` 안에 donor 순서 기반 bootstrap 추가

```text
Drivers_open()
Board_driversOpen()
EnetApp_mainTask()
Board_driversClose()
Drivers_close()
```

4. remoteproc trace 최소 로그 추가

- `PathB gptp switch entry`
- `Drivers_open start/done`
- `Board_driversOpen start/done`
- `EnetApp_mainTask entry`
- `EnetApp_mainTask returned`

## build 결과

다음 raw ELF는 다시 링크 성공했다.

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
  Release/ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang.out
```

post-build `mcelf`는 기존과 동일한 host-side Python tool 문제로 실패했다.

```text
TypeError: ELFFile.iter_segments() got an unexpected keyword argument 'type'
```

이번 검증에는 raw ELF `.out`만 사용했다.

## 보드 적용 방식

### test firmware 배치

host에서 다음 파일로 복사했다.

```text
/lib/firmware/gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

SHA256:

```text
9ad5932d496217282ea126f123d3d4999dc4193570ca64709be573b183c56e1a
```

### boot-time temporary override

U-Boot에서 다음을 수행했다.

1. base kernel/DT/overlay load
2. C2 ownership disable 재적용
3. `firmware-name`만 test ELF로 override
4. `run run_kern`

적용 항목:

```text
/bus@f4000/ethernet@8000000/ethernet-ports/port@2 -> status = "disabled"
/mdio-mux-1 -> status = "disabled"
/icssg1-eth -> status = "disabled"
/bus@f4000/r5fss@78000000/r5f@78000000
  firmware-name = "gptp_icssg_linux_remoteproc_r5f0_0_test.out"
```

`saveenv`는 하지 않았다.

## A 단계 결과

### 판정

**성공**

### 근거

boot log에서:

```text
remoteproc remoteproc0: Booting fw image gptp_icssg_linux_remoteproc_r5f0_0_test.out, size 4695388
remoteproc remoteproc0: remote processor 78000000.r5f is now up
```

Linux shell에서:

```text
/sys/class/remoteproc/remoteproc0
  name     = 78000000.r5f
  state    = running
  firmware = gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

즉 bootstrap parity 수정 후에도 **remoteproc loadability는 유지**되었다.

## B 단계 결과

### 판정

**실패**

### trace 결과

`/sys/kernel/debug/remoteproc/remoteproc0/trace0`:

```text
[RPROC_TRACE] stage=boot state=enter code=0 main start
```

이번에 추가한 아래 trace는 여전히 보이지 않았다.

- `system and board init complete`
- `main task created`
- `PathB gptp switch entry`
- `Drivers_open start`
- `Drivers_open done`
- `Board_driversOpen start`
- `Board_driversOpen done`
- `EnetApp_mainTask entry`

### 의미

이번 donor bootstrap parity 수정에도 불구하고,
firmware는 여전히 **`main start` 이후 더 진행하지 못한다**.

즉 실패 지점은 최소한 다음 이전으로 좁혀진다.

```text
System_init() 완료 이전
또는
Board_init() 완료 이전
또는
main task 생성 이전
```

따라서 현재 분류 기준으로는:

```text
Drivers_open 전에서 멈춤
=> scaffold entry/runtime 문제 또는 System_init/Board_init 초기화 문제
```

로 해석하는 것이 맞다.

## 이번 재검증으로 얻은 결론

### 확정된 것

1. donor bootstrap 일부 복원 후에도 A 단계는 계속 성공한다.
2. B 단계는 계속 실패한다.
3. failure point는 `Drivers_open()` 이전이다.
4. 따라서 현재 1차 blocker는 `EnetApp_mainTask()` 내부가 아니다.

### 아직 미확정인 것

1. `System_init()` 내부 어느 단계에서 멈추는지
2. `Board_init()` 진입까지는 가는지
3. remoteproc scaffold + generated driver init 조합 중 어느 쪽이 실제 blocker인지

## 원복

시험 후 정상 reboot로 기본 firmware boot path 복귀를 확인했다.

확인 결과:

```text
78000000.r5f firmware = am64-main-r5f0_0-fw
```

즉 temporary override는 부팅 한 번에만 적용되었고, 기본 boot path는 복귀했다.

test ELF 파일은 다음 경로에 그대로 남겨 두었다.

```text
/lib/firmware/gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

이유:

- 다음 C5 반복 검증에서 같은 artifact를 다시 사용할 가능성이 높기 때문

## 다음 우선순위

이번 결과로 다음 우선순위가 더 명확해졌다.

1. `System_init()` 전/후 trace 분리
2. `Board_init()` 전/후 trace 분리
3. 필요 시 `System_init()` 내부 generated init 경로 점검
4. B 단계 통과 후에만 `.icss_mem` / `.enet_dma_mem` placement 복원 검토

즉 다음 단계는 아직 C 단계가 아니다.

```text
B 단계에서 어디서 멈추는지 더 정확히 좁히는 것
```

이 우선이다.
