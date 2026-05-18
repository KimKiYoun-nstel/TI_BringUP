# AM64x R5F Remoteproc 커널 모듈 불일치 이슈 정리

## Knowledge

AM64x 계열 SoC는 heterogeneous multicore 구조이다. A53 core는 Linux가 직접 실행되는 application core이고, R5F core는 Linux 프로세스를 직접 실행하는 CPU가 아니라 별도 firmware를 실행하는 remote processor로 다루는 것이 일반적이다.

구조적으로는 다음과 같이 이해한다.

```text
A53 core:
  Linux kernel + userspace 실행

R5F core:
  RTOS 또는 bare-metal firmware 실행

A53 <-> R5F:
  remoteproc, RPMsg, mailbox, shared memory 등을 통해 제어/통신
```

따라서 A53 Linux가 정상 부팅되었다고 해서 R5F firmware가 자동으로 실행 중이라고 판단하면 안 된다. R5F의 정상 동작 여부는 별도 검증 항목으로 확인해야 한다.

R5F bring-up의 일반적인 단계는 다음과 같다.

```text
1. R5F platform device가 DT 기반으로 생성된다.
2. Linux remoteproc driver가 해당 device에 bind된다.
3. /sys/class/remoteproc/remoteprocX 인터페이스가 생성된다.
4. R5F firmware를 지정하고 load/start한다.
5. state=running 여부를 확인한다.
6. RPMsg 또는 실제 peripheral 제어로 기능 동작을 검증한다.
```

## 현재 관측된 상태

보드에서 확인한 kernel version은 다음과 같다.

```text
uname -r
6.18.13-gc21449208550
```

하지만 rootfs에 설치된 module directory는 다음 하나뿐이다.

```text
/lib/modules/6.18.13-ti-00778-gc21449208550-dirty/
```

R5F remoteproc 모듈 파일은 rootfs 안에 존재한다.

```text
/lib/modules/6.18.13-ti-00778-gc21449208550-dirty/kernel/drivers/remoteproc/ti_k3_r5_remoteproc.ko
```

RPMsg 관련 모듈도 존재한다.

```text
/lib/modules/6.18.13-ti-00778-gc21449208550-dirty/kernel/drivers/rpmsg/rpmsg_char.ko
/lib/modules/6.18.13-ti-00778-gc21449208550-dirty/kernel/drivers/rpmsg/rpmsg_ctrl.ko
```

그러나 현재 실행 중인 kernel이 찾는 위치는 다음이다.

```text
/lib/modules/6.18.13-gc21449208550/
```

해당 디렉터리가 없기 때문에 `modprobe ti_k3_r5_remoteproc`는 실패한다.

```text
modprobe: FATAL: Module ti_k3_r5_remoteproc not found in directory /lib/modules/6.18.13-gc21449208550
```

또한 기존 rootfs에 있는 모듈의 `vermagic`은 다음과 같이 현재 실행 중인 kernel release와 다르다.

```text
vermagic: 6.18.13-ti-00778-gc21449208550-dirty SMP preempt mod_unload aarch64
```

## 이슈의 본질

이번 문제는 R5F firmware가 없어서 발생한 문제가 아니다. rootfs에는 TI 예제 R5F firmware들이 이미 존재한다.

예시:

```text
/lib/firmware/am64-main-r5f0_0-fw
/lib/firmware/am64-main-r5f0_1-fw
/lib/firmware/am64-main-r5f1_0-fw
/lib/firmware/am64-main-r5f1_1-fw
/lib/firmware/ti-ipc/am64xx/ipc_echo_test_*.xer5f
```

문제의 핵심은 다음이다.

```text
커널 Image는 로컬에서 rebuild한 것으로 교체했다.
rootfs는 TI SDK WIC 이미지의 기존 rootfs를 그대로 사용했다.
그 결과 uname -r과 /lib/modules/<version>이 불일치했다.
```

즉 `Kernel Image`와 `rootfs kernel modules`가 같은 빌드 산출물이 아니다.

인과관계는 다음과 같다.

```text
직접 빌드한 kernel Image로 부팅
  -> uname -r = 6.18.13-gc21449208550
  -> rootfs에는 /lib/modules/6.18.13-ti-00778-gc21449208550-dirty만 존재
  -> modprobe가 /lib/modules/6.18.13-gc21449208550에서 모듈을 찾음
  -> ti_k3_r5_remoteproc.ko를 찾지 못함
  -> R5F remoteproc driver가 kernel에 등록되지 않음
  -> r5fss platform device에 driver bind 안 됨
  -> /sys/class/remoteproc/가 비어 있음
  -> R5F firmware start/stop/running 확인 불가
```

## 왜 이런 일이 생겼는가

Embedded Linux BSP에서 kernel Image, DTB, kernel modules는 한 세트로 관리해야 한다.

```text
/boot/Image
/boot/dtb/*.dtb
/lib/modules/$(uname -r)/
```

TI prebuilt WIC 이미지는 원래 다음과 같은 세트로 구성되어 있었을 가능성이 높다.

```text
TI prebuilt kernel Image
TI prebuilt DTB
TI prebuilt /lib/modules/6.18.13-ti-00778-gc21449208550-dirty/
```

하지만 로컬에서 kernel Image만 rebuild하여 교체하면, kernel release string이 달라질 수 있다.

Linux kernel의 `uname -r`은 단순히 `6.18.13` 같은 base version만으로 정해지지 않는다. 다음 요소들이 포함될 수 있다.

```text
VERSION / PATCHLEVEL / SUBLEVEL
EXTRAVERSION
CONFIG_LOCALVERSION
LOCALVERSION 환경변수
scripts/setlocalversion 결과
git describe 결과
소스 tree dirty 상태
TI recipe가 부여한 local version 문자열
```

그래서 같은 소스를 기반으로 rebuild했다고 해도 다음처럼 kernel release가 달라질 수 있다.

```text
TI prebuilt:
  6.18.13-ti-00778-gc21449208550-dirty

로컬 rebuild:
  6.18.13-gc21449208550
```

이 차이 때문에 Linux는 기존 rootfs의 모듈을 자동으로 찾지 못한다.

## Decision

이번 R5F 이슈는 다음과 같이 판정한다.

```text
R5F 하드웨어:
  존재함

R5F firmware:
  rootfs에 존재함

R5F Linux 제어 드라이버:
  모듈 파일은 rootfs에 존재하지만 현재 kernel release와 불일치

현재 문제:
  kernel Image와 /lib/modules/<version> 불일치로 ti_k3_r5_remoteproc 모듈 로드 실패

현재 R5F 상태:
  Linux remoteproc 기준으로 제어/시작/상태확인 불가
```

## Action Item

로컬 빌드 Repo의 Agent에게 지시할 작업은 다음과 같다.

```text
현재 부팅에 사용 중인 kernel Image와 동일한 kernel source/config/build output 기준으로 kernel modules를 빌드하고,
그 modules_install 결과를 rootfs에 반영한다.
```

구체적인 작업 지시:

```text
1. 현재 로컬에서 빌드한 AM64x kernel Image의 kernelrelease를 확인한다.
   예: make ARCH=arm64 kernelrelease

2. kernel modules를 빌드한다.
   예: make ARCH=arm64 modules

3. rootfs staging 경로 또는 SD card rootfs mount 경로로 modules_install을 수행한다.
   예: make ARCH=arm64 INSTALL_MOD_PATH=<rootfs_path> modules_install

4. rootfs에 다음 경로가 생성되는지 확인한다.
   /lib/modules/6.18.13-gc21449208550/

5. 해당 경로 아래에 최소한 다음 모듈들이 존재하는지 확인한다.
   kernel/drivers/remoteproc/ti_k3_r5_remoteproc.ko
   kernel/drivers/remoteproc/ti_k3_m4_remoteproc.ko
   kernel/drivers/rpmsg/rpmsg_char.ko
   kernel/drivers/rpmsg/rpmsg_ctrl.ko

6. 보드에서 재부팅 후 확인한다.
   uname -r
   ls /lib/modules/$(uname -r)
   modprobe ti_k3_r5_remoteproc
   modprobe rpmsg_char
   modprobe rpmsg_ctrl
   ls /sys/class/remoteproc/
   dmesg | grep -i remoteproc
```

## 대안

### 대안 1: modules에 맞는 kernel Image로 부팅

기존 rootfs의 modules를 그대로 사용하려면 부팅되는 kernel Image의 `uname -r`도 다음과 같아야 한다.

```text
6.18.13-ti-00778-gc21449208550-dirty
```

즉 rootfs modules와 같은 빌드에서 나온 kernel Image로 부팅해야 한다.

### 대안 2: R5F/RPMsg 드라이버를 built-in으로 빌드

초기 bring-up 편의를 위해 다음 드라이버를 built-in으로 넣을 수 있다.

```text
CONFIG_TI_K3_R5_REMOTEPROC=y
CONFIG_TI_K3_M4_REMOTEPROC=y
CONFIG_RPMSG_CHAR=y
CONFIG_RPMSG_CTRL=y
```

단, 이는 R5F 관련 모듈 의존성만 줄이는 방법이다. BSP 관리 원칙상 kernel Image와 `/lib/modules/$(uname -r)`는 여전히 같은 빌드 산출물로 맞추는 것이 정석이다.

## Open Question

1. 현재 로컬 빌드 Repo의 kernelrelease 값은 정확히 무엇인가?
2. rootfs에 modules_install을 자동으로 반영하는 스크립트가 있는가?
3. 현재 boot image 교체 절차가 `/boot/Image`만 복사하는 구조인지, `/lib/modules`까지 같이 반영하는 구조인지 확인이 필요하다.
4. R5F를 실제 제품 기능으로 사용할 계획인지, 아니면 현재는 검증 항목으로만 둘 것인지 결정해야 한다.

## Board Note

TMDS64EVM과 SK-AM64B는 같은 AM64x 계열 SoC를 사용할 수 있지만, board DTB와 rootfs 구성, boot image 교체 방식은 다를 수 있다. R5F remoteproc 검증은 보드별 boot image, DTB, rootfs modules 세트가 일치하는 상태에서 진행해야 한다.

## Artifact

권장 저장 위치:

```text
docs/bringup/am64x_r5f_remoteproc_module_mismatch_summary.md
```
