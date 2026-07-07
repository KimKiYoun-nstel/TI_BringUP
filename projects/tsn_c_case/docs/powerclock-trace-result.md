# AM64x TSN C Case C5 Path B PowerClock Step Trace Result

## 목적

`PowerClock_init()` 내부를 module/clock 단위로 분해해,
현재 B 단계 stop point를 한 번의 부팅으로 특정한다.

## 추가한 trace 범위

대상 파일:

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/ccs_projects/
  gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/
  Release/syscfg/ti_power_clock_config.c
```

추가 trace:

- `PowerClock_init enter`
- `PowerClock_init module enable done`
- `PowerClock_init clock set done`
- `pwr_mod_enable_start/done`
- `pwr_clk_set_start/done`
- `pwr_mod_enable_failed`
- `pwr_clk_set_failed`

`pwr_clk_set_*`는 아래 정보를 함께 출력하도록 했다.

```text
module
clk
rate
parent
idx
```

## 보드 적용 방식

이전과 동일한 temporary boot-time override를 사용했다.

- Linux ICSSG ownership disable 3개 유지
- `firmware-name = gptp_icssg_linux_remoteproc_r5f0_0_test.out`

## 관찰 결과

`/sys/kernel/debug/remoteproc/remoteproc1/trace0`에서 다음을 확인했다.

```text
[RPROC_TRACE] stage=boot state=ok code=0 System_init PowerClock_init start
[RPROC_TRACE] stage=boot state=ok code=0 PowerClock_init enter
[RPROC_TRACE] stage=boot state=pwr_mod_enable_start code=0 module=102 idx=0
[RPROC_TRACE] stage=boot state=pwr_mod_enable_done code=0 module=102 idx=0
[RPROC_TRACE] stage=boot state=pwr_mod_enable_start code=0 module=103 idx=1
[RPROC_TRACE] stage=boot state=pwr_mod_enable_done code=0 module=103 idx=1
[RPROC_TRACE] stage=boot state=pwr_mod_enable_start code=0 module=82 idx=2
[RPROC_TRACE] stage=boot state=pwr_mod_enable_done code=0 module=82 idx=2
[RPROC_TRACE] stage=boot state=ok code=0 PowerClock_init module enable done
[RPROC_TRACE] stage=boot state=pwr_clk_set_start code=0 module=82 clk=0 rate=333333333 parent=2 idx=0
[RPROC_TRACE] stage=boot state=error code=-1 pwr_clk_set_failed module=82 clk=0 rate=333333333 parent=2 idx=0
```

## 현재 확정된 사실

### 통과한 단계

1. `System_init()` 진입
2. `Dpl_init()`
3. `Sciclient_init()`
4. `CycleCounterP_init()`
5. `PowerClock_init()` 진입
6. module clock enable
   - `module=102`
   - `module=103`
   - `module=82`

### 실패한 단계

다음 항목에서 첫 실패가 발생한다.

```text
SOC_moduleSetClockFrequencyWithParent(
  module=82,
  clk=0,
  rate=333333333,
  parent=2
)
-> code = -1
```

## 의미

이제 stop point는 다음 수준으로 특정됐다.

```text
PRU_ICSSG1 core clock frequency 설정
```

즉 현재 문제는 더 이상

- `System_init()` 전체
- `PowerClock_init()` 전체
- `module enable`

가 아니라,

- `PRU_ICSSG1 core clock set with parent`

이다.

## donor와의 관계

현재 `ti_power_clock_config.c`는 donor `gptp_icssg_switch` generated output과 거의 동일하다.

주요 차이는 donor에 있던 `UART0` clock 항목이 Path B에서는 빠진 정도다.

따라서 현재 failure는

- 단순 file drift

보다는,

- remoteproc/Linux IPC scaffold 환경에서 donor의 `PRU_ICSSG1 clock parent/rate request`가 현재 runtime 전제와 맞지 않음

쪽으로 해석하는 것이 합리적이다.

## 다음 우선순위

이제 다음 작업은 trace 확대가 아니라 다음 둘 중 하나다.

1. `module=82 clk=0 rate=333333333 parent=2` 설정을 우회/완화
2. donor의 clock request를 유지하되, 현재 remoteproc runtime에서 왜 `-1`이 나는지 parent/rate 조합을 조정

즉 다음 단계는 **실제 power/clock 설정 수정**이다.

## 후속 parent/rate 검증 결과

위 초기 결과 이후, 같은 `PRU_ICSSG1 core clock`에 대해 parent/rate 조합을 추가로 시험했다.

### 시험 1. parent-free rate-only 경로

근거:

- TI SDK `bootloader_soc.c`는 `PRU_ICSSG1 core clock`를 `SOC_moduleSetClockFrequency()`로 요청한다.
- 즉 fixed parent 강제보다 `rate-only` 경로가 runtime에서 더 적합할 가능성을 검토했다.

결과:

- `remoteproc ... Booting fw image ...`는 보였지만
- `remote processor 78000000.r5f is now up`가 나타나지 않았고
- 이후 Linux에서 해당 remoteproc는 `offline` 상태였다.

즉 `rate-only` 변경은 현재 기준으로 개선을 증명하지 못했다.

### 시험 2. parent=1 + rate=333333333

근거:

- `PRU_ICSSG1 core clock`는 parent 후보가 2개뿐이다.
- 기존 donor parent=2가 실패했으므로 남은 다른 유효 parent인 `1`을 검증했다.

결과 trace:

```text
pwr_clk_set_start module=82 clk=0 rate=333333333 parent=1 idx=0
pwr_clk_set_failed module=82 clk=0 rate=333333333 parent=1 idx=0 code=-1
```

즉 parent=1에서도 333MHz는 실패했다.

### 시험 3. parent=1 + rate=200000000

근거:

- `333MHz`뿐 아니라 `rate` 자체가 문제일 가능성을 보기 위해 lower rate를 시험했다.
- `200MHz`는 같은 ICSSG clock domain과 IEP 관련 설정에서 자주 쓰이는 값이므로 첫 후보로 선택했다.

결과 trace:

```text
pwr_clk_set_start module=82 clk=0 rate=200000000 parent=1 idx=0
pwr_clk_set_failed module=82 clk=0 rate=200000000 parent=1 idx=0 code=-1
```

즉 parent=1에서도 200MHz는 실패했다.

## 현재 추가 결론

이제 다음 사실까지 확보됐다.

1. donor 원래 조합 `parent=2 + 333333333` 실패
2. 남은 다른 유효 parent `parent=1 + 333333333` 실패
3. lower rate `parent=1 + 200000000`도 실패

따라서 현재는 단순히

- 특정 parent 하나의 문제
- 333MHz 한 값의 문제

로 보기는 어렵다.

현재 해석은 다음이 더 타당하다.

```text
remoteproc-hosted runtime에서
PRU_ICSSG1 core clock set request 자체가 허용되지 않거나,
현재 시점에서는 이미 다른 owner/boot stage가 정한 상태와 충돌한다.
```

즉 다음 분석/수정은

- parent 1/2 더 바꿔보기
- rate 조금씩 바꿔보기

를 반복하기보다,

- 이 clock request를 app 쪽에서 해야 하는 전제 자체가 맞는지
- remoteproc 환경에서는 이미 설정된 clock을 재요청하면 안 되는지
- core clock 설정을 건드리지 않고 진행해야 하는지

를 검토하는 쪽이 맞다.

## Path 1 실보드 검증 확정 결과

이후 U-Boot temporary `fdt set` 경로를 다시 정리해, Linux가 실제로 수정된 DT를 받는지부터 재검증했다.

확인된 사실:

1. `model = TI_Bringup_Path1_Marker`를 넣으면 Linux early boot의 `Machine model:`에 그대로 반영된다.
2. `/bus@f4000/r5fss@78000000/r5f@78000000/firmware-name`를 `gptp_icssg_linux_remoteproc_r5f0_0_test.out`로 override하면 Linux remoteproc가 실제로 해당 test ELF를 읽는다.
3. `/icssg1-eth`, `port@2`, `mdio-mux-1` disable도 적용되어 Linux에서는 `eth0`만 남는다.

즉 이 시점부터는 **U-Boot temporary DT override 경로 자체는 정상**이라고 봐도 된다.

### 1차 Path 1: `clk0(core)`만 skip

trace 결과:

```text
pwr_clk_get_parent module=82 clk=0 parent=2
pwr_clk_get_freq   module=82 clk=0 freq=333333333
pwr_clk_set_skip   module=82 clk=0 reason=remoteproc_hosted_policy
```

바로 다음 실패:

```text
pwr_clk_set_start  module=82 clk=19 rate=192000000 parent=SOC_MODULES_END
pwr_clk_set_failed module=82 clk=19 rate=192000000 parent=SOC_MODULES_END code=-1
```

해석:

- `clk0(core)`는 이미 host/TIFS runtime이
  - `parent=2`
  - `freq=333333333`
  로 준비해 둔 상태였다.
- app 쪽 재요청을 skip하면 해당 단계는 통과한다.
- 그러나 곧바로 같은 `module=82`의 `clk19(UCLK)` request가 새 blocker로 드러난다.

### 2차 Path 1 확장: `module=82` clock request 전체 skip

동일한 remoteproc-hosted policy를 `module=82`의 clock list 전체에 적용했다.

관찰 결과:

```text
clk=0  get_parent=2   get_freq=333333333  -> skip
clk=19 get_parent failed, get_freq=192000000 -> skip
clk=3  get_parent=4   get_freq=225000000  -> skip
PowerClock_init clock set done
System_init call done
Board_init call done
Drivers_open done
Board_driversOpen done
EnetApp_mainTask entry
```

즉 다음이 확정됐다.

1. `PRU_ICSSG1 core clock` 문제는 실제 ownership/runtime model issue였다.
2. 같은 유형의 ownership/permission mismatch가 `module=82`의 다른 clock request에도 이어진다.
3. `PowerClock_init()` 자체는 remoteproc-hosted skip policy로 통과 가능하다.

## 현재 최신 blocker

`PowerClock_init()`을 넘긴 최신 trace에서는 다음에서 멈춘다.

```text
EnetUdma_openRxCh
Enet_open failed
Assertion @ Line: 500 in syscfg/ti_enet_open_close.c
```

즉 현재 기준 최신 stop point는 더 이상 clock set이 아니다.

```text
PowerClock ownership issue: 확인/우회 완료
다음 blocker: Enet/UDMA open path
```

guide 기준으로 보면 이제 `Path 2 Resource Ownership Audit`로 이동하는 것이 자연스럽다.
