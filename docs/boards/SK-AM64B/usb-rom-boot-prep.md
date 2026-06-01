# SK-AM64B USB ROM Boot 준비 메모

## 목적

이 문서는 기존의

```text
SD card bootloader + USB kernel/DTB/rootfs
```

실험에서 방향을 바꿔,

```text
Boot ROM primary boot device 자체를 USB로 선택
```

하는 실험을 준비하기 위한 사전 점검과 준비 절차를 정리한다.

## 현재 시점의 핵심 판단

### 1. 지금까지 성공한 것은 "U-Boot 이후 USB storage 접근"이다

현재까지 repo와 live board에서 확인된 것은 다음이다.

- U-Boot가 USB storage를 인식할 수 있다.
- U-Boot가 USB에서 `Image`, `DTB`를 load 할 수 있다.
- Linux가 나중에는 같은 USB stick을 `usb-storage -> scsi -> sda` 로 인식할 수 있다.

즉 지금까지 입증된 것은 **late U-Boot / Linux host-storage path** 이다.

이 사실만으로는 다음이 자동으로 성립하지 않는다.

```text
AM64x Boot ROM이 boot-mode switch를 USB로 바꿨을 때
같은 USB stick에서 tiboot3.bin을 직접 읽어 boot chain을 시작할 수 있다.
```

### 2. 현재 USB BOOT 파티션은 Boot ROM mass-storage boot 기준으로는 아직 미완성이다

live board 기준 현재 SD FAT root는 다음과 같다.

```text
/run/media/boot-mmcblk1p1
  tiboot3.bin
  tispl.bin
  u-boot.img
  uEnv.txt
  EFI/
  Image
```

반면 현재 USB BOOT FAT root는 다음과 같다.

```text
/run/media/BOOT-sda2
  Image
  k3-am642-sk.dtb
  boot/
  extlinux/
```

즉 USB BOOT root에는 최소한의 bootloader trio

```text
tiboot3.bin
tispl.bin
u-boot.img
```

가 아직 없다.

따라서 **현재 상태 그대로는 Boot ROM USB media boot를 시도할 준비가 되었다고 말하기 어렵다.**

### 3. repo 로그에는 USB DFU/device path 흔적도 있다

여러 로그에 다음 문자열이 반복된다.

```text
Please resend tiboot3.bin in case of UART/DFU boot
```

또한 U-Boot env dump에는 다음도 보인다.

```text
dfu_alt_info_mmc=... tiboot3.bin fat 1 1; tispl.bin fat 1 1; u-boot.img fat 1 1 ...
```

이것은 적어도 AM64x / current boot stack에 **DFU/device-style recovery path** 가 존재함을 시사한다.

따라서 switch의 `USB`가 실제로

1. USB mass-storage host boot인지
2. USB DFU/device boot인지

는 반드시 분리해서 확인해야 한다.

## 첨부 이미지 기준 switch 해석

사용자가 첨부한 TI guide screenshot 기준,
`BOOT-MODE [6:3]` 의 `USB` row는 다음으로 읽힌다.

```text
SW3.2 = ON
SW3.3 = OFF
SW3.4 = ON
SW3.5 = OFF
```

그리고 PLL 25 MHz 기본값은 screenshot의 `BOOTMODE [2:0]` table 기준 다음으로 읽힌다.

```text
SW3.6 = OFF
SW3.7 = ON
SW3.8 = ON
```

주의:

- 실제 보드 silk print 방향이 문서 그림과 다를 수 있다.
- 실제 스위치 조작 전에는 반드시 보드 실물 orientation 기준으로 다시 확인해야 한다.

## 실험 전에 준비해야 할 것

### A. 공통 준비

1. 현재 정상 SD boot switch 상태 사진 기록
2. 현재 USB switch 목표 상태 사진 기록
3. recovery 경로 확보
   - baseline SD switch 복귀 절차
   - UART console 확보
   - 필요 시 DFU/UART/TFTP 복구 경로 메모

### B. USB mass-storage boot 가능성에 대비한 media 준비

현재 USB BOOT FAT root에 다음을 배치한다.

```text
tiboot3.bin
tispl.bin
u-boot.img
```

가장 보수적인 1차 방법은 **현재 SD FAT에서 실제로 부팅 중인 trio를 그대로 USB BOOT root로 복제** 하는 것이다.

이 준비는 아래 helper script로 수행할 수 있다.

```text
tools/install/prepare-sk-am64b-usb-rom-boot-media.sh
```

### C. USB DFU/device boot 가능성에 대비한 host 준비

만약 switch의 `USB`가 DFU/device boot라면,
USB stick layout보다 host PC 쪽 준비가 더 중요하다.

준비 항목:

- host PC의 USB cable 연결 방식 확인
- `dfu-util` 사용 가능 여부 확인
- `tiboot3.bin`, `tispl.bin`, `u-boot.img` host-side staging
- 보드 security type(현재 HS-FS)와 artifact 일치 여부 확인

## 지금 바로 할 수 있는 준비 범위

현재 agent가 바로 할 수 있는 것은 다음까지다.

1. USB BOOT FAT root에 bootloader trio staging
2. 현재 USB BOOT / USB rootfs layout 기록
3. switch 변경 전 checklist 문서화

## 현재 적용 완료된 layout

2026-06-01 기준으로 실제 USB stick에 다음 변경을 적용했다.

### `/dev/sda1`

- 기존 junk data 삭제
- FAT32로 재포맷
- label: `ROMBOOT`
- 현재 mount point: `/mnt/usb-romboot`
- root에 다음 trio 배치 완료:

```text
tiboot3.bin
tispl.bin
u-boot.img
```

초기 staging 검증 checksum:

```text
tiboot3.bin  a97974de66c121ccccdd9b4fc16270cc
tispl.bin    ecc6dd0dbf8730745f9896f58500ecb6
u-boot.img   25ca2df6a60ac562475e3620983eb46c
```

이 checksum은 현재 SD FAT root의 proven trio와 동일하다.

### `/dev/sda2`

- 기존 rehearsal FAT `BOOT` partition 유지
- 현재 USB kernel/DTB asset 유지

## USB ROM boot용 2차 bootloader update

USB primary boot 시도에서 다음 UART failure가 관찰되었다.

```text
Trying to boot from USB
cdns-usb3-host usb@f400000: Couldn't get USB3 PHY: -19
Bus usb@f400000: Port not available.
No USB controllers found
0 Storage Device(s) found
SPL: Unsupported Boot Device!
```

이 로그를 기준으로,
현재 workspace U-Boot source에서는 SK SPL이 USB3 PHY path를 직접 잡으려다 실패한다고 판단했다.

따라서 다음 U-Boot SPL override를 적용한 2차 trio를 다시 빌드해 USB media에 staging 했다.

```text
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

이 2차 trio는 다음 checksum으로 `/dev/sda1` 과 `/dev/sda2` 양쪽에 모두 반영했다.

```text
tiboot3.bin  cddd8e6796910186dd4bc4991f301836
tispl.bin    b5239ceb9777fcf0423e219c68de82bd
u-boot.img   6beac95d99ec994eafd0e607da0046c7
```

즉 다음 USB switch 실험은 **USB3 PHY 의존성을 줄인 SPL bootloader set** 으로 수행해야 한다.

## USB ROM boot용 3차 driver-level update

2차 trio에서도 여전히 다음 failure가 유지되었다.

```text
Trying to boot from USB
cdns-usb3-host usb@f400000: Couldn't get USB3 PHY: -19
Bus usb@f400000: Port not available.
No USB controllers found
```

decompiled SPL DTB를 확인한 결과,
이미 `ti,usb2-only`, `dr_mode = "host"`, `maximum-speed = "high-speed"`,
그리고 `phys` / `phy-names` 삭제가 실제 build output에 반영되어 있었다.

즉 이 단계에서는 DT가 아니라 U-Boot Cadence core driver가
optional USB3 PHY absence를 fatal로 처리하는 쪽을 먼저 의심했다.

적용 변경:

```text
workspace/ti-u-boot-sdk12/drivers/usb/cdns3/core.c
```

요지:

```text
USB3 PHY lookup failure에서 -ENODEV도 optional-missing으로 취급
```

이 변경을 반영해 다시 빌드한 3차 trio checksum은 다음과 같고,
`/dev/sda1` 과 `/dev/sda2` 모두에 반영했다.

```text
tiboot3.bin  c7ebdb813087286dc50f1e35a1d28e73
tispl.bin    4b3f50dae94e2e0718ae8d6856e934bb
u-boot.img   e630b80ac963c6bb9f21a7a008a09a51
```

따라서 다음 USB switch 실험은 **driver-level optional PHY handling patch 포함 set** 으로 수행해야 한다.

## USB ROM boot용 4차 usb2-only-aware driver update

3차 set에서도 `Couldn't get USB3 PHY: -19` 가 유지되었다.

built SPL DTB를 다시 확인한 결과,
실제로는 이미:

- `ti,usb2-only`
- `dr_mode = "host"`
- `maximum-speed = "high-speed"`
- `phys` / `phy-names` 없음

이 반영되어 있었다.

따라서 다음 수정은 단순 errno 완화가 아니라,
Cadence core driver가 `usb2-only`일 때 **USB3 PHY get/init/power_on path 자체를 skip** 하도록 하는 것이다.

적용 파일:

```text
workspace/ti-u-boot-sdk12/drivers/usb/cdns3/core.c
```

요지:

```text
parent wrapper node가 ti,usb2-only 이면
generic_phy_get_by_name("cdns3,usb3-phy") 및
USB3 PHY init/power_on 을 수행하지 않음
```

이 변경을 반영해 다시 빌드한 4차 trio checksum은 다음과 같고,
`/dev/sda1` 과 `/dev/sda2` 양쪽에 반영했다.

```text
tiboot3.bin  c5441d7281ceb45a748d4fc3b394c6ef
tispl.bin    87130bb2af4dd8bae51d27f1a37682a0
u-boot.img   45ec3ec221b648a42a9e306e8a2b6be7
```

즉 다음 USB switch 실험은 **usb2-only-aware Cadence core patch 포함 set** 으로 수행해야 한다.

### `/dev/sda3`

- 기존 `usb-rootfs` ext4 유지

즉 현재 USB stick은 다음 3층 구조가 되었다.

```text
sda1: ROMBOOT FAT32 (Boot ROM / SPL first try candidate)
sda2: BOOT FAT32 (existing USB rehearsal kernel/DTB assets)
sda3: usb-rootfs ext4
```

## 다음 실험 직전 체크포인트

switch를 바꾸기 전에 다음만 다시 확인하면 된다.

1. 보드 전원 완전 OFF
2. SW3 USB boot mode 방향 재확인
3. UART logger attach 확인
4. 가능하면 SD card 제거 여부도 함께 결정

특히 이번 실험의 목적이 **진짜 USB primary boot 반응 확인** 이라면,
SD card가 꽂힌 상태에서 fallback이 섞이지 않도록 SD 제거를 우선 검토하는 편이 낫다.

반면 다음은 사용자의 물리 개입이 필요하다.

1. SW3 USB boot mode로 실제 변경
2. 전원 cycle / reset
3. cable 재구성(필요 시)

## 1차 권장 접근

현재 시점의 가장 안전한 1차 접근은 다음이다.

1. USB BOOT FAT root를 bootloader trio까지 포함하도록 준비
2. switch를 USB mode로 변경
3. UART에서 Boot ROM/SPL 첫 반응을 본다
4. 만약 `Trying to boot from USB` 와 함께 storage read 계열 로그가 보이면 mass-storage path로 계속 분석
5. 만약 DFU/device wait 계열 반응이면 host-side DFU 절차로 전환

즉 **지금은 먼저 준비를 끝내고, switch 변경 직후 Boot ROM이 어떤 부류의 USB path로 반응하는지 증거를 보는 것이 우선** 이다.

## USB-only autoboot 최종 확인

이후 USB media를 다음처럼 self-contained 형태로 재구성했다.

```text
/dev/sda1  FAT32  label=ROMBOOT
  tiboot3.bin
  tispl.bin
  u-boot.img
  Image
  k3-am642-sk.dtb
  /extlinux/extlinux.conf

/dev/sda2  FAT32  label=BOOT
  rehearsal kernel/DTB assets

/dev/sda3  ext4   label=usb-rootfs
  root filesystem
```

그리고 SD card를 제거한 상태에서 cold reboot 후,
manual U-Boot command 없이 다음 흐름이 실제로 관찰되었다.

```text
U-Boot SPL ...
Trying to boot from USB
Starting the controller
USB XHCI 1.00
Bus usb@f400000: 2 USB Device(s) found
scanning usb for storage devices... 1 Storage Device(s) found
...
U-Boot ...
MMC: no card present
...
Scanning bootdev 'usb_mass_storage.lun0.bootdev':
0  extlinux  ready ... /extlinux/extlinux.conf
** Booting bootflow ... with extlinux
AM64x USB extlinux Autoboot
Retrieving file: /Image
Retrieving file: /k3-am642-sk.dtb
...
Kernel command line: ... root=PARTUUID=2bcf5ad2-03 ...
...
VFS: Mounted root (ext4 filesystem) on device 8:3.
```

즉 다음이 입증되었다.

1. Boot ROM / `tiboot3.bin` 는 USB `sda1` 에서 시작된다.
2. `tispl.bin` / `u-boot.img` continuation도 USB storage에서 이어진다.
3. U-Boot proper는 `sda1` 의 `/extlinux/extlinux.conf` 를 자동 탐색해 사용한다.
4. kernel / DTB는 USB FAT (`sda1`) 에서 load 된다.
5. rootfs는 USB `sda3` (`PARTUUID=2bcf5ad2-03`) 에서 mount 된다.

따라서 **SD absent 조건에서는 end-to-end USB-only autoboot가 입증 완료** 상태다.

## 아직 남은 불확실성

현재 성공은 SD card absent 조건에서 확인된 것이다.

기본 U-Boot env는 여전히:

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
boot_targets=mmc1 mmc0 usb pxe dhcp
```

이므로 SD card inserted 상태에서는 `mmc` 쪽이 먼저 선택될 수 있다.

즉 현재 안전한 문구는 다음이다.

```text
입증 완료: SD absent USB-only autoboot
미입증: SD inserted 상태에서의 USB 우선성
```
