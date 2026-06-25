# 2026-06-19 CPU_BRD_V03_PBA_260511 OSPI U-Boot + eMMC Current Kernel Fixed DTB Boot Log

## 목적

이 문서는 다음 상태에서 reboot 후 부트로그를 수집한 기록이다.

- bootloader source: OSPI known-good
- Linux handoff source: eMMC rootfs `/boot`
- kernel: current custom kernel
- DTB: bringup-default 수정 반영 후 재생성한 fixed custom DTB

custom board의 canonical raw UART evidence는
`projects/am64x-custom-board-emmc-boot-lab/logs/2026-06-19_ospi-uboot_current-kernel-final-fixed-dtb_uart-reboot.log`다.
이 문서는 해당 reboot의 핵심 관찰점만 정리한 요약 문서다.

## reboot 전 확인 상태

- SSH 접속 성공
- kernel release: `6.18.13-gc21449208550-dirty`
- cmdline: `console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=a5c46e86-02 rw rootfstype=ext4 rootwait`
- rootfs: `/dev/mmcblk0p2`
- boot mount: `/run/media/boot-mmcblk0p1`

## 이번 세션에서 반영한 DT 수정

bringup-default 기준으로 다음 unresolved block을 disable했다.

- `usbss0`
- `usb0`
- `serdes_ln_ctrl`
- `serdes_wiz0`
- `serdes0`
- `icssg0`
- `icssg1`
- `crypto` (`sa2ul`)
- `main_r5fss0/1` 및 core들
- `mcu_m4fss`

추가로 `k3-am64-ti-ipc-firmware.dtsi`가 include 마지막에 remoteproc/M4 노드를 다시 `okay`로 되살리는 문제를 막기 위해, `k3-am6412-custom-final.dts`의 include 뒤에서 다시 `status = "disabled"`를 덮어썼다.

## reboot 직전 active `/boot` 상태

- `/boot/Image` sha256: `9d708e3401d591b9f7bc636674a4592e475871eee6a80aebe7b48cab01a7b671`
- `/boot/dtb/ti/k3-am642-sk.dtb` sha256: `3b340aad889b691eaea521d904c141d44279ac75352f55e7888af6f4ca172990`
- `/boot/dtb/ti/k3-am6412-cpu-brd-v03-pba.dtb` sha256: `3b340aad889b691eaea521d904c141d44279ac75352f55e7888af6f4ca172990`

## reboot 후 핵심 boot evidence

부트 체인은 정상적으로 다음 순서로 진행되었다.

```text
OSPI tiboot3/tispl/u-boot
  -> U-Boot env-driven MMC boot
  -> eMMC /boot/Image + /boot/dtb/ti/k3-am642-sk.dtb
  -> Linux kernel boot
  -> rootfs mount
  -> systemd / login prompt
```

이번 reboot에서 확인된 핵심 UART evidence:

```text
[    1.981001] check access for rdinit=/init failed: -2, ignoring
[   11.024446] cfg80211: failed to load regulatory.db
[   12.204670] ti_sci_pm_domains ... pending due to fc40000.spi
[   13.380200] am65-cpsw-nuss 8000000.ethernet eth0: PHY [8000f00.mdio:00] driver [TI DP83867] (irq=POLL)
[   17.545389] am65-cpsw-nuss 8000000.ethernet eth0: Link is Up - 1Gbps/Full - flow control off
[   18.129091] omap-mailbox 29020000.mailbox: omap mailbox rev 0x66fc9100
[   18.165002] omap-mailbox 29040000.mailbox: omap mailbox rev 0x66fc9100
[   18.209567] omap-mailbox 29060000.mailbox: omap mailbox rev 0x66fc9100
[   18.493125] at24 0-0051: 65536 byte 24c512 EEPROM, writable, 1 bytes/write
am64xx-evm login:
```

## reboot 후 확인 결과

- UART에서 `login:` prompt 도달 확인
- UART `root` login 성공
- SSH 재접속 성공
- reboot 후 boot ID: `13bad274-7199-4b4a-95c8-664ae0257fe2`

SSH 확인 결과:

```text
Linux am64xx-evm 6.18.13-gc21449208550-dirty #3 SMP PREEMPT Wed Jun 17 16:38:07 KST 2026 aarch64 GNU/Linux
```

## 판단

이번 reboot으로 다음을 확인했다.

1. 현재 `OSPI U-Boot + eMMC current kernel + fixed custom DTB + current modules` 조합은 정상 login 단계까지 간다.
2. 이전 crash의 직접 원인은 current DTB가 unresolved subsystem을 너무 넓게 enable한 상태에서 current modules가 autoload/probe되던 경로로 본다.
3. bringup-default 단계에서는 `USB/SERDES`, `ICSSG/PRUSS`, `remoteproc`, `SA2UL`을 disable한 상태를 유지하는 것이 맞다.

## 다음 액션

1. 현재 살아 있는 Linux에서 `uname -a`, `dmesg`, `lsmod`, network, storage 상태를 추가 점검
2. 문제가 없으면 같은 kernel/DTB 세트를 기준으로 eMMC bootloader 검증 단계로 이동
3. 이후 별도 실험에서 `USB/SERDES`, `ICSSG/PRUSS`, `remoteproc`, `SA2UL`을 하나씩 재활성화하며 원인 분리
