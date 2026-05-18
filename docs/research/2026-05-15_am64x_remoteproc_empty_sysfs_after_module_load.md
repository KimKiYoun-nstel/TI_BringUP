# AM64x remoteproc sysfs 미생성 이슈 조사 메모

- 날짜: 2026-05-15
- 상태: Mitigation verified on live board
- 질문:
  - `ti_k3_r5_remoteproc` 모듈을 현재 커널 release에 맞게 배포/로드했는데도 왜 `/sys/class/remoteproc/` 가 비어 있는가?
  - 이 현상을 build/deploy 문제로 봐야 하는가, 아니면 runtime/DT/resource ownership 문제로 봐야 하는가?

## 요약

- 현재 확인된 사실만 놓고 보면 **kernel module mismatch 문제는 해결되었다**.
- clean reboot 직후 live board를 다시 확인한 결과, **R5F/M4F remoteproc 인스턴스는 정상적으로 sysfs에 생성되고 `state=running` 까지 도달한다**.
- 따라서 처음 관측한 empty `/sys/class/remoteproc` 상태는 **정상 boot steady-state를 대표하는 현상이 아니었다**.
- 현재 더 유력한 잔여 문제는 **`rpmsg_json.service` 가 remoteproc/rpmsg 준비 완료 전에 먼저 시작되는 startup timing race** 이다.
- rootfs overlay drop-in으로 `rpmsg_json.service` 시작 전에 `remoteproc1 state=running` 과 `/dev/rpmsg_ctrl1` 생성을 기다리도록 보강했고, live board reboot 후 서비스 정상 동작까지 확인했다.
- 따라서 현 시점의 핵심 질문은 더 이상

```text
모듈을 어떻게 빌드/배포할 것인가?
```

가 아니라,

```text
왜 특정 시점에는 remoteproc object가 release되는 것으로 보였고,
현재 clean boot에서는 정상인데 rpmsg userspace가 너무 일찍 시작되는가?
```

이다.

## 현재까지 확인된 사실

### 1. build/deploy mismatch 문제는 해결됨

기존 문제 정의:

- 실행 중 kernel release: `6.18.13-gc21449208550`
- rootfs에는 `/lib/modules/6.18.13-ti-00778-gc21449208550-dirty/` 만 존재
- 따라서 `modprobe ti_k3_r5_remoteproc` 실패

배경 정리 문서:
- [am64x-r5f-remoteproc-kernel-module-mismatch](file:///home/nstel/ti/TI_Bringup/docs/common/am64x-r5f-remoteproc-kernel-module-mismatch.md)

이번에 추가한 deploy flow로 다음은 해결되었다.

- `/lib/modules/6.18.13-gc21449208550/` 생성/반영
- `ti_k3_r5_remoteproc.ko`
- `ti_k3_m4_remoteproc.ko`
- `rpmsg_char.ko`
- `rpmsg_ctrl.ko`
- 실제 `modprobe` 성공

즉 현재 남은 문제를 **module file 부재**로 설명할 수는 없다.

### 2. remoteproc 정상 baseline 증적이 repo 안에 존재함

이전 boot log에는 AM64x remoteproc이 정상적으로 올라온 흔적이 남아 있다.

근거:
- [First_Boot_LOG_20260507_172151.rtf#L643-L664](file:///home/nstel/ti/TI_Bringup/docs/bringup-logs/First_Boot_LOG_20260507_172151.rtf#L643-L664)

핵심 로그:

```text
configured R5F for remoteproc mode
configured M4F for remoteproc mode
remoteproc remoteproc0: 5000000.m4fss is available
remoteproc remoteproc1: 78000000.r5f is available
remoteproc remoteproc1: Booting fw image am64-main-r5f0_0-fw
remoteproc remoteproc0: Booting fw image am64-mcu-m4f0_0-fw
remote processor 78000000.r5f is now up
virtio_rpmsg_bus virtio0: rpmsg host is online
```

이 baseline은 최소한 다음을 보여준다.

- A53 Linux가 부팅된 상태에서
- R5F/M4F remoteproc이 probe/register 되고
- firmware boot까지 진행되며
- RPMsg host online까지 갈 수 있다

즉 “A53과 R5F는 원리적으로 동시에 활성화될 수 없다”는 진술은 **이 repo의 baseline 증적과는 일치하지 않는다**.

### 3. 최초 관측된 이상 상태

현재 보드에서는 다음이 확인되었다.

- 관련 모듈들은 `lsmod` 에 존재
- 관련 platform device 존재
  - `5000000.m4fss`
  - `bus@f4000:r5fss@78000000`
  - `bus@f4000:r5fss@78400000`
- dmesg에는 probe 초반 흔적이 있음

예:

```text
k3-m4-rproc 5000000.m4fss: assigned reserved memory node memory@a4000000
k3-m4-rproc 5000000.m4fss: configured M4F for remoteproc mode
remoteproc remoteproc0: releasing 5000000.m4fss
remoteproc remoteproc0: releasing 78200000.r5f
remoteproc remoteproc1: releasing 78000000.r5f
remoteproc remoteproc1: releasing 78600000.r5f
remoteproc remoteproc0: releasing 78400000.r5f
```

반면 당시 관측에서는 `/sys/class/remoteproc/` 가 비어 있었다.

이 차이는 중요하다.

- baseline: `is available` → `Booting fw image` → `is now up`
- current: `configured ...` → `releasing ...`

이 시점만 놓고 보면 **remoteproc object registration/lifecycle 유지 실패처럼 보였지만**, 이후 clean reboot 검증에서 이 해석이 boot steady-state의 대표 현상은 아님이 드러났다.

### 4. clean reboot 후 live board 재검증 결과

보드를 재부팅한 뒤, 추가 modprobe 실험 없이 clean boot 상태를 확인했다.

확인 결과:

- `/sys/class/remoteproc/` 에 remoteproc entry가 정상적으로 생성됨
  - `remoteproc0` = `5000000.m4fss`
  - `remoteproc1` = `78000000.r5f`
  - `remoteproc2` = `78200000.r5f`
  - `remoteproc3` = `78400000.r5f`
  - `remoteproc4` = `78600000.r5f`
- 각 entry의 `firmware` 와 `state` 확인 결과:
  - `am64-mcu-m4f0_0-fw` / `running`
  - `am64-main-r5f0_0-fw` / `running`
  - `am64-main-r5f0_1-fw` / `running`
  - `am64-main-r5f1_0-fw` / `running`
  - `am64-main-r5f1_1-fw` / `running`

clean boot dmesg도 baseline과 같은 흐름을 보였다.

```text
remoteproc ... is available
remoteproc ... Booting fw image ...
remote processor ... is now up
virtio_rpmsg_bus ... rpmsg host is online
```

즉 다음은 현재 보드에서 실제로 성립한다.

```text
A53 Linux 부팅 상태에서
R5F/M4F remoteproc 등록 가능
firmware boot 가능
running state 도달 가능
RPMsg host online 가능
```

따라서 “A53과 R5F가 동시에 활성화될 수 없다”는 가설은 현재 live board 증적과 맞지 않는다.

### 5. clean boot에서 드러난 실제 잔여 문제

boot journal을 다시 확인한 결과, 다음 서비스 실패가 확인되었다.

```text
rpmsg_json.service
```

실패 로그:

```text
file_deref_link: readlink failed for /sys/bus/platform/devices/78000000.r5f
_rpmsg_char_find_rproc: 78000000.r5f device is mostly yet to be created!
Can't create an endpoint device: Bad address
```

이 서비스 unit은 다음 ordering만 갖고 있었다.

```text
After=network.target network-online.target
```

즉 remoteproc/rpmsg readiness와는 직접적인 ordering 관계가 없다.

이 증거는 현재 잔여 문제가 다음에 더 가깝다는 것을 보여준다.

```text
R5F 자체가 안 뜨는 문제
```

가 아니라,

```text
rpmsg userspace consumer가 remoteproc/rpmsg 준비 완료 전에 너무 일찍 시작되는 startup timing race
```

### 6. timing race 완화 적용 및 검증

repo에 다음 rootfs overlay drop-in을 추가했다.

- [rootfs overlay override](file:///home/nstel/ti/TI_Bringup/rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf)

핵심 동작:

- `ExecStartPre` 에서 최대 30초 동안 다음을 기다림
  - `/sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc1/state`
  - 그 값이 `running`
  - `/dev/rpmsg_ctrl1` 존재
- `Restart=on-failure`
- `RestartSec=5`

live board에서 확인한 timing:

```text
18.127s  systemd: Starting rpmsg_json.service...
26.499s  remoteproc remoteproc0: 5000000.m4fss is available
26.666s  remoteproc remoteproc1: 78000000.r5f is available
26.757s  virtio_rpmsg_bus virtio1: rpmsg host is online
29.824s  systemd: Started rpmsg_json.service.
```

boot 후 결과:

- `rpmsg_json.service` = `active (running)`
- `remoteproc0..4` = 모두 `state=running`
- `/dev/rpmsg*`, `/dev/rpmsg_ctrl*` 정상 생성
- `rpmsg_json` 로그에서 round-trip 측정 및 `oob_update.json` 출력 확인

이다.

## remoteproc 관점에서 `/sys/class/remoteproc` 의 의미

로컬 정리 문서에서도 R5F bring-up 일반 흐름을 다음처럼 정리했다.

근거:
- [am64x-r5f-remoteproc-kernel-module-mismatch#L22-L30](file:///home/nstel/ti/TI_Bringup/docs/common/am64x-r5f-remoteproc-kernel-module-mismatch.md#L22-L30)

```text
1. R5F platform device가 DT 기반으로 생성된다.
2. Linux remoteproc driver가 해당 device에 bind된다.
3. /sys/class/remoteproc/remoteprocX 인터페이스가 생성된다.
4. R5F firmware를 지정하고 load/start한다.
5. state=running 여부를 확인한다.
6. RPMsg 또는 실제 peripheral 제어로 기능 동작을 검증한다.
```

따라서 `/sys/class/remoteproc/` 가 비어 있다는 것은 보통 다음 의미에 가깝다.

```text
모듈이 없어서 로드가 안 됐다
```

가 아니라,

```text
remoteproc device가 최종적으로 등록 상태에 남지 못했다
```

이다.

## 커널 source 관점 근거

remoteproc core의 release 로그는 실제 remoteproc device object가 해제될 때 찍힌다.

근거:
- [remoteproc_core.c#L2503-L2518](file:///home/nstel/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12/drivers/remoteproc/remoteproc_core.c#L2503-L2518)

핵심:

```c
dev_info(&rproc->dev, "releasing %s\n", rproc->name);
```

즉 현재 보드에서 보인 `releasing ...` 는 단순 informational string이 아니라,
**생성된 remoteproc device가 release path로 들어갔다**는 직접 증거다.

또 sysfs interface 자체는 remoteproc device가 살아 있는 동안 의미가 있다.

근거:
- [remoteproc_sysfs.c](file:///home/nstel/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12/drivers/remoteproc/remoteproc_sysfs.c)

따라서 `/sys/class/remoteproc` 가 비어 있다는 것은
remoteproc core가 사용자에게 노출할 device를 유지하지 못했다는 해석과 일치한다.

## TI 공식 문서에서 확인한 방향

TI Processor SDK Linux AM64x IPC 문서 계열은 AM64x에서 A53 Linux가 remote core(R5F/M4F)를 제어하는 흐름을 전제한다.

참고:
- TI Processor SDK Linux AM64x IPC / Remoteproc 문서
  - `https://software-dl.ti.com/processor-sdk-linux/esd/AM64X/latest/exports/docs/linux/Foundational_Components_IPC64x.html`

이번 parallel research 요약에서 확인한 포인트:

- AM64x에서 A53 Linux가 R5F/M4F를 boot/control 하는 흐름이 TI 문서에 존재함
- firmware naming/path는 core별 기대 경로가 있음
- remoteproc sysfs 기반 확인 절차가 전제됨
- AM64x에서 early boot 대신 Linux/userspace flow가 중요한 축으로 다뤄짐

즉 TI 공식 방향도 “A53 Linux와 R5F remoteproc control은 공존 가능한 모델”에 가깝고,
현재 현상은 그 일반 모델이 깨진 예외 상태로 봐야 한다.

## 현재 단계에서 build/deploy를 1차 원인으로 보기 어려운 이유

다음 네 가지가 이미 충족되었기 때문이다.

1. 현재 `uname -r` 와 `/lib/modules/<release>` 일치
2. required `.ko` 파일 존재
3. `modprobe` 성공
4. `lsmod` 로 실제 적재 확인

따라서 남은 현상을 설명하려면 최소한 다음 중 하나가 더 필요하다.

- probe 이후 resource/ownership conflict
- DT wiring mismatch
- firmware / mailbox / reserved-memory / TI-SCI sequence 문제
- remoteproc 생성 후 특정 late runtime experiment에서 unwind/release되는 경로
- userspace startup ordering race

## 현재 가능한 가설 (사실과 분리)

아래는 **확정 결론이 아니라 조사 우선순위용 가설**이다.

### 가설 1. late userspace / runtime sequencing issue

- clean boot steady-state에서는 remoteproc과 rpmsg가 정상적으로 올라옴
- 그러나 `rpmsg_json.service` 는 remoteproc ready 이전에 시작되어 실패함
- 초기 empty sysfs 관측은 late runtime unload/reload 또는 관측 타이밍 영향일 가능성이 큼

### 가설 2. 일부 수동 modprobe/rmmod 실험이 release path를 관측하게 만들었을 가능성

- 재부팅 전에는 `configured ...` 뒤 `releasing ...` 가 보였음
- clean reboot 후에는 baseline과 같은 정상 boot path가 재현됨
- 따라서 earlier observation은 boot steady-state보다 late experiment path였을 수 있음

### 가설 3. R5F ownership/state conflict

- 다른 boot stage(SBL/system firmware/secure world/other runtime component)가 R5F state를 먼저 잡고 있을 수 있음
- 이 경우 Linux remoteproc이 probe를 시작해도 완전한 제어권을 얻지 못하고 release될 수 있음

### 가설 4. Device Tree wiring mismatch

- current DTB에서 remoteproc child/core node, reserved-memory, mboxes, memory-region, firmware binding 중 일부가 baseline과 달라졌을 수 있음
- baseline에서는 `is available` → `Booting fw image` 까지 갔지만 current는 그 전/중간에서 unwind되는 것으로 보임

### 가설 5. Firmware/resource dependency mismatch

- firmware 파일 자체 부재보다,
- firmware expectation과 carveout/resource table/mailbox/resource ownership이 맞지 않아 registration이 유지되지 않을 수 있음

### 가설 6. A53/R5F coexistence에 대한 현장 관찰은 “불가능”이 아니라 “특정 타이밍/설정에서 충돌”일 수 있음

- repo baseline log는 A53 + R5F 공존 사례를 이미 보여준다
- 따라서 “동시에 활성화 안 된다”는 관찰은 generic truth라기보다 current boot policy/config/resource 조합 문제일 가능성이 높다

## 다음 조사 포인트

### 1. `rpmsg_json.service` startup ordering 수정 또는 지연 실험

우선순위가 가장 높다.

확인 대상:

- service가 remoteproc/rpmsg ready 이후에 시작되도록 조정 가능한가
- 단순 재시작 시 성공하는가
- rpmsg endpoint 생성 코드가 `/sys/bus/platform/devices/78000000.r5f` 준비 완료까지 기다려야 하는가

현재는 첫 번째 완화책을 적용해 live board에서 정상 동작을 확인했다.
남은 것은 이 방식이 지속 가능한 제품/배포 정책으로 적절한지 판단하는 것이다.

### 2. baseline boot log vs current DTB 차이 비교

우선순위가 가장 높다.

확인 대상:

- R5F/M4F 관련 DT node status
- `memory-region`
- `mboxes` / mailbox controller wiring
- firmware name / alias / cluster-core topology
- TI SCI / power-domain 관련 node

### 3. current runtime에서 remoteproc release가 다시 재현되는 정확한 조작 시퀀스 확인

현재는 clean boot에서는 정상이고, earlier manual investigation path에서만 `releasing ...` 가 관측되었다.

더 확인할 것:

- 어떤 `modprobe` / `modprobe -r` / service action 이후에 release가 보였는가
- 해당 시점에 `/sys/class/remoteproc` 가 실제로 비워지는가

### 4. current runtime에서 remoteproc probe failure 직전 로그 더 수집

현재는 `releasing ...` 만 보였고, 직접적인 failure reason log가 충분하지 않다.

더 확인할 것:

- probe 직전/직후 full dmesg
- deferred probe / error return 흔적
- TI SCI / mailbox / reserved-memory 관련 error

### 5. current DTB를 decompile하여 baseline expectation과 대조

특히 다음이 중요하다.

- `78000000.r5f`, `78200000.r5f`, `78400000.r5f`, `78600000.r5f`
- `5000000.m4fss`
- 관련 reserved memory node

### 6. A53/R5F coexistence 주장 검증

현재 repo baseline, clean reboot live board 증적, TI 문서를 근거로 보면 “항상 불가능”이라고 말하기는 어렵다.

따라서 다음처럼 재정의해야 한다.

```text
이 보드/이 부트 체인/이 DTB/이 resource ownership 조합에서
A53 Linux가 R5F remoteproc을 기대대로 제어하지 못하고 있는가?
```

## 현재 시점의 판단

현 시점에서 가장 타당한 정리는 다음과 같다.

```text
module build/deploy mismatch는 해결되었다.
clean reboot 기준으로 remoteproc registration/lifecycle도 정상이다.
현재 live board에서 더 실제적인 잔여 문제는
rpmsg userspace consumer startup ordering race 이다.
따라서 우선순위는 build/deploy나 generic remoteproc bring-up failure가 아니라
service timing / late runtime sequencing 확인 쪽으로 이동한다.
```

현 시점에서 live board 기준 완화책은 적용되었고, 서비스 정상 동작까지 확인되었다.

## BSP/Bring-up 관점 재사용 포인트

- `modprobe` 성공과 R5F usable 상태는 같은 것이 아니지만, clean reboot에서는 실제로 `remoteprocX` 와 `state=running` 까지 확인해야 결론을 낼 수 있다.
- `/sys/class/remoteproc/remoteprocX` 유무는 “제어 인터페이스가 살아 있는가”를 보는 핵심 분기점이다.
- baseline boot log를 남겨 두면 “이 SoC/board가 원리적으로 가능한가”를 빠르게 반박/확인할 수 있다.
- AM64x에서 remoteproc 문제는 build/deploy mismatch, DT wiring, runtime ownership, firmware-resource dependency를 분리해서 봐야 한다.
- AM64x에서 RPMsg userspace 문제는 remoteproc/rpmsg ready ordering race와 분리해서 봐야 한다.

## 확인 필요

- `rpmsg_json.service` 를 remoteproc/rpmsg ready 이후로 지연했을 때 정상 동작하는지
- earlier `releasing ...` 관측을 재현하는 정확한 runtime 조작 시퀀스
- current DTB에서 baseline 대비 remoteproc node/property 차이
