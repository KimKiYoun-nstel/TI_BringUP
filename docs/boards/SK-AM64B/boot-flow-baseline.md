# SK-AM64B 부트 플로우 BASE

## 요약

현재 SK-AM64B의 baseline은 다음 실사용 부트 경로를 기준으로 한다.

```text
SD card boot assets + 현재 U-Boot environment + rootfs /boot kernel/DTB load
```

앞으로의 deploy 및 파이프라인 변경은 모두 이 상태를 기준으로 관리한다.

## 확인된 보드 정체성

부트 로그와 현재 실보드 상태에서 다음을 확인했다.

```text
Model: Texas Instruments AM642 SK
Board: AM64B-SKEVM rev A
compatible: ti,am642-sk / ti,am642
```

## 확인된 부트 인자

현재 부트 인자는 다음과 같다.

```text
console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait
```

이 값은 현재 baseline의 다음 기준을 정한다.

- serial console device
- root device 해석 방식
- rootfs type 기대값

## 확인된 U-Boot BASE 정책

핵심 U-Boot environment 값은 다음과 같다.

```text
boot=mmc
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
bootpart=1:2
bootdir=/boot
bootenvfile=uEnv.txt
fdtfile=ti/k3-am642-sk.dtb
get_kern_mmc=load mmc ${bootpart} ${loadaddr} ${bootdir}/${name_kern}; run load_initramfs_mmc
get_fdt_mmc=load mmc ${bootpart} ${fdtaddr} ${bootdir}/dtb/${fdtfile}
run_kern=booti ${loadaddr} ${rd_spec} ${fdtaddr}
```

## 확인된 Kernel / DTB 위치

현재 baseline에서 로드되는 대상은 다음과 같다.

```text
Kernel: /boot/Image
DTB:    /boot/dtb/ti/k3-am642-sk.dtb
```

이 파일들은 다음 rootfs partition 기준으로 로드된다.

```text
mmc 1:2
```

## 현재 FAT boot partition의 역할

현재 FAT boot partition에는 다음과 같은 bootloader 관련 자산이 있다.

```text
tiboot3.bin
tispl.bin
u-boot.img
uEnv.txt
EFI/BOOT/grub.cfg
```

하지만 현재 검증된 Linux 부트 경로는 여전히 U-Boot environment가 rootfs 경로의 `/boot/Image`와 `/boot/dtb/ti/k3-am642-sk.dtb`를 읽는 방식이다.

## BASE DTB 결정

현재 SK-AM64B 파이프라인 작업의 baseline DTB는 다음이다.

```text
k3-am642-sk.dtb
```

근거:

- board model 및 compatible과 일치한다.
- `fdtfile=ti/k3-am642-sk.dtb`로 명시되어 있다.
- 현재 rootfs boot tree에 존재한다.
- 기존 bring-up 문서에서 running device tree 비교 기준으로 이미 사용되었다.

## 중요한 운용상 주의사항

U-Boot는 Linux에 넘기기 전에 최종 FDT를 수정할 수 있다.

따라서:

- 새 DTB를 배포하는 것은 baseline 입력을 바꾸는 일이다.
- runtime Linux-visible tree는 필요 시 별도로 다시 검증해야 한다.

## 파이프라인 영향

이 baseline은 Option A deploy 작업에서 다음을 의미한다.

- bootloader deploy는 FAT boot partition을 대상으로 한다.
- kernel deploy는 `/boot/Image`를 대상으로 한다.
- DTB deploy는 `/boot/dtb/ti/k3-am642-sk.dtb`를 대상으로 한다.
- DTB-only loop는 명시적 요구가 없는 한 kernel Image를 건드리지 않는다.
