# 2026-05-28 SK-AM64B USB Boot Case Matrix

## 목적

SK-AM64B USB boot 실험을 ad hoc 방식이 아니라 **케이스 매트릭스 기반**으로 관리한다.

현재 기준에서 kernel config 재현성 문제는 해소되었고, 남은 핵심 축은 다음이다.

- DTB: `k3-am642-sk.dtb` / `k3-am642-sk-usb-root.dtb`
- root selector: `LABEL=usb-rootfs` / `/dev/sda3` / `PARTUUID=2bcf5ad2-03`
- rootdelay: `5` / `30` / `60` / `90`
- init mode: normal / `init=/bin/sh`
- U-Boot path: env helper manual load / extlinux / broken path

## 상태 규칙

- `PENDING`: 아직 실행 안 함
- `TRIED`: 실행했지만 로그가 섞였거나 판정이 불완전함
- `PASS`: fresh log 기준 단일 시도에서 UART 증거로 성공 확인
- `FAIL`: fresh log 기준 실패 지점이 명확함

## 성공 기준

### normal init

- fresh UART 로그에서 kernel handoff 이후 `login:` 또는 shell prompt 도달
- 가능하면 추가 확인:
  - `cat /proc/cmdline`
  - `findmnt /`
  - `lsblk -f`

### `init=/bin/sh`

- fresh UART 로그에서 아래 증거 중 하나 확인
  - `Run /bin/sh as init process`
  - UART shell prompt

SSH 여부는 성공 기준으로 쓰지 않는다.

## Case Matrix

| Case ID | Status | Kernel | DTB | root= | rootdelay | init | U-Boot path | Observed evidence | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| C01 | FAIL | pre-USB-build `Image.usbtest` intent | baseline | PARTUUID | 5 | normal | env helper but bad file path | `Failed to load '/boot/Image.usbtest'`, `Failed to load '/boot/ti/...dtb'` | U-Boot file path mismatch |
| C02 | FAIL | earlier rebuild context | baseline | `LABEL=usb-rootfs` | with rootwait | normal | env/manual family | `Disabling rootwait; root= is invalid`, `Cannot open root device` | LABEL path invalid on this path |
| C03 | FAIL | earlier rebuild context | baseline | `/dev/sda3` | unspecified | normal | env/manual family | `Waiting for root device /dev/sda3...` | root device wait |
| C04 | TRIED | rebuilt `/boot/Image.usbtest` | baseline | `PARTUUID=2bcf5ad2-03` | 5 | normal | env helper | handover claims `login:` reached, but logs were mixed with later SD boots | needs fresh repro |
| C05 | TRIED | known-good SD kernel+DTB | baseline | USB rootfs | varied | `init=/bin/sh` | SD kernel/DTB + USB rootfs split test | `VFS: Mounted root`, `Run /bin/sh as init process` seen per handover | likely success, but needs fresh repro and prompt check |
| C06 | TRIED | earlier rebuild context | baseline | PARTUUID | 90 | normal | env/manual family | `Waiting 90 sec before mounting root device...`, later mount-like evidence mentioned in handover | needs fresh repro |
| C07 | FAIL | rebuilt kernel with built-in CDNS | baseline | `PARTUUID=2bcf5ad2-03` | 60 | normal | env helper | `platform f400000.usb: deferred probe pending ... phy@0`, then `Waiting for root device PARTUUID=...` | kernel-side USB/PHY bring-up suspect |
| C08 | FAIL | rebuilt kernel with built-in CDNS | usb-root variant | `PARTUUID=2bcf5ad2-03` | 60 | normal | env helper | `bus@f4000:wiz@f000000` pending, then `Waiting for root device PARTUUID=...` | DTB changes symptoms but not outcome |
| C09 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | baseline | `PARTUUID=2bcf5ad2-03` | 60 | normal | env helper | new kernel actually booted, then same `f400000.usb ... phy@0` pending and root wait | config issue no longer primary suspect |
| C10 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | baseline | `PARTUUID=2bcf5ad2-03` | 60 | `init=/bin/sh` | env helper | no `Run /bin/sh as init process`; still `f400000.usb ... phy@0` deferred probe then `Waiting for root device PARTUUID=...` | root mount itself did not complete |
| C11 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | usb-root variant | `PARTUUID=2bcf5ad2-03` | 60 | `init=/bin/sh` | env helper | no `Run /bin/sh as init process`; no root mount; `wiz@f000000` pending signature remains, then `Waiting for root device PARTUUID=...` | DTB variant still does not reach root mount |
| C12 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | baseline | `PARTUUID=2bcf5ad2-03` | 90 | `init=/bin/sh` | env helper | `Waiting 90 sec before mounting root device...`, then same `f400000.usb ... phy@0` deferred probe; no `Run /bin/sh as init process` | delay increase alone still does not mount root |
| C13 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | usb-root variant | `PARTUUID=2bcf5ad2-03` | 90 | `init=/bin/sh` | env helper | valid U-Boot prompt from user-provided `=>`; `Waiting 90 sec before mounting root device...`; no `Run /bin/sh as init process`; root mount success evidence absent | usb-root variant + longer delay still does not solve root mount |
| C14 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | usb-root variant + `serdes_wiz0` disabled | `PARTUUID=2bcf5ad2-03` | 90 | `init=/bin/sh` | env helper | valid U-Boot run; `Waiting 90 sec before mounting root device...`; `Run /bin/sh as init process` absent; previous `f400000.usb` / `wiz@f000000` deferred probe signature no longer appears | removing WIZ supplier changes the failure signature but still does not produce a mounted USB root |
| C15 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | usb-root variant + `serdes_wiz0` disabled + `dr_mode="otg"` | `PARTUUID=2bcf5ad2-03` | 90 | `init=/bin/sh` | env helper | valid U-Boot run; early `xhci-hcd` host init appears by ~2.1s, but still no `usb-storage`/`sda` before timeout; `Waiting for root device PARTUUID=...` at ~93s | role assumption changes early host init timing but still does not yield a USB root block device |
| C16 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) | usb-root variant + `serdes_wiz0` disabled + `dr_mode="host"` | `PARTUUID=2bcf5ad2-03` | implicit `rootwait` | `init=/bin/sh` | manual U-Boot load from USB | `f900000.cdns-usb` first returns `-517`, then `xhci-hcd.0.auto` / `f400000.usb` / `f900000.cdns-usb` all probe successfully by ~32.38s, but kernel still reaches `Waiting for root device PARTUUID=2bcf5ad2-03...` at ~33.05s with no `usb-storage` / `scsi host0` / `sda` evidence | forcing host mode removes the older immediate deferred-probe outcome, but host-ready alone is still insufficient for pre-root USB mass-storage enumeration |
| C17 | FAIL | repo-managed USB build (`#2`, IKCONFIG verified) + external `sk-am64b-usb-root-diag.cpio.gz` | usb-root variant + `serdes_wiz0` disabled + `dr_mode="host"` | `PARTUUID=2bcf5ad2-03` | watchdog 240 | `rdinit=/init` | manual U-Boot load from USB + mmc initramfs load | `load mmc 1:2 ... sk-am64b-usb-root-diag.cpio.gz` succeeded, but kernel printed `check access for rdinit=/init failed: -2, ignoring`, then `Waiting for root device PARTUUID=2bcf5ad2-03...`, and board reset before any `N17DIAG:` output | this cycle did not actually enter the external initramfs; next cycle must first ensure the USB test kernel is rebuilt with initramfs support (`CONFIG_BLK_DEV_INITRD`, `CONFIG_RD_GZIP`) |
| C18 | FAIL | repo-managed USB build + initramfs-support config + fixed external `sk-am64b-usb-root-diag.cpio.gz` | usb-root variant + `serdes_wiz0` disabled + `dr_mode="host"` | `PARTUUID=2bcf5ad2-03` | watchdog 240 | `rdinit=/init` | manual U-Boot load from USB + mmc initramfs load | kernel unpacked initramfs, printed `Run /init as init process`, emitted `N17DIAG:` snapshots from `t=0` through `t=120`, but never logged `/dev/sda3`; final marker was `N17DIAG: timeout waiting for /dev/sda3; leaving system to watchdog reset`, and board later returned to baseline login/shell | this is the first clean initramfs-based proof that pre-root USB mass-storage enumeration still does not happen even when `/init` holds the system open for 120s |

## 고정 사실

1. U-Boot 단계에서는 USB storage enumeration과 kernel/DTB load가 반복적으로 성공한다.
2. 새 USB build kernel은 `extract-ikconfig`로 `CONFIG_USB_CDNS_SUPPORT=y`, `CONFIG_USB_CDNS3=y`, `CONFIG_USB_CDNS3_HOST=y`, `CONFIG_USB_CDNS3_TI=y`가 직접 확인되었다.
3. 현재 병목은 command syntax보다 kernel-side USB root mount 경로일 가능성이 더 높다.

## 다음 우선 실험

### N01

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: baseline `k3-am642-sk.dtb`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `60`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- command/U-Boot file path 문제는 이미 대부분 배제되었다.
- 현재 가장 중요한 질문은 **USB rootfs를 mount 자체는 할 수 있는가**이다.
- `init=/bin/sh`는 userspace/systemd 변수를 제거하고 root mount 성공 여부를 가장 직접적으로 판별한다.

### 결과

`FAIL`

- kernel banner: `Linux version ... #2 ...`
- `Waiting 60 sec before mounting root device...`
- `platform f400000.usb: deferred probe pending: ... phy@0`
- `Waiting for root device PARTUUID=2bcf5ad2-03...`
- `Run /bin/sh as init process` 미도달

### 해석

- normal init 문제가 아니라, rootfs mount 자체가 완료되지 못한다.
- command/U-Boot file path 문제보다 Linux-side USB root bring-up 문제가 더 강하게 의심된다.

## 다음 우선 실험

### N02

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: usb-root variant `k3-am642-sk-usb-root.dtb`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `60`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- baseline DTB에서는 `f400000.usb ... phy@0` deferred probe가 반복된다.
- usb-root variant는 이 signature를 바꾸는 효과가 이미 관찰되었다.
- 이제 userspace 변수를 제거한 `init=/bin/sh` 조건에서 DTB 차이가 root mount 단계에 실질적으로 영향을 주는지 확인할 차례다.

### 성공 기대 증거

```text
VFS: Mounted root (ext4 filesystem) on device 8:3.
Run /bin/sh as init process
```

또는 UART shell prompt.

### 결과

`FAIL`

- kernel banner: `Linux version ... #2 ...`
- `Waiting 60 sec before mounting root device...`
- `bus@f4000:wiz@f000000` pending signature 유지
- `Waiting for root device PARTUUID=2bcf5ad2-03...`
- `Run /bin/sh as init process` 미도달

### 해석

- baseline DTB와 usb-root DTB 모두 `init=/bin/sh` 조건에서 root mount 자체를 못 넘겼다.
- usb-root variant는 symptom shape를 바꾸지만, mount 성공으로 이어지지 않는다.

## 다음 우선 실험

### N03

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: baseline `k3-am642-sk.dtb`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `90`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- handover에는 `rootdelay=90`에서 이후 `sda3` mount까지 간 사례가 있다고 기록돼 있다.
- `init=/bin/sh`는 userspace 영향을 제거하므로, delay만 늘렸을 때 root mount가 실제로 되는지 직접 확인할 수 있다.
- baseline/usb-root DTB 둘 다 `60`초에서 실패했으므로, 다음 분기점은 DTB보다 enumeration timing 차이 확인이다.

### 결과

`FAIL`

- kernel banner: `Linux version ... #2 ...`
- `Waiting 90 sec before mounting root device...`
- `platform f400000.usb: deferred probe pending: ... phy@0`
- `Run /bin/sh as init process` 미도달

### 해석

- `rootdelay=90` 적용 자체는 확인되었다.
- 하지만 delay 증가만으로 root mount는 해결되지 않았다.
- 현 시점에서 남은 우선 가설은 timing 단독 문제가 아니라 USB host/PHY/SerDes bring-up 경로 그 자체다.

## 다음 우선 실험

### N04

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: usb-root variant `k3-am642-sk-usb-root.dtb`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `90`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- usb-root variant가 baseline의 `usb0 -> USB3 PHY supplier chain` 의존을 줄이는지 더 긴 delay와 함께 확인
- baseline/variant 모두 `60`에서는 실패했으므로, variant + `90`의 조합이 마지막 timing 완화 케이스다.

### 결과

`FAIL`

- valid U-Boot `=>` prompt에서 실행됨
- kernel banner: `Linux version ... #2 ...`
- `Waiting 90 sec before mounting root device...`
- `Run /bin/sh as init process` 미도달
- root mount 성공 증거 없음

### 해석

- `usb-root` DTB와 `rootdelay=90`를 결합해도 root mount 자체가 되지 않는다.
- 따라서 현재 남은 검색 공간은 command/rootdelay 조합보다 더 좁고, SK-AM64B의 USB host/PHY/SerDes bring-up 또는 더 낮은 board-specific dependency 쪽으로 수렴한다.

## 다음 우선 실험

### N06

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: usb-root variant + `serdes_wiz0` disabled + `dr_mode = "otg"`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `90`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- AM642 EVM/TMDS64EVM Linux DTS는 USB2-only/high-speed/OTG 쪽 가정을 가진다.
- SK usb-root variant에서 role assumption을 EVM 쪽과 더 가깝게 만들어 early host path 형성이 달라지는지 본다.

### 결과

`FAIL`

- valid U-Boot `=>` prompt에서 실행됨
- kernel banner: `Linux version ... #2 ...`
- `xhci-hcd` host init이 매우 이른 시점(~2.1s)에 나타남
- `Waiting 90 sec before mounting root device...`
- `usb-storage`, `scsi host0`, `sda` partition discovery는 root mount 전까지 나타나지 않음
- `Run /bin/sh as init process` 미도달

### 해석

- `dr_mode = "otg"` 변경은 early xHCI host bring-up timing을 바꾸는 효과가 있었다.
- `dr_mode = "host"` 강제에서도 `usb-storage` / `sda`가 root mount 전에 나타나지 않았다.
- 즉 다음 우선순위는 role 값 재시도보다 `initramfs holdoff` 로 pre-root readiness 자체를 직접 관찰하는 쪽이다.
- 단, 외부 initramfs 실험 전제조건으로 kernel 쪽 `CONFIG_BLK_DEV_INITRD` / `CONFIG_RD_GZIP` 유무를 먼저 보장해야 한다.
- `C18`로 이제 initramfs 진입 자체는 입증되었고, 문제는 실제로 `/dev/sda3`가 pre-root window 동안 끝내 생기지 않는다는 쪽으로 다시 좁혀졌다.
- 하지만 핵심 실패는 이제 더 좁혀졌다: controller/xHCI host는 올라오지만, root mount 시점까지 USB mass-storage block device가 준비되지 않는다.
- 즉 남은 병목은 host role 자체보다 더 뒤쪽의 USB storage enumeration / SCSI disk readiness / board-specific electrical dependency 쪽일 가능성이 높다.

## 다음 우선 실험

### N05

- Kernel: repo-managed USB build `Image.usbtest`
- DTB: usb-root variant + `&serdes_wiz0 { status = "disabled"; }`
- root=: `PARTUUID=2bcf5ad2-03`
- rootdelay: `90`
- init: `init=/bin/sh`
- U-Boot path: env helper manual load

### 이유

- baseline/variant 모두 `f400000.usb -> phy@0 / wiz@f000000` supplier chain이 의심됐기 때문에, WIZ supplier를 명시적으로 제거해 failure signature가 바뀌는지 확인

### 결과

`FAIL`

- valid U-Boot `=>` prompt에서 실행됨
- kernel banner: `Linux version ... #2 ...`
- `Waiting 90 sec before mounting root device...`
- `Run /bin/sh as init process` 미도달
- root mount 성공 증거 없음
- 기존의 `f400000.usb` / `wiz@f000000` deferred probe signature는 더 이상 로그에 나타나지 않음

### 해석

- WIZ supplier chain은 실제로 failure signature에 영향을 준다.
- 하지만 그 chain을 제거해도 root mount는 되지 않았다.
- 따라서 root-cause는 USB3 PHY supplier chain 하나에만 있지 않고, USB root boot에 필요한 더 낮은 레벨의 board-specific dependency 또는 다른 early host path 조건이 남아 있을 가능성이 높다.
