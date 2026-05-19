# AM64x remoteproc firmware-name 흐름 정리

## 목적

이 문서는 AM64x 계열, 특히 SK-AM64B에서 A53 Linux가 R5F/M4F/PRU remote core 펌웨어를 어떤 이름으로 찾고, 어디에서 그 이름을 가져오며, 어떤 순서로 로드/실행하는지 정리한다.

이 내용은 커스텀 보드 BSP 포팅 시 R5F/M4F firmware 교체, rootfs firmware layout 구성, Device Tree 수정 범위를 판단하기 위한 공통 지식으로 사용한다.

## 결론

AM64x에서 `am64-main-r5f0_0-fw` 같은 firmware 이름은 CPU core에 하드웨어적으로 고정된 이름이 아니다.

현재 확인된 TI Processor SDK Linux 12 기반 kernel/DT 기준으로 이 이름은 Device Tree의 `firmware-name` property에서 온다.

```text
DTS/DTSI
  arch/arm64/boot/dts/ti/k3-am64-main.dtsi
  arch/arm64/boot/dts/ti/k3-am64-mcu.dtsi
        ↓
DTB
        ↓
U-Boot가 Linux Kernel에 전달
        ↓
ti_k3_r5_remoteproc / ti_k3_m4_remoteproc probe
        ↓
/sys/class/remoteproc/remoteprocX/firmware
        ↓
/usr/lib/firmware/<firmware-name>
        ↓
R5F/M4F firmware load/start
```

## 확인된 SDK source 위치

Host SDK source에서 다음 grep 결과를 확인했다.

```text
arch/arm64/boot/dts/ti/k3-am64-main.dtsi:935: firmware-name = "am64-main-r5f0_0-fw";
arch/arm64/boot/dts/ti/k3-am64-main.dtsi:951: firmware-name = "am64-main-r5f0_1-fw";
arch/arm64/boot/dts/ti/k3-am64-main.dtsi:980: firmware-name = "am64-main-r5f1_0-fw";
arch/arm64/boot/dts/ti/k3-am64-main.dtsi:996: firmware-name = "am64-main-r5f1_1-fw";
arch/arm64/boot/dts/ti/k3-am64-mcu.dtsi:171: firmware-name = "am64-mcu-m4f0_0-fw";
```

PRU/RTU/TX_PRU 계열 firmware-name도 `k3-am64-main.dtsi`에 정의되어 있다.

## 확인된 remote core 매핑

SK-AM64B runtime에서 확인한 매핑은 다음과 같다.

```text
78000000.r5f  -> am64-main-r5f0_0-fw
78200000.r5f  -> am64-main-r5f0_1-fw
78400000.r5f  -> am64-main-r5f1_0-fw
78600000.r5f  -> am64-main-r5f1_1-fw
5000000.m4fss -> am64-mcu-m4f0_0-fw
```

주의할 점은 `remoteproc0`, `remoteproc1` 같은 번호는 probe 순서에 따라 달라질 수 있다는 것이다. 자동화 스크립트에서는 반드시 번호가 아니라 `name` 값을 기준으로 target remoteproc을 찾아야 한다.

## runtime Device Tree 확인 방법

타겟 보드에서 아래 명령으로 실제 부팅된 DTB에 `firmware-name`이 포함되어 있는지 확인할 수 있다.

```sh
for r in /sys/class/remoteproc/remoteproc*; do
    echo "== $r =="
    cat "$r/name" 2>/dev/null
    cat "$r/firmware" 2>/dev/null
    OFNODE=$(readlink -f "$r/device/of_node" 2>/dev/null)
    echo "of_node=$OFNODE"
    ls -al "$OFNODE/firmware-name" 2>/dev/null
    strings "$OFNODE/firmware-name" 2>/dev/null
 done
```

확인된 예:

```text
/sys/firmware/devicetree/base/bus@f4000/r5fss@78000000/r5f@78000000/firmware-name
am64-main-r5f0_0-fw
```

## driver와 firmware의 차이

`ti_k3_r5_remoteproc.ko`는 R5F에서 실행되는 펌웨어가 아니다. A53 Linux kernel 안에서 실행되는 R5F 제어용 driver/module이다.

```text
ti_k3_r5_remoteproc.ko
  = A53 Linux 쪽 R5F lifecycle manager / loader / controller

am64-main-r5f0_0-fw
  = 실제 R5F core에서 실행되는 firmware
```

## kernel config 기준 구조

현재 확인된 설정:

```text
CONFIG_REMOTEPROC=y
CONFIG_REMOTEPROC_CDEV=y
CONFIG_TI_K3_R5_REMOTEPROC=m
CONFIG_TI_K3_M4_REMOTEPROC=m
CONFIG_PRU_REMOTEPROC=m
CONFIG_RPMSG=y
CONFIG_RPMSG_CHAR=m
CONFIG_RPMSG_CTRL=m
CONFIG_RPMSG_NS=y
CONFIG_RPMSG_VIRTIO=y
```

의미:

```text
remoteproc core framework = kernel built-in
TI K3 R5F/M4F/PRU remoteproc driver = kernel module
rpmsg_char / rpmsg_ctrl = kernel module
```

## module load와 firmware 실행 흐름

현재 구성에서는 R5F driver module이 로드되면 DT node probe 이후 remoteproc core의 auto boot 흐름에 의해 firmware가 자동 실행된다.

```text
ti_k3_r5_remoteproc.ko load
  -> platform driver 등록
  -> DT의 r5f node probe
  -> firmware-name 읽음
  -> remoteproc device 생성
  -> /sys/class/remoteproc/remoteprocX 생성
  -> /usr/lib/firmware에서 firmware 요청
  -> R5F memory/resource table 처리
  -> R5F reset 해제
  -> R5F firmware 실행
```

## sysfs state 제어의 의미

```sh
echo stop > /sys/class/remoteproc/remoteprocX/state
echo start > /sys/class/remoteproc/remoteprocX/state
```

이 명령은 user program을 실행하는 것이 아니라, A53 Linux kernel의 remoteproc framework에 remote core lifecycle 제어를 요청하는 것이다.

```text
echo start
  -> firmware load
  -> memory carveout/resource table 처리
  -> R5F reset 해제
  -> R5F firmware 실행

echo stop
  -> R5F shutdown sequence 수행
  -> 필요 시 graceful shutdown handshake
  -> R5F 정지
```

## module unload/load와 sysfs stop/start의 차이

`modprobe -r ti_k3_r5_remoteproc` / `modprobe ti_k3_r5_remoteproc`는 A53 Linux driver lifecycle을 흔드는 작업이다.

반면 sysfs `state` 제어는 이미 probe된 remoteproc device를 유지한 상태에서 remote core firmware lifecycle만 제어하는 작업이다.

```text
module unload/load
  = Linux driver 제거/재등록
  = platform device remove/probe 재수행
  = remoteproc/rpmsg/virtio/mailbox/carveout 구조 전체에 영향

sysfs stop/start
  = 이미 probe된 remoteproc device 유지
  = R5F firmware만 stop/start
  = firmware 개발 루프에 더 적합
```

## 커스텀 보드 BSP 관점

커스텀 보드에서 R5F/M4F firmware 이름을 고정 변경하려면 다음 중 하나를 선택한다.

1. Board DTS 또는 overlay에서 `firmware-name` override
2. DTS의 기본 이름은 유지하고 rootfs의 `/usr/lib/firmware/<firmware-name>` symlink만 교체
3. 개발 중에는 sysfs의 `firmware` attribute로 임시 firmware 이름 지정

정식 BSP 반영은 DTS/DTBO 또는 rootfs firmware packaging 정책으로 관리하고, 단기 개발 루프는 symlink 또는 sysfs override를 사용한다.

