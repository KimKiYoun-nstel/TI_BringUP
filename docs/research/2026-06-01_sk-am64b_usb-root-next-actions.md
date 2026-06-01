# 2026-06-01 SK-AM64B USB Root 다음 액션 정리

## 목적

2026-05-29 handover 이후 시점에서 direct USB root boot 이슈의 현재 상태를 다시 정리하고,
다음 실험을 **delay 재시도**가 아니라 **원인 분리 실험** 중심으로 재구성한다.

watchdog은 이번 문서 범위에서 제외한다.

## 이번 재확인에서 확정된 사실

### 1. baseline SD root 상태는 정상이다

live UART 기준 현재 baseline cmdline은 다음과 같다.

```text
console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait
```

mount root는 실제로 SD rootfs이다.

```text
/ -> /dev/mmcblk1p2 (ext4)
```

### 2. 같은 부팅에서 USB storage 자체는 나중에 정상 enumerate 된다

`logs/runtime_log` 재확인 기준:

```text
[   49.150371] xhci-hcd xhci-hcd.6.auto: xHCI Host Controller
[   49.680760] usb 2-1: new SuperSpeed USB device number 2 using xhci-hcd
[   49.711386] usb-storage 2-1:1.0: USB Mass Storage device detected
[   49.724030] scsi host0: usb-storage 2-1:1.0
[   50.822421]  sda: sda1 sda2 sda3
[   55.299177] EXT4-fs (sda3): mounted filesystem ...
```

즉 현재 USB stick, xHCI host, usb-storage, scsi, block layer 자체가 완전히 죽어 있는 상태는 아니다.

### 3. USB rootfs target 식별값은 현재도 동일하다

live shell 기준:

```text
blkid -s PARTUUID -o value /dev/sda3
2bcf5ad2-03
```

case matrix에서 사용한 `root=PARTUUID=2bcf5ad2-03` 가 현재 대상 USB rootfs와 일치한다.

### 4. steady-state 시점에는 deferred device가 남아 있지 않다

baseline SD root가 모두 올라온 뒤에는 다음이 empty였다.

```text
cat /sys/kernel/debug/devices_deferred
```

즉 현재 보이는 deferred 문제는 **영구 bind failure**라기보다,
direct USB root 시점의 **early boot ordering / supplier readiness** 문제일 가능성이 더 높다.

## 기존 케이스와 합친 현재 해석

`docs/research/2026-05-28_sk-am64b_usb-boot-case-matrix.md` 기준으로 다음은 이미 강하다.

1. U-Boot file path mismatch는 초기 원인이었지만 현재 주원인은 아니다.
2. `CONFIG_USB_*`, `CONFIG_SCSI`, `CONFIG_BLK_DEV_SD`, `CONFIG_EXT4_FS` 누락은 주원인 가능성이 낮다.
3. `rootdelay`, `rootwait`, `usb-storage.delay_use=0`, `scsi_mod.scan=sync` 반복만으로는 해결되지 않았다.
4. direct USB root path에서는 `platform f400000.usb: deferred probe pending ... phy@0` 또는 `wiz@f000000` 류의 signature가 관찰되었다.
5. `serdes_wiz0` disable + `ti,usb2-only` + `dr_mode="otg"` 조합에서는 xHCI host init timing이 빨라졌지만,
   여전히 `usb-storage` / `sda`가 root mount 전에 나오지 않았다.

따라서 현재 병목은 다음 문장으로 요약된다.

```text
USB mass-storage stack은 결국 살아나지만,
direct USB root에서는 prepare_namespace() 이전에 root block device가 준비되지 못한다.
```

## source/asset 상태

현재 repo-managed USB boot config fragment는 다음이다.

`bsp/linux/configs/am64x-usb-boot.config`

```text
CONFIG_USB=y
CONFIG_USB_XHCI_HCD=y
CONFIG_USB_XHCI_PLATFORM=y
CONFIG_USB_STORAGE=y
CONFIG_USB_GADGET=y
CONFIG_USB_CDNS_SUPPORT=y
CONFIG_USB_CDNS3=y
CONFIG_USB_CDNS3_GADGET=y
CONFIG_USB_CDNS3_HOST=y
CONFIG_USB_CDNS3_TI=y
CONFIG_SCSI=y
CONFIG_BLK_DEV_SD=y
CONFIG_EXT4_FS=y
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
```

workspace에는 다음 rehearsal DT variant가 존재한다.

`workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-sk-usb-root.dts`

핵심 delta:

1. `ti,usb2-only;`
2. `&serdes_wiz0 { status = "disabled"; }`
3. `&usb0 { maximum-speed = "high-speed"; }`
4. `phys` / `phy-names` 삭제
5. 현재 파일은 `dr_mode = "otg"`

이 파일은 이번에 repo 쪽 `bsp/linux/dts/` 후보 자산으로도 복제한다.

## 외부 참고에서 얻은 힌트

### 1. TI E2E의 과거 SK-AM64 USB boot 논의

SK-AM64에서 과거 USB boot 논의 중,
기본 `dr_mode = "otg"` 대신 `dr_mode = "host"` 와 built-in Cadence 관련 config가 필요했던 사례가 있다.

이 점은 현재 local C15가 `otg` 단순화 path만 확인했다는 점과 맞물린다.

### 2. AM64x 계열 custom board에서 `ti,usb2-only` 로 USB3 PHY 의존성을 제거해 문제를 줄인 사례가 있다

즉 `USB3/SerDes supplier chain` 자체가 문제 축일 가능성은 여전히 유효하다.

### 3. 다른 AM64x 계열 forum 사례에서도 Cadence/Torrent PHY ready timeout 후 `f400000.usb` probe 실패가 보고된다

즉 `phy ready before root mount` 축은 단순 추측이 아니라 계열 특성상 plausibility가 있다.

## 다음 실험 우선순위

### N16. 단순화 DT variant + `dr_mode = "host"` 재시도

목적:

- 현재 C15는 `otg` 단순화 path만 검증했다.
- TI 쪽 과거 힌트와 local 결과를 합치면, 다음 분기점은 `host` 재시도다.

권장 조합:

```text
Kernel: repo-managed USB build
DTB: usb-root variant 기반, 단 dr_mode = "host"
root=: PARTUUID=2bcf5ad2-03
rootdelay: 60
init: init=/bin/sh
```

성공 기준:

```text
Run /bin/sh as init process
```

추가로 봐야 할 것:

```text
usb-storage
scsi host0
sda1 sda2 sda3
```

### N16 결과

`FAIL`

fresh manual U-Boot load 기준:

```text
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=2bcf5ad2-03 rw rootwait init=/bin/sh'
load usb 0:2 ${loadaddr} /boot/Image.usbtest
load usb 0:2 ${fdtaddr} /boot/dtb/ti/k3-am642-sk-usb-root.dtb
fdt print ... dr_mode = "host"
booti ${loadaddr} - ${fdtaddr}
```

핵심 UART evidence:

```text
[   25.608221] probe of f900000.cdns-usb returned -517
[   32.270135] xhci-hcd xhci-hcd.0.auto: xHCI Host Controller
[   32.373703] probe of f400000.usb returned 0
[   32.379897] probe of f900000.cdns-usb returned 0
[   33.054912] Waiting for root device PARTUUID=2bcf5ad2-03...
```

관찰 포인트:

1. `dr_mode="host"` 강제로 xHCI host와 Cadence wrapper probe 자체는 완료됐다.
2. 그러나 그 직후에도 `usb-storage`, `scsi host0`, `sda` 증거가 없다.
3. 즉 이번에는 `host role 진입 실패` 보다, **host probe 완료 이후 mass-storage enumeration이 root mount 이전에 붙지 않는 문제**로 보는 편이 더 정확하다.

### N17. initramfs holdoff 실험

목적:

- 문제를 "USB root capability 부재" 와 "root mount 시점 이전 준비 실패" 중 어디로 볼지 분리한다.

핵심 아이디어:

1. 작은 initramfs로 먼저 부팅
2. `/sys/kernel/debug/devices_deferred`, `/sys/bus/usb/devices`, `/dev/disk/by-partuuid` 상태를 관찰
3. `/dev/disk/by-partuuid/2bcf5ad2-03` 등장 후 `switch_root`

판정:

- initramfs에서 USB rootfs가 뒤늦게라도 나타나면 원인은 **early sequencing** 쪽이다.
- 끝까지 안 나타나면 단순 timing보다 **DT/PHY/role path** 쪽 비중이 더 커진다.

### N17 1차 결과

`FAIL`

이번 cycle에서는 다음을 수행했다.

1. `Image.usbtest` 를 USB `0:2` 에서 load
2. `k3-am642-sk-usb-root.dtb` 를 USB `0:2` 에서 load
3. `sk-am64b-usb-root-diag.cpio.gz` 를 `mmc 1:2 /boot/` 에서 load
4. `rdinit=/init` + watchdog 240 설정 후 `booti`

그러나 핵심 UART evidence는 다음과 같았다.

```text
[    7.348468] check access for rdinit=/init failed: -2, ignoring
[    7.371618] Waiting for root device PARTUUID=2bcf5ad2-03...
...
U-Boot SPL 2026.01...
```

즉 이번 cycle은 **N17 diagnostic initramfs 자체에 진입하지 못했다.**

해석:

1. 이번 실패는 아직 `N17DIAG:` 로깅 단계의 USB readiness 문제 이전이다.
2. 먼저 current USB test kernel이 external initramfs를 실제로 받을 수 있어야 한다.
3. 다음 cycle 전 준비 항목은 `CONFIG_BLK_DEV_INITRD=y`, `CONFIG_RD_GZIP=y`, `CONFIG_DEBUG_FS=y` 를 포함한 kernel rebuild다.

### N17 2차 결과

`FAIL`, but this time the intended diagnostic path actually ran.

변경점:

1. USB test kernel에 `CONFIG_BLK_DEV_INITRD=y`, `CONFIG_RD_GZIP=y`, `CONFIG_DEBUG_FS=y` 를 포함시켰다.
2. diagnostic initramfs build script의 archive corruption bug를 수정했다.
3. 새 `Image.usbtest`, `k3-am642-sk-usb-root.dtb`, `sk-am64b-usb-root-diag.cpio.gz` 를 다시 배포했다.

핵심 UART evidence:

```text
[    5.724174] Unpacking initramfs...
[    7.461803] Run /init as init process
N17DIAG: snapshot t=0 rootdev=/dev/sda3
...
N17DIAG: snapshot t=120 rootdev=/dev/sda3
N17DIAG: timeout waiting for /dev/sda3; leaving system to watchdog reset
```

관찰 포인트:

1. 이제 external initramfs 진입 자체는 확정되었다.
2. initramfs가 120초 동안 `/sys/bus/usb/devices`, `/sys/class/block`, `devices_deferred` 를 계속 관찰했지만 `/dev/sda3`는 나타나지 않았다.
3. 즉 현재 문제는 더 이상 root mount race만이 아니라, **host mode 진입 후에도 pre-root window 동안 USB mass-storage block device가 생성되지 않는 것**으로 정리된다.

현재 최우선 다음 단계:

```text
N18: initramfs 내부에서 usb-storage/scsi/block 생성 시점을 더 직접 계측하거나,
     host controller / phy / storage probe path에 대한 추가 driver-level instrumentation을 넣는다.
```

### N18. direct path fresh repro 시 deferred trace 더 수집

가능하면 다음 boot 1회는 결과만 보지 말고 아래 string의 상대 시점을 같이 적는다.

```text
f400000.usb
f900000.cdns-usb
phy@0
wiz@f000000
xhci-hcd
usb-storage
Waiting for root device
```

지금 필요한 것은 "실패했다" 가 아니라,
**어느 supplier chain이 언제 풀렸고 root wait 전에 무엇이 끝내 안 나왔는가** 이다.

## 이번 시점의 작업 결론

현재는 새 fix를 섣불리 단정할 단계가 아니다.

하지만 다음 두 가지는 충분히 정리되었다.

1. direct USB root 문제는 단순 delay 튜닝 단계는 지났다.
2. 다음 실험은 `host vs otg` 와 `initramfs holdoff` 두 축으로 좁히는 것이 가장 정보량이 크다.

즉 다음 세션/실험의 1순위는 watchdog 반복이 아니라 다음 둘 중 하나다.

```text
N17: initramfs holdoff로 root mount 이전 USB readiness 직접 관찰
N18: direct path fresh repro에서 usb-storage/scsi attach 시점 추가 계측
```

현재 시점에서는 N17 1차 cycle이 끝났고, 실제 최우선은 **initramfs-support kernel rebuild 후 N17 재실행** 이다.
