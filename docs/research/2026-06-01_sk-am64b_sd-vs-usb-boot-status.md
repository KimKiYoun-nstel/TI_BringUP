# 2026-06-01 SK-AM64B SD vs USB Boot Status

## 목적

이 문서는 현재 SK-AM64B에서 확인된 다음 두 부트 경로를 한 곳에 정리한다.

1. SD baseline boot
2. USB-only autoboot (SD absent)

또한 다음을 함께 정리한다.

- Boot ROM / SPL / U-Boot / kernel / DTB / rootfs 단계별 source
- `env` 방식인지 `extlinux.conf` 방식인지
- USB 성공을 위해 실제로 수정한 U-Boot / media / kernel 관련 항목
- TI SDK generic 문서와 SK board 현실 사이의 차이
- 아직 남아 있는 open question

---

## 1. 현재 SD baseline boot

### 1.1 부트 구조

현재 공식 baseline은 다음과 같다.

```text
SD card boot assets + 현재 U-Boot env + SD rootfs /boot kernel/DTB load
```

### 1.2 단계별 source

```text
Boot ROM / SPL / U-Boot proper : SD FAT boot partition
Kernel                          : SD rootfs /boot/Image
DTB                             : SD rootfs /boot/dtb/ti/k3-am642-sk.dtb
Rootfs                          : SD ext4 (PARTUUID=076c4a2a-02)
```

### 1.3 U-Boot 부트 방식

핵심 env는 다음이다.

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
boot=mmc
bootpart=1:2
bootdir=/boot
bootenvfile=uEnv.txt
fdtfile=ti/k3-am642-sk.dtb
get_kern_mmc=load mmc ${bootpart} ${loadaddr} ${bootdir}/${name_kern}; run load_initramfs_mmc
get_fdt_mmc=load mmc ${bootpart} ${fdtaddr} ${bootdir}/dtb/${fdtfile}
run_kern=booti ${loadaddr} ${rd_spec} ${fdtaddr}
```

즉 baseline의 본질은:

```text
U-Boot env 기반 SD boot
```

이다. extlinux는 baseline replacement가 아니었다.

---

## 2. USB-only autoboot 성공 상태

### 2.1 성공이 입증된 조건

성공은 다음 조건에서만 입증되었다.

```text
SD card absent
USB media connected
Cold reboot / power-on after USB boot media preparation
```

### 2.2 최종 USB media layout

#### `/dev/sda1` - `ROMBOOT` FAT32

```text
tiboot3.bin
tispl.bin
u-boot.img
Image
k3-am642-sk.dtb
extlinux/extlinux.conf
```

이 파티션이 현재 USB-only autoboot의 핵심이다.

#### `/dev/sda2` - `BOOT` FAT32

```text
existing rehearsal assets
Image
Image.usbtest
boot/dtb/ti/k3-am642-sk-usb-root.dtb
...
```

이 파티션은 여전히 rehearsal / manual load 자산을 보관하지만,
최종 USB-only autoboot 자체는 `sda1` 기준으로 증명되었다.

#### `/dev/sda3` - `usb-rootfs` ext4

```text
Root filesystem
PARTUUID=2bcf5ad2-03
```

### 2.3 단계별 source

성공한 USB-only autoboot의 단계별 source는 다음과 같다.

```text
Boot ROM / tiboot3.bin          : USB sda1
tispl.bin / u-boot.img          : USB storage continuation
U-Boot proper Linux autoboot    : USB sda1 /extlinux/extlinux.conf
Kernel                          : USB sda1 /Image
DTB                             : USB sda1 /k3-am642-sk.dtb
Rootfs                          : USB sda3 (PARTUUID=2bcf5ad2-03)
```

### 2.4 U-Boot 부트 방식

성공한 USB-only autoboot는 `env`의 수동 load path가 아니라,
다음 흐름으로 성립했다.

```text
bootcmd
  -> mmc path 실패 (SD absent)
  -> bootflow scan -lb
  -> usb_mass_storage.lun0.bootdev 발견
  -> /extlinux/extlinux.conf 발견
  -> extlinux entry로 /Image + /k3-am642-sk.dtb load
  -> kernel boot
```

즉 이 성공 경로의 본질은:

```text
USB bootflow + extlinux autoboot
```

이다.

---

## 3. USB 성공을 위해 실제로 수정한 항목

### 3.1 USB media 재구성

가장 큰 변화는 `sda1` 을 self-contained boot partition으로 만든 것이다.

초기에는 USB bootloader trio가 `sda2` 쪽 rehearsal FAT에만 있거나,
kernel/DTB와 bootloader trio가 다른 파티션에 나뉘어 있었다.

최종적으로는 `sda1` root에 다음을 함께 둠으로써,
Boot ROM부터 U-Boot extlinux까지 한 파티션에서 이어지게 만들었다.

```text
tiboot3.bin
tispl.bin
u-boot.img
Image
k3-am642-sk.dtb
extlinux/extlinux.conf
```

이 변경은 실질적으로 필수였다.

### 3.2 U-Boot SPL DTS override

다음 SPL USB override를 workspace에 적용했다.

```dts
&usbss0 {
	bootph-all;
	ti,vbus-divider;
	ti,usb2-only;
};

&usb0 {
	bootph-all;
	dr_mode = "host";
	maximum-speed = "high-speed";
	/delete-property/ phys;
	/delete-property/ phy-names;
};
```

의도:

- SK board의 USB3 PHY dependency 축소
- SPL에서 단순한 USB2/high-speed host continuation 시도

### 3.3 U-Boot Cadence core driver patch

초기 SPL failure는 다음과 같았다.

```text
Trying to boot from USB
cdns-usb3-host usb@f400000: Couldn't get USB3 PHY: -19
Bus usb@f400000: Port not available.
No USB controllers found
0 Storage Device(s) found
SPL: Unsupported Boot Device!
```

이 문제를 완화하기 위해 `drivers/usb/cdns3/core.c` 에서
`usb2-only` wrapper 상황에서는 USB3 PHY path를 skip 하도록 driver-side patch를 적용했다.

핵심 의도:

```text
usb2-only이면 generic USB3 PHY get/init/power_on 을 수행하지 않음
```

이 수정은 최종 성공과 인과관계가 높다고 판단되지만,
성공 직전 단계에서 media restructuring도 함께 수행되었기 때문에,
driver patch 단독 효과를 분리 입증했다고까지는 말하지 않는다.

### 3.4 kernel / DTB USB rehearsal 자산

USB rootfs mount 자체를 위해 kernel/DTB rehearsal도 별도로 진행했다.

예:

- `Image.usbtest`
- `k3-am642-sk-usb-root.dtb`
- built-in USB storage stack config
- N17 initramfs diagnostics

그러나 최종 USB-only autoboot 성공에 직접 쓰인 경로는
`sda1`의 `/Image` 와 `/k3-am642-sk.dtb` 기준이었다.

즉 USB-only autoboot 관점에서는 kernel rehearsal 자산보다,
**`sda1` self-contained extlinux 구조**가 더 핵심적이었다.

### 3.5 TI SDK prebuilt 대비 bootloader 차이

현재 USB 성공에 사용한 bootloader trio는 TI SDK prebuilt와 **동일하지 않다**.

비교 기준 hash:

```text
[current workspace-built USB trio]
tiboot3.bin  c5441d7281ceb45a748d4fc3b394c6ef
tispl.bin    87130bb2af4dd8bae51d27f1a37682a0
u-boot.img   45ec3ec221b648a42a9e306e8a2b6be7

[TI SDK prebuilt-images/am64xx-evm]
tiboot3.bin  c4ebf3aafff9ffb509536cac8963d903
tispl.bin    41b296c17fd213a39b2bde9a1f65ac1d
u-boot.img   4cd912e5e7acaad504696ff067a76ea6
```

즉 bootloader 기준으로는 다음이 달라졌다.

1. source가 prebuilt가 아니라 local workspace rebuild 결과다.
2. SK SPL DTS USB override가 포함되었다.
3. Cadence core의 `usb2-only` aware driver patch가 포함되었다.
4. watchdog command 사용이 가능한 A53 U-Boot build option도 같이 유지되었다.

따라서 현재 성공 경로는 **TI SDK prebuilt 그대로가 아니라, repo-managed U-Boot rebuild 산출물** 기준이다.

### 3.6 TI SDK prebuilt 대비 kernel/DTB 차이

USB-only autoboot 성공에서 실제 사용된 kernel/DTB는 다음 hash를 가진다.

```text
[current USB-success path]
Image               bb5ee4a03639adc68a30c73c376f6fbb
k3-am642-sk.dtb     c852f95738d8b89a3cdd0d6c5b9c4268

[baseline SD artifact]
Image               0438322852503dc5fef45646917f5c05
k3-am642-sk.dtb     313a843fecc8075253c237c5a4813ca4
```

또 repo 관점에서 USB rootfs experimentation을 위해 별도 자산도 존재했다.

```text
Image.usbtest
k3-am642-sk-usb-root.dtb
am64x-usb-boot.config
am64x-usb-root-diag-initramfs.config
```

다만 최종 USB-only autoboot는 다음처럼 정리해야 한다.

```text
최종 성공 경로에서 직접 사용된 것은
sda1에 놓인 /Image 와 /k3-am642-sk.dtb 이다.

Image.usbtest / k3-am642-sk-usb-root.dtb 는
중간 실험과 검증 자산으로서 중요하지만,
최종 autoboot의 direct input은 아니었다.
```

즉 kernel/DTB 기준 차이는 두 층이다.

1. USB 실험용 빌드/자산 계층
2. 최종 autoboot에 실제 배치된 sda1 self-contained 계층

---

## 4. TI SDK generic 문서와 SK 실보드 현실의 차이

### 4.1 generic AM64x 문서

TI Processor SDK U-Boot 문서는 generic AM64x 기준으로 다음을 설명한다.

- FAT32 boot partition 생성
- `tiboot3.bin`, `tispl.bin`, `u-boot.img` 배치
- USB host boot mode 설정
- USB storage에서 U-Boot prompt까지 부팅 가능

즉 기능 자체는 generic AM64x 문서상 존재한다.

### 4.2 SK board 관련 공개 정보

TI E2E thread에서는 다음이 확인된다.

```text
USB host boot feature has been validated on the GPEVM.
... the function wasn't tested on the AM64x SK EVM.
```

즉 generic AM64x 문서와 달리,
SK board에서 same path가 공식적으로 강하게 검증되었다고 보긴 어렵다.

### 4.3 이번 실보드 결론

그럼에도 불구하고,
현재 우리 실보드 기준으로는 최소한 다음은 입증되었다.

```text
SK-AM64B + SD absent 조건에서
USB ROM boot -> USB SPL/U-Boot -> USB extlinux -> USB rootfs
end-to-end autoboot 성공
```

즉 지금 상태는:

```text
TI generic docs: supports the path in principle
SK public validation: historically ambiguous/under-tested
our board: success demonstrated under SD-absent condition
```

으로 정리하는 것이 가장 정확하다.

---

## 5. SD inserted vs SD absent 차이

### 입증 완료

```text
SD absent -> USB-only autoboot 성공
```

### 아직 미입증

```text
SD inserted 상태에서 USB가 여전히 우선되는지 여부
```

그 이유는 기본 U-Boot env가 여전히:

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
boot_targets=mmc1 mmc0 usb pxe dhcp
```

즉 `mmc` 경로가 먼저 시도되기 때문이다.

따라서 SD가 꽂혀 있으면,

- SD extlinux
- SD env path
- SD rootfs `/boot`

가 먼저 선택될 수 있다.

현재 안전한 표현은 다음이다.

```text
입증 완료: SD absent USB-only autoboot
미입증: SD inserted 상태에서의 USB 우선성
```

### 왜 SD inserted 상태에서 USB가 안 되는 것이 자연스러운가

사용자가 처음부터 지적한 것처럼,
현재 구조는 SD용 baseline boot policy와 USB-only boot policy가 완전히 분리된 상태가 아니다.

기본 U-Boot env는 여전히:

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
boot_targets=mmc1 mmc0 usb pxe dhcp
```

이므로 SD card가 삽입되어 있으면 다음 순서가 자연스럽다.

1. SD env / mmc boot path 시도
2. SD rootfs /boot 기준 kernel/DTB 시도
3. 그 이후에야 USB bootflow fallback

따라서 현재 상태에서 **SD inserted인데도 USB가 그대로 우선 부팅된다면 오히려 더 이상한 결과** 다.

즉 사용자가 요구한 “SD용 부트로더와 USB용 부트로더를 구분”한다는 말을
현재 구조에 맞게 다시 풀면 다음과 같다.

```text
동일한 source tree에서 빌드한 bootloader binary라도
어떤 media layout + 어떤 extlinux/env policy + 어떤 boot mode switch로 쓰느냐가
실질적인 구분이다.
```

현재 성공 경로는 완전히 별개의 permanent product boot policy라기보다,
**USB-only media layout + SD absent 조건 + USB extlinux bootflow** 조합이다.

즉 지금의 안전한 해석은:

```text
SD inserted에서 USB가 안 되는 것은 자연스럽다.
SD absent에서 USB-only autoboot가 되는 것이 현재 입증된 성공 조건이다.
```

---

## 6. 현재 시점의 가장 정확한 한 줄 정리

```text
현재 SK-AM64B는 SD card가 제거된 상태에서는,
USB sda1의 bootloader trio + extlinux + kernel/DTB와
USB sda3 rootfs를 사용해 end-to-end USB-only autoboot가 가능하다.

단, SD card가 삽입된 상태에서 USB가 여전히 우선되는지는 아직 별도 검증이 필요하다.
```

---

## 7. USB-specific boot policy build 추가 결과

위 문서는 원래 **SD absent에서 확인된 USB-only autoboot**를 기준으로 작성되었다.

이후 사용자의 요구에 따라,
SD inserted 상태에서도 fallback이 아니라 **명시적 USB-first policy** 로 부팅되도록
U-Boot policy를 별도로 분리하는 실험을 추가로 진행했다.

### 7.1 왜 별도 policy가 필요했는가

사용자 지적의 핵심은 정확했다.

```text
기본 bootcmd / boot_targets 가 mmc -> usb 순서라면,
SD inserted 상태에서 USB가 자동 부팅되는 것이 오히려 이상하다.
```

실제로 TI baseline U-Boot env는 다음과 같다.

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
boot_targets=mmc1 mmc0 usb pxe dhcp
```

즉 baseline policy에서는 SD inserted 시 mmc-first가 자연스럽다.

### 7.2 적용한 분리 방식

U-Boot board late init에서 USB-capable build에 대해 다음 policy를 강제했다.

```text
boot = usb
boot_targets = usb
bootcmd = bootflow scan -lb
```

의미:

```text
이 build는 baseline SD-first U-Boot가 아니라,
USB-only boot policy를 내장한 별도 U-Boot build다.
```

### 7.3 이 policy-separated build의 trio hash

```text
tiboot3.bin  6587b0dcc3723ef6f7a1fcf1cc90f1d4
tispl.bin    13a2d0b22405ee687bcc0c19430b7586
u-boot.img   684dabe510a02b8d198c657f9c306c60
```

이 trio는 `/dev/sda1` 과 `/dev/sda2` 에 다시 반영했다.

### 7.4 SD inserted 상태에서의 관찰 결과

최신 비교 로그에서는, SD inserted 상태에서도 다음처럼 USB-only path가 관찰되었다.

```text
Trying to boot from USB
Trying to boot from USB
Scanning bootdev 'usb_mass_storage.lun0.bootdev':
** Booting bootflow ... with extlinux
Retrieving file: /Image
Retrieving file: /k3-am642-sk.dtb
Kernel command line: ... root=PARTUUID=2bcf5ad2-03 ...
VFS: Mounted root (ext4 filesystem) on device 8:3.
```

즉 이 결과는 다음을 의미한다.

```text
TI baseline policy:
  SD inserted -> mmc-first가 자연스럽다.

current USB-specific policy build:
  SD inserted 상태에서도 USB-only path로 강제 가능하다.
```

### 7.5 최종 해석

따라서 지금은 다음처럼 구분해서 기록해야 한다.

1. **TI baseline / SD-first build**
   - SD inserted면 SD가 먼저 선택되는 것이 정상

2. **USB-specific separated build**
   - U-Boot policy 자체를 USB-first로 바꿔,
     SD inserted 상태에서도 USB-only boot를 강제하도록 만든 것

즉 현재 성공은 단순히 media layout만의 결과가 아니라,
최종적으로는 **별도 USB-first boot policy를 가진 U-Boot build** 까지 포함한 결과다.
