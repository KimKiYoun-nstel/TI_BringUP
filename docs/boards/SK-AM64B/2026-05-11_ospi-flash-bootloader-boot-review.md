# SK-AM64B OSPI Flash Bootloader Bring-up Note

Date: 2026-05-11  
Board: TI SK-AM64B / AM64B-SKEVM Rev A  
SoC: AM64x SR2.0 HS-FS  
Context: SD boot 기반에서 온보드 OSPI NOR Flash에 부트로더 이미지를 기록하고, 이후 boot switch를 변경하여 OSPI Flash 기반 U-Boot 부팅을 검증했다.

---

## Summary

지난주 금요일 작업에서 SD 카드로 Linux를 부팅한 상태에서 온보드 OSPI NOR Flash의 MTD partition을 확인하고, SD 카드 boot partition에 있던 부트로더 이미지 3종을 OSPI Flash에 기록했다.

오늘 작업에서는 boot switch를 xSPI/SFDP(OSPI) 부팅 설정으로 변경한 뒤, SD 카드를 제거한 상태에서도 U-Boot까지 정상 진입하는 것을 UART 로그로 확인했다.

현재 확인된 부팅 구조는 다음과 같다.

```text
Boot ROM
  -> xSPI/SFDP boot mode
  -> onboard OSPI NOR Flash에서 tiboot3.bin 로드
  -> onboard OSPI NOR Flash에서 tispl.bin 로드
  -> onboard OSPI NOR Flash에서 u-boot.img 로드
  -> U-Boot 실행
  -> 이후 Linux Kernel / DTB / RootFS는 기본 설정상 SD 카드에서 탐색
```

즉, 현재 상태는 **OSPI Flash에서 U-Boot까지 부팅 성공**, **Linux OS 본체는 여전히 SD 카드 의존** 상태다.

---

## Knowledge

### 1. SK-AM64B의 온보드 Flash는 Linux에서 MTD 장치로 노출된다

SD 카드로 Linux 부팅 후 `/proc/mtd`를 확인한 결과, 온보드 OSPI NOR Flash는 다음과 같은 MTD partition으로 인식되었다.

```text
dev:    size   erasesize  name
mtd0: 00100000 00040000 "ospi.tiboot3"
mtd1: 00200000 00040000 "ospi.tispl"
mtd2: 00400000 00040000 "ospi.u-boot"
mtd3: 00040000 00040000 "ospi.env"
mtd4: 00040000 00040000 "ospi.env.backup"
mtd5: 037c0000 00040000 "ospi.rootfs"
mtd6: 00040000 00040000 "ospi.phypattern"
```

해석:

```text
0x00000000 ~ 0x00100000 : ospi.tiboot3
0x00100000 ~ 0x00300000 : ospi.tispl
0x00300000 ~ 0x00700000 : ospi.u-boot
0x00700000 ~ 0x00740000 : ospi.env
0x00740000 ~ 0x00780000 : ospi.env.backup
0x00800000 ~ 0x03fc0000 : ospi.rootfs
0x03fc0000 ~ 0x04000000 : ospi.phypattern
```

### 2. OSPI Flash에 기록한 부트로더 이미지

SD 카드 boot partition은 다음 위치에 mount되어 있었다.

```text
/run/media/boot-mmcblk1p1
```

확인된 주요 파일:

```text
tiboot3.bin  약 506 KiB
tispl.bin    약 1.1 MiB
u-boot.img   약 1.6 MiB
Image        약 21 MiB
uEnv.txt
```

OSPI Flash 기록 대상:

```text
/run/media/boot-mmcblk1p1/tiboot3.bin -> /dev/mtd/by-name/ospi.tiboot3
/run/media/boot-mmcblk1p1/tispl.bin   -> /dev/mtd/by-name/ospi.tispl
/run/media/boot-mmcblk1p1/u-boot.img  -> /dev/mtd/by-name/ospi.u-boot
```

사용한 write 방식:

```sh
flashcp -v /run/media/boot-mmcblk1p1/tiboot3.bin /dev/mtd/by-name/ospi.tiboot3
flashcp -v /run/media/boot-mmcblk1p1/tispl.bin   /dev/mtd/by-name/ospi.tispl
flashcp -v /run/media/boot-mmcblk1p1/u-boot.img  /dev/mtd/by-name/ospi.u-boot
sync
```

### 3. OSPI write 검증

OSPI MTD에서 readback 후 원본과 `cmp`로 비교했다.

```sh
mkdir -p /root/ospi-verify

dd if=/dev/mtd/by-name/ospi.tiboot3 of=/root/ospi-verify/tiboot3.readback.bin bs=1M
dd if=/dev/mtd/by-name/ospi.tispl   of=/root/ospi-verify/tispl.readback.bin   bs=1M
dd if=/dev/mtd/by-name/ospi.u-boot  of=/root/ospi-verify/u-boot.readback.bin  bs=1M

cmp -n $(stat -c%s /run/media/boot-mmcblk1p1/tiboot3.bin) \
  /run/media/boot-mmcblk1p1/tiboot3.bin \
  /root/ospi-verify/tiboot3.readback.bin

cmp -n $(stat -c%s /run/media/boot-mmcblk1p1/tispl.bin) \
  /run/media/boot-mmcblk1p1/tispl.bin \
  /root/ospi-verify/tispl.readback.bin

cmp -n $(stat -c%s /run/media/boot-mmcblk1p1/u-boot.img) \
  /run/media/boot-mmcblk1p1/u-boot.img \
  /root/ospi-verify/u-boot.readback.bin
```

`cmp` 명령은 차이가 없을 때 아무 출력 없이 종료한다. 세 이미지 모두 출력 없이 종료되어, OSPI Flash write/readback이 정상으로 판단되었다.

### 4. Boot switch 설정

User Guide의 generic boot mode table에서 `OSPI` row와 `xSPI` row가 별도로 존재하여 혼란이 있었다.

실제로 SK-AM64B 온보드 OSPI NOR Flash boot에 성공한 switch 설정은 다음이다.

```text
SW2 = OFF OFF OFF OFF OFF OFF ON  OFF
SW3 = OFF ON  ON  ON  OFF OFF ON  ON
```

비트 표기:

```text
SW2 = 00000010
SW3 = 01110011
```

주의:

- 이 설정은 보드 실사용 문서에서 `OSPI BOOT MODE` 또는 `xSPI/SFDP (OSPI)`로 안내되는 설정이다.
- 물리 저장장치는 온보드 OSPI NOR Flash이다.
- Boot ROM mode 명칭/encoding 관점에서는 xSPI/SFDP 계열로 해석된다.
- 따라서 기록 시에는 “onboard OSPI NOR Flash boot via xSPI/SFDP boot mode”로 표현하는 것이 가장 정확하다.

### 5. SD 카드 제거 후 부팅 로그 해석

SD 카드를 제거하고 xSPI/SFDP(OSPI) boot switch 상태로 전원을 인가했을 때, UART 로그에서 다음이 확인되었다.

```text
U-Boot SPL 2026.01-ti-g2549829cc194 ...
Trying to boot from SPI
Authentication passed
...
U-Boot 2026.01-ti-g2549829cc194 ...
SoC:   AM64X SR2.0 HS-FS
Model: Texas Instruments AM642 SK
Board: AM64B-SKEVM rev A
```

이 로그의 의미:

```text
Boot ROM / SPL 단계에서 SPI 계열 Flash에서 이미지를 읽음
OSPI Flash에 기록된 tiboot3/tispl/u-boot 체인이 정상 동작함
SD 카드 없이도 U-Boot까지 진입 가능함
```

이후 Linux 부팅 시도는 실패했다.

주요 로그:

```text
MMC: no card present
** Bad device specification mmc 1 **
Couldn't find partition mmc 1:2
Can't set block device
...
libfdt fdt_check_header(): FDT_ERR_BADMAGIC
No FDT memory address configured.
Aborting!
Bad Linux ARM64 Image magic!
```

이 의미:

```text
U-Boot는 기본적으로 mmc 1:2, 즉 SD 카드 rootfs partition에서 Kernel/DTB/rootfs를 찾는다.
SD 카드가 제거되어 mmc 1이 없으므로 Kernel/DTB를 로드하지 못했다.
Image/DTB가 메모리에 정상 로드되지 않은 상태에서 boot 시도가 이어져 FDT_ERR_BADMAGIC / Bad Linux Image magic이 발생했다.
```

이후 U-Boot는 자동 bootflow scan을 수행했다.

```text
Scanning for bootflows in all bootdevs
...
USB XHCI 1.00
Bus usb@f400000: 1 USB Device(s) found
...
BOOTP broadcast 1
BOOTP broadcast 2
...
```

의미:

```text
SD/MMC 부팅 실패 후 U-Boot standard bootflow가 USB, PXE, DHCP 등을 순서대로 탐색한다.
USB 장치 탐색과 Ethernet BOOTP/DHCP 시도가 수행되었지만, 부팅 가능한 USB storage 또는 네트워크 boot 서버가 준비되지 않아 Linux 부팅으로 이어지지 않았다.
```

---

## Decision

### 1. 현재 SK-AM64B의 bootloader source는 OSPI Flash로 전환 가능함

현재 검증된 구조:

```text
Bootloader source: onboard OSPI NOR Flash
ROM boot mode: xSPI/SFDP
Linux Kernel/DTB/RootFS source: SD card
```

### 2. SD 카드 없이 U-Boot까지는 가능함

SD 카드를 제거해도 OSPI Flash에서 `tiboot3.bin`, `tispl.bin`, `u-boot.img`가 로드되어 U-Boot prompt까지 진입 가능한 것으로 확인되었다.

### 3. SD 카드 없이 Linux까지 부팅하려면 추가 작업이 필요함

현재 U-Boot environment는 Kernel/DTB/rootfs를 기본적으로 SD 카드에서 찾도록 되어 있다.

따라서 SD 없이 Linux까지 부팅하려면 다음 중 하나가 필요하다.

```text
1. USB storage에 Kernel/DTB/rootfs 구성 후 U-Boot에서 USB boot
2. Ethernet TFTP/NFS 기반 boot 구성
3. OSPI Flash에 Kernel/DTB + 작은 initramfs/rootfs 구성
4. 커스텀 보드에서는 eMMC 등 별도 저장장치에 Kernel/DTB/rootfs 저장
```

SK-AM64B 기본 보드에는 eMMC가 실장되어 있지 않으므로, 현재 EVM에서는 eMMC boot/rootfs 실험은 대상이 아니다.

---

## Assumption

- 현재 사용 중인 SD card image의 `tiboot3.bin`, `tispl.bin`, `u-boot.img`는 SK-AM64B Rev A / AM64x SR2.0 HS-FS 보드에 맞는 이미지로 판단한다.
- `Trying to boot from SPI` 로그는 SPI 계열 Flash, 즉 이번 실험에서는 onboard OSPI NOR Flash에서 bootloader chain을 읽었다는 의미로 판단한다.
- 현재 Linux Kernel/DTB/rootfs는 SD card의 rootfs partition, 즉 `mmcblk1p2` 기반 구성을 사용하고 있다.

---

## Open Question

### 1. User Guide의 generic `OSPI` boot row와 실제 SK-AM64B boot switch 표기의 차이

User Guide의 generic boot mode table에는 `OSPI`와 `xSPI`가 별도 row로 존재한다.

그러나 SK-AM64B 온보드 OSPI NOR Flash boot에 성공한 설정은 보드 실사용 문서에서 `OSPI BOOT MODE` 또는 `xSPI/SFDP (OSPI)`로 안내되는 `SW2=00000010`, `SW3=01110011` 설정이다.

추후 확인할 항목:

```text
- AM64x TRM의 OSPI Bootloader Operation
- AM64x TRM의 xSPI Bootloader Operation
- BOOTMODE[9:7] Speed / Iclk / Csel 정의
- S28HS512T Flash의 default protocol 및 SFDP/xSPI compatibility
- User Guide generic boot table과 SK-AM64B board-specific boot mode 문서 간 표현 차이
```

### 2. SD-less Linux boot 경로 결정

현재 U-Boot까지는 OSPI Flash로 독립 부팅 가능하지만, Linux OS는 SD에 의존한다.

다음 중 어떤 방식을 우선 실험할지 결정이 필요하다.

```text
- USB Mass Storage 기반 Kernel/DTB/rootfs boot
- Ethernet TFTP/NFS boot
- OSPI Flash + initramfs 기반 최소 Linux boot
```

---

## Action Item

### 1. 현재 상태 보존

현재 OSPI Flash에는 부트로더 3종이 정상 기록되어 있으므로, 다음 실험 전 현재 상태를 repo에 문서화한다.

추천 파일 경로:

```text
docs/bringup/sk-am64b/2026-05-11-ospi-bootloader-flash-and-boot-review.md
```

### 2. U-Boot environment 저장 여부 확인

현재 로그에는 다음이 보인다.

```text
Loading Environment from nowhere... OK
```

이는 U-Boot environment가 persistent storage에서 로드되지 않고 기본 environment를 사용하는 상태일 수 있다.

추후 확인:

```sh
printenv
saveenv
```

단, `saveenv` 사용 전 `CONFIG_ENV_IS_IN_*` 및 실제 env storage 위치를 확인해야 한다. 현재 OSPI에 `ospi.env`, `ospi.env.backup` partition은 존재하지만, U-Boot 로그상 실제 environment load는 `nowhere`로 표시되었다.

### 3. USB storage boot 실험 준비

현재 U-Boot environment에는 USB boot 관련 설정이 존재한다.

관련 변수:

```text
usbboot=setenv boot usb; setenv bootpart 0:2; usb start; run init_usb; run get_kern_usb; run get_fdt_usb; run run_kern;
get_kern_usb=load usb ${bootpart} ${loadaddr} ${bootdir}/${name_kern}
get_fdt_usb=load usb ${bootpart} ${fdtaddr} ${bootdir}/${name_fdt}
boot_targets=mmc1 mmc0 usb pxe dhcp
```

주의할 점:

```text
MMC DTB path: /boot/dtb/ti/k3-am642-sk.dtb
USB DTB path: /boot/ti/k3-am642-sk.dtb
```

USB storage boot 실험 시 USB storage의 파일 경로를 현재 env와 맞추거나, env를 수정해서 경로를 맞춰야 한다.

### 4. Ethernet boot / NFS boot 검토

현재 bootflow scan에서 DHCP/BOOTP가 자동 시도되는 것을 확인했다.

추후 Ethernet boot 실험 시 필요한 항목:

```text
- Ethernet cable 연결
- DHCP server
- TFTP server
- Kernel Image / DTB 제공 경로
- NFS rootfs 또는 initramfs 구성
- U-Boot env: serverip, ipaddr, bootfile, rootpath, bootargs
```

---

## Board Note

### SK-AM64B 현재 확인된 boot 상태

```text
Board: AM64B-SKEVM rev A
SoC: AM64X SR2.0 HS-FS
U-Boot: 2026.01-ti-g2549829cc194
SYSFW ABI: 4.0
OP-TEE: 4.9.0
```

### OSPI Flash bootloader chain

```text
tiboot3.bin  -> ospi.tiboot3
              offset 0x00000000, size 0x00100000

tispl.bin    -> ospi.tispl
              offset 0x00100000, size 0x00200000

u-boot.img   -> ospi.u-boot
              offset 0x00300000, size 0x00400000
```

### Verified UART log markers

OSPI Flash bootloader chain 성공을 의미하는 주요 로그:

```text
Trying to boot from SPI
Authentication passed
U-Boot 2026.01-ti-g2549829cc194
Board: AM64B-SKEVM rev A
```

SD 카드 제거 상태에서 Linux 부팅 실패를 의미하는 주요 로그:

```text
MMC: no card present
Couldn't find partition mmc 1:2
Bad Linux ARM64 Image magic!
```

U-Boot bootflow fallback 동작:

```text
Scanning for bootflows in all bootdevs
USB XHCI 1.00
BOOTP broadcast
```

---

## Artifact

이 문서는 독립적인 저장소 문서로 커밋하는 것을 전제로 작성했다.

권장 저장소 경로:

```text
docs/bringup/sk-am64b/2026-05-11-ospi-bootloader-flash-and-boot-review.md
```

권장 커밋 메시지:

```text
docs: SK-AM64B OSPI 부트로더 기록 및 부팅 검증 정리
```
