# AM64x TSN C Case C5 Path B System_init 세분화 trace 재검증

## 목적

한 번의 부팅으로 `main start` 이후 정확히 어느 init step에서 멈추는지 확인하기 위해,

- `main()`
- `System_init()`
- `Board_init()`

에 세분화된 trace를 추가하고 A/B만 다시 검증한다.

## 추가한 trace 범위

### main.c

- `System_init call start`
- `System_init call done`
- `Board_init call start`
- `Board_init call done`
- `main task create start ...`

### Release/syscfg/ti_drivers_config.c

`System_init()` 내부에 아래 step trace를 추가했다.

- `System_init enter`
- `System_init Dpl_init start/done`
- `System_init Sciclient_init start/done`
- `System_init CycleCounterP_init start/done`
- `System_init PowerClock_init start/done`
- `System_init Pinmux_init start/done`
- `System_init IpcNotify_Params_init start/done`
- `System_init IpcNotify_init start/done`
- `System_init RPMessage_Params_init start/done`
- `System_init RPMessage_init start/done`
- `System_init I2C_init start/done`
- `System_init GPIO_init start/done`
- `System_init PRUICSS_init start/done`
- `System_init Udma_init inst=%u start/done`
- `System_init exit`

오류 반환이 가능한 항목에는 `failed` trace도 함께 넣었다.

### Release/syscfg/ti_board_config.c

`Board_init()`는 비어 있으므로 다음만 추가했다.

- `Board_init enter`
- `Board_init exit`

## build 결과

raw ELF `.out`는 다시 링크 성공했다.

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
  Release/ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang.out
```

이번 ELF의 보드 배치 후 SHA256:

```text
631032b1a90edb20d336762397dd26c2a5325a0526d6e830cd484321df860a2d
```

`mcelf` post-build 실패는 기존과 동일한 host-side tool 문제이며 무시했다.

## 보드 검증 방식

이전과 같은 temporary boot-time override 방식을 사용했다.

```text
/bus@f4000/ethernet@8000000/ethernet-ports/port@2 -> disabled
/mdio-mux-1 -> disabled
/icssg1-eth -> disabled
/bus@f4000/r5fss@78000000/r5f@78000000
  firmware-name = gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

## A 단계 결과

### 판정

**성공**

### 근거

```text
remoteproc remoteproc0: Booting fw image gptp_icssg_linux_remoteproc_r5f0_0_test.out, size 4702892
remoteproc remoteproc0: remote processor 78000000.r5f is now up
```

Linux 확인:

```text
remoteproc0
  name     = 78000000.r5f
  state    = running
  firmware = gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

## B 단계 결과

### 판정

**실패하지만 stop point는 특정됨**

### trace 결과

`/sys/kernel/debug/remoteproc/remoteproc0/trace0`:

```text
[RPROC_TRACE] stage=boot state=enter code=0 main start
[RPROC_TRACE] stage=boot state=ok code=0 System_init call start
[RPROC_TRACE] stage=boot state=ok code=0 System_init enter
[RPROC_TRACE] stage=boot state=ok code=0 System_init Dpl_init start
[RPROC_TRACE] stage=boot state=ok code=0 System_init Dpl_init done
[RPROC_TRACE] stage=boot state=ok code=0 System_init Sciclient_init start
[RPROC_TRACE] stage=boot state=ok code=0 System_init Sciclient_init done
[RPROC_TRACE] stage=boot state=ok code=0 System_init CycleCounterP_init start
[RPROC_TRACE] stage=boot state=ok code=0 System_init CycleCounterP_init done
[RPROC_TRACE] stage=boot state=ok code=0 System_init PowerClock_init start
```

그 뒤 trace가 없다.

## 이번 검증으로 확정된 것

이번 한 번의 부팅으로 다음은 확정됐다.

1. `main()` 진입은 정상
2. `System_init()` 진입은 정상
3. `Dpl_init()` 통과
4. `Sciclient_init()` 통과
5. `CycleCounterP_init()` 통과
6. **`PowerClock_init()` 이후로 진행되지 못함**

즉 현재 1차 blocker는 다음으로 좁혀진다.

```text
PowerClock_init() 내부
또는
PowerClock_init() 직후
```

## 의미

이제 더 이상 막연히 `System_init()` 전체가 의심 대상이 아니다.

현재는 다음 두 경우만 남는다.

1. `PowerClock_init()` 내부에서 hang/assert
2. `PowerClock_init()`는 돌아오지만 그 직후 trace flush 전에 fail

하지만 현상상 첫 번째 가능성이 더 크다.

## 다음 우선순위

이제 다음은 `System_init` 전체 trace 확대가 아니라,

```text
PowerClock_init() 내부 또는 generated power/clock init 경로 분해
```

가 우선이다.

즉 다음 단계는:

1. `ti_power_clock_config.c` 내부 init flow 확인
2. 필요 시 `PowerClock_init()` 전후보다 더 아래 단계로 trace 삽입
3. `Pinmux_init()` / `IpcNotify_init()` 쪽은 현재 후순위

## 현재 판단

이번 추가 trace는 목적을 달성했다.

- 한 번의 부팅으로
- `Drivers_open()` 이전이라는 수준을 넘어서
- **`PowerClock_init()` 구간이 현재 stop point**임을 특정했다.
