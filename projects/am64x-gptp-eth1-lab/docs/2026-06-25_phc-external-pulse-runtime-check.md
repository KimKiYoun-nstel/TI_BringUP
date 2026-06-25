# AM64x PHC External Pulse Runtime Check

## 목적

이 문서는 **공식 문서 조사 대신 실제 부팅된 Linux runtime**에서,

- `ptp4l`로 사용하는 PHC가
- `perout` / `PPS` / programmable pin / external timestamp capability를
- 실제로 노출하는지

를 점검한 결과를 정리한다.

최종 질문은 다음이다.

```text
ptp4l로 동기화된 PHC 기준 pulse를
실제 외부 pin/header/test point에서 측정할 수 있는가?
```

## 확인 대상

- SK-AM64B `eth1`
  - driver: `am65-cpsw-nuss`
  - runtime selected PHC: `/dev/ptp0`
- TMDS64EVM `eth2`
  - driver: `icssg-prueth`
  - runtime selected PHC: `/dev/ptp2`
  - `clock_name`: `ICSS IEP timer`

## 실행 방법 요약

### 1. rootfs 기본 상태 확인

- `/dev/ptp*`
- `/sys/class/ptp/ptp*`
- `ethtool -T`
- `/sys/class/ptp/ptp*/n_*`, `pps_available`
- `/sys/class/ptp/ptp*/pins` 존재 여부

### 2. `testptp` 확인

- rootfs에는 `testptp`가 없었다.
- local kernel workspace의 다음 소스를 사용해 `aarch64`용 바이너리를 host에서 cross-build했다.

```text
workspace/ti-linux-kernel-sdk12/tools/testing/selftests/ptp/testptp.c
```

빌드 예:

```bash
source tools/env/sdk-12.00.00.07.04.env
SYSROOT="$LINUX_DEVKIT/sysroots/aarch64-oe-linux"
"${CROSS_COMPILE_AARCH64}gcc" --sysroot="$SYSROOT" -O2 -Wall \
    "$KERNEL_SRC/tools/testing/selftests/ptp/testptp.c" \
    -o /tmp/opencode/testptp-aarch64 -lrt
```

이후 `/tmp/testptp`로 각 보드에 복사해 실행했다.

### 3. direct gPTP 경로 재확인

- `SK eth1 <-> TMDS eth2` direct cable
- SK: `ptp4l -i eth1 -f /tmp/gptp-l2.cfg -m`
- TMDS: `ptp4l -i eth2 -f /tmp/gptp-l2.cfg -m`

runtime에서 다음이 다시 확인되었다.

- SK: `selected /dev/ptp0 as PTP clock`
- TMDS: `selected /dev/ptp2 as PTP clock`
- TMDS: `MASTER -> UNCALIBRATED -> SLAVE`
- TMDS: `delay 436~439 ns` 부근으로 안정화

즉 외부 pulse 가능성 판단 전에 필요한 **direct gPTP 동기화 경로 자체는 정상**이었다.

## Runtime 관찰 결과

### SK-AM64B

- `/dev/ptp0`, `/dev/ptp1` 존재
- `eth1`의 hardware timestamp provider index는 `0`
- 즉 gPTP 실험에서 쓰는 target PHC는 `/dev/ptp0`
- `/dev/ptp0 clock_name`: `CTPS timer`
- `/dev/ptp0 device path`: `/sys/devices/platform/bus@f4000/8000000.ethernet`
- `/sys/class/ptp/ptp0/pins`: 없음
- `testptp -d /dev/ptp0 -l`: 출력 없음

sysfs / `testptp -c` 결과:

```text
n_ext_ts   = 4
n_per_out  = 2
pps        = 1
n_pins     = 0
```

추가 참고:

- 같은 보드에 `/dev/ptp1`도 있으나 `eth1`가 선택하는 PHC는 아님
- `/dev/ptp1`는 `n_per_out = 6`이지만 `pps = 0`

### TMDS64EVM

- `/dev/ptp0`, `/dev/ptp1`, `/dev/ptp2` 존재
- `eth2`의 hardware timestamp provider index는 `2`
- 즉 gPTP 실험에서 쓰는 target PHC는 `/dev/ptp2`
- `/dev/ptp2 clock_name`: `ICSS IEP timer`
- `/dev/ptp2 device path`: `/sys/devices/platform/bus@f4000/30080000.icssg/300ae000.iep`
- `/sys/class/ptp/ptp2/pins`: 없음
- `testptp -d /dev/ptp2 -l`: 출력 없음

sysfs / `testptp -c` 결과:

```text
n_ext_ts   = 0
n_per_out  = 1
pps        = 1
n_pins     = 0
```

## perout / PPS ioctl 결과

### SK `/dev/ptp0`

실행:

```bash
/tmp/testptp -d /dev/ptp0 -p 1000000000 -i 0
/tmp/testptp -d /dev/ptp0 -P 1
```

결과:

- `PTP_PEROUT_REQUEST2`: 성공
- `PTP_ENABLE_PPS`: 성공

즉 Linux runtime 기준으로는 **periodic output request와 PPS enable ioctl이 모두 수용**되었다.

### TMDS `/dev/ptp2`

실행:

```bash
/tmp/testptp -d /dev/ptp2 -p 1000000000 -i 0
/tmp/testptp -d /dev/ptp2 -P 1
```

결과:

- `PTP_PEROUT_REQUEST2`: 성공
- 첫 `PTP_ENABLE_PPS`: `Device or resource busy`
- `-p 0`로 perout request를 다시 넣은 뒤 `PTP_ENABLE_PPS` 재시도: 성공

해석:

- `/dev/ptp2`는 runtime에서 **perout request를 실제로 수용**한다.
- 단일 output resource를 perout/PPS가 공유할 가능성이 높다.

## pinmux / live runtime 상태

### SK-AM64B current runtime

local kernel DTS 기준:

- `k3-am642-sk.dts`
  - `cpts@3d000 { ti,pps = <7 1>; }`
- 하지만 base DTS의 `D18`는 여전히 `ECAP0_IN_APWM_OUT`

runtime debugfs pinctrl:

```text
pin 156 (PIN156): 23100000.pwm ... function main-ecap0-default-pins
```

즉 현재 부팅된 SK는

```text
CPTS/PHC perout capability는 커널에 존재하지만,
실제 외부 출력 pad D18는 아직 ECAP0 기능으로 잡혀 있다.
```

SK에서 외부 pulse를 내보내려면 DTS overlay가 필요하다.

관련 overlay:

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-evm-sk-cpsw3g-pps.dtso
```

이 overlay는 다음을 수행한다.

- `D18`를 `SYNC0_OUT`으로 mux 변경
- `timesync_router`에서 `cpts genf1`를 `SYNC0_OUT`으로 라우팅
- `ecap0` 비활성화

즉 **현재 부팅 형상 그대로는 scope 측정 불가**, overlay 적용 후 재부팅이 필요하다.

### TMDS64EVM current runtime

local kernel DTS 기준:

- `k3-am642-evm.dts`
  - `icssg1_iep0_pins_default`
  - `(W7) PRG1_IEP0_EDC_SYNC_OUT0`
  - `&icssg1_iep0 { pinctrl-0 = <&icssg1_iep0_pins_default>; }`

runtime debugfs pinctrl:

```text
pin 65 (PIN65): 300ae000.iep ... function icssg1-iep0-default-pins
```

즉 현재 부팅된 TMDS는

```text
/dev/ptp2(ICSS IEP)의 output candidate pad가
실제로 IEP pinctrl로 claim된 상태다.
```

이 점은 SK와 달리 **runtime pinmux까지 이미 맞아 있다**는 뜻이다.

## 물리 pin / header / test point 관점

### SK-AM64B

- repo에서 확인된 candidate physical output pin: `D18 / SYNC0_OUT`
- 현재 booted runtime pinmux 상태: `ECAP0_IN_APWM_OUT`
- header/test point 번호: **repo 내부 근거 미확보**
- pinmux status: **현재는 미적용**, overlay 필요

### TMDS64EVM

- repo에서 확인된 candidate physical output pin: `W7 / PRG1_IEP0_EDC_SYNC_OUT0`
- 현재 booted runtime pinmux 상태: **적용됨**
- header/test point 번호: **repo 내부 근거 미확보**

중요한 점은, local repo 안에는 SK/TMDS EVM schematic 또는 assembly/header mapping 문서가 없어

- candidate package ball / mux function
- current runtime pinctrl 적용 여부

까지는 확인되지만,

- 실제 header 번호
- test point 번호
- DNI/mounted 여부
- probe를 어디에 대야 하는지

는 local repo만으로 확정할 수 없었다.

## AM64x PHC External Pulse Runtime Check

### SK-AM64B

* Target interface: `eth1`
* Target PHC: `/dev/ptp0`
* clock_name: `CTPS timer`
* device path: `/sys/devices/platform/bus@f4000/8000000.ethernet`
* testptp available: rootfs 기본 포함 아님, local kernel selftest에서 cross-build 후 실행
* n_pins: `0`
* n_ext_ts: `4`
* n_per_out: `2`
* PPS support: `yes` (`pps=1`, `PTP_ENABLE_PPS` 성공)
* perout/PPS request result: `PTP_PEROUT_REQUEST2` 성공, `PTP_ENABLE_PPS` 성공
* candidate physical output pin: `D18 / SYNC0_OUT`
* header/test point: repo 내부 근거 미확보
* pinmux status: **현재 booted runtime에서는 미적용**, `D18`가 `ECAP0`로 점유 중
* measurement feasibility: **현재 부팅 형상에서는 불가**, CPSW PPS overlay 적용 후 재확인 필요

### TMDS64EVM

* Target interface: `eth2`
* Target PHC: `/dev/ptp2`
* clock_name: `ICSS IEP timer`
* device path: `/sys/devices/platform/bus@f4000/30080000.icssg/300ae000.iep`
* testptp available: rootfs 기본 포함 아님, local kernel selftest에서 cross-build 후 실행
* n_pins: `0`
* n_ext_ts: `0`
* n_per_out: `1`
* PPS support: `yes` (`pps=1`, `PTP_ENABLE_PPS` 성공)
* perout/PPS request result: `PTP_PEROUT_REQUEST2` 성공, `PTP_ENABLE_PPS`도 가능. 단, active perout와 동시에는 `resource busy` 발생 가능
* candidate physical output pin: `W7 / PRG1_IEP0_EDC_SYNC_OUT0`
* header/test point: repo 내부 근거 미확보
* pinmux status: **현재 booted runtime에서 적용됨**, `300ae000.iep`가 pin claim 중
* measurement feasibility: **Linux runtime capability와 pinmux 관점에서는 가능성 높음**, 다만 실제 probe 지점은 repo 내부만으로 확정 불가

### Final Judgement

* Can SK `/dev/ptp0` generate a measurable external pulse?
  * **현재 부팅 형상 기준으로는 아니오.**
  * PHC capability와 perout/PPS ioctl은 존재하지만, 출력 pad가 아직 `ECAP0`에 묶여 있다.

* Can TMDS `/dev/ptp2` generate a measurable external pulse?
  * **Linux runtime capability 기준으로는 예에 가깝다.**
  * `/dev/ptp2`는 `n_per_out=1`, `pps=1`, perout ioctl 성공, IEP output pinmux 적용까지 확인되었다.
  * 다만 실제 측정 위치는 local repo 안에서 확정하지 못했다.

* Is oscilloscope-based PHC sync measurement feasible with current EVM hardware?
  * **TMDS64EVM 쪽은 부분적으로 feasible**하다.
  * **SK-AM64B 쪽은 현재 booted image 상태로는 not feasible**하다.
  * 두 보드 모두에 대해 즉시 scope probe 위치까지 확정하는 수준의 feasibility는 아직 아니다.

* If not feasible, why?
  * SK: current driver/runtime does expose perout/PPS, but **output pinmux is not currently routed to SYNC0_OUT**
  * both boards: **`n_pins = 0`**, so Linux runtime에서 programmable pin 목록을 직접 다루는 방식은 아님
  * both boards: **repo 내부에 external header/test point mapping 근거가 없음**
  * TMDS: output candidate는 살아 있지만 **actual probe point 미확정**

* Recommended alternative:
  * SK는 `k3-am642-evm-sk-cpsw3g-pps.dtso` 적용 후 재부팅해서 `D18/SYNC0_OUT` 측정 경로 재검증
  * TMDS는 현재 `eth2 -> /dev/ptp2` 경로를 유지한 채 `W7 / PRG1_IEP0_EDC_SYNC_OUT0`의 board-level route를 추가 확인
  * board schematic/assembly 자료가 없으면 probe 위치 확정이 어려우므로 custom board test point 설계가 가장 확실함
  * 대안으로 PRU/IEP firmware-generated pulse 또는 R5F timer GPIO pulse를 별도 측정 신호로 쓰는 방법도 현실적임
