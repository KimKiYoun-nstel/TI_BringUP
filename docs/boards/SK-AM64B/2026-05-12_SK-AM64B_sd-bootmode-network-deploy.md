# SK-AM64B SD BootMode, Wi-Fi Probe, and Network Deploy Note

- Date: 2026-05-12
- Board: SK-AM64B / AM642 SK
- Context: TI Processor SDK Linux / Arago 2025.01, SDK 12 U-Boot standalone build validation
- Recommended repo path: `docs/boards/SK-AM64B/2026-05-12_sd-bootmode-network-deploy.md`
- Related raw logs path if preserved separately: `docs/bringup-logs/2026-05-12_SK-AM64B_sd-bootmode-network-deploy-log.md`

## Repository Category Decision

This session should primarily be documented under:

```text
docs/boards/SK-AM64B/
```

Reason:

- The key finding is board-specific: SK-AM64B SD boot mode switch setting affected the final Linux Device Tree passed by U-Boot and changed whether MMC0/WiLink was enabled.
- The Ethernet and SSH/SCP deploy flow was validated on this specific board and SD-card layout.
- Raw command outputs, boot logs, and pasted terminal sessions should be separated into `docs/bringup-logs/` if long-term evidence is needed.
- A future generalized procedure for “copy U-Boot artifacts to a target over SSH” can later be promoted into `docs/setup/` or `docs/common/` if reused across boards.

## Knowledge

### Boot artifacts replaced on SD boot partition

The board was initially updated by copying only the following three U-Boot-related artifacts to the SD card boot partition:

```text
tiboot3.bin
tispl.bin
u-boot.img
```

The Linux kernel `Image`, root filesystem, and `/boot/dtb/ti/k3-am642-sk.dtb` were not intentionally changed.

Observed boot partition path on the running board:

```text
/run/media/boot-mmcblk1p1/
```

Relevant files observed there:

```text
Image
tiboot3.bin
tispl.bin
u-boot.img
uEnv.txt
tiboot3.prebuilt.bin
tispl.prebuilt.bin
u-boot.prebuilt.img
```

### U-Boot build timestamp meaning

U-Boot log timestamp is the build timestamp embedded in the binary, not the current boot time.

Example:

```text
U-Boot SPL 2026.01-g2549829cc194 (May 12 2026 - 13:08:32 +0900)
```

This means the relevant SPL binary was built at that time. It is useful for confirming whether the expected binary was actually used during boot.

For AM64x boot logs, the stages should be interpreted carefully:

```text
tiboot3.bin  -> early R5 SPL / first U-Boot SPL messages
tispl.bin    -> later A53 SPL messages
u-boot.img   -> U-Boot proper message
```

File modification time from `ls -al` is not always identical to the build timestamp embedded in the binary. Use boot log timestamp and `sha256sum` for stronger validation.

### Timezone note

The board and WSL2 were showing the same time in different timezones:

```text
Board Linux: Tue May 12 07:30:12 UTC 2026
WSL2 host:   Tue May 12 16:30:15 KST 2026
```

KST is UTC+9, so these are effectively the same time.

### Wi-Fi disappeared because MMC0 was disabled in the running Device Tree

When `wlan0` was missing, the board showed:

```bash
ip addr
```

Only `lo`, `eth0`, `eth1`, and `docker0` appeared. `wlan0` did not exist.

Wi-Fi-related checks showed:

```text
cfg80211 loaded
wl18xx firmware files present
wl18xx/wlcore probe logs absent
mmc0 absent
```

The decisive evidence:

```bash
cat /proc/device-tree/bus@f4000/mmc@fa10000/status
# disabled

cat /proc/device-tree/bus@f4000/mmc@fa00000/status
# okay
```

On SK-AM64B:

```text
mmc@fa10000 = MMC0 = WiLink WL1837 SDIO
mmc@fa00000 = MMC1 = microSD card
```

Therefore, if `mmc@fa10000` is disabled in the running Device Tree, Linux never probes MMC0, WiLink is not detected, and `wlan0` cannot appear.

### Original DTB was okay; U-Boot modified the running FDT

The DTB file in the root filesystem was checked:

```bash
dtc -I dtb -O dts /boot/dtb/ti/k3-am642-sk.dtb > /tmp/k3-am642-sk.dts
dtc -I fs -O dts /proc/device-tree > /tmp/running.dts
```

The original DTB contained:

```dts
mmc@fa10000 {
    compatible = "ti,am64-sdhci-8bit";
    status = "okay";
    wlcore@2 {
        compatible = "ti,wl1837";
        reg = <0x02>;
    };
};
```

But the running Device Tree contained:

```dts
mmc@fa10000 {
    compatible = "ti,am64-sdhci-8bit";
    status = "disabled";
    wlcore@2 {
        compatible = "ti,wl1837";
        reg = <0x02>;
    };
};
```

Conclusion: the DTB file was not inherently wrong. U-Boot changed the final FDT before passing it to Linux.

### BootMode switch setting affected Linux-visible device status

After correcting the boot mode switch setting, `wlan0` appeared.

The important discovery:

- Boot mode switches are sampled by Boot ROM for boot media selection.
- On TI K3 / AM64x systems, U-Boot may also use boot mode information for board logic and FDT fixups.
- Therefore, a boot mode switch can indirectly affect which devices Linux sees as enabled or disabled.

Corrected state produced:

```bash
ip addr
```

With `wlan0` visible:

```text
4: wlan0: <NO-CARRIER,BROADCAST,MULTICAST,UP> ... state DOWN
```

### Wired Ethernet deploy path was validated

After connecting Ethernet, the board logged:

```text
am65-cpsw-nuss 8000000.ethernet eth0: Link is Up - 1Gbps/Full - flow control rx/tx
```

`ip addr` showed DHCP assignment:

```text
eth0: 192.168.0.110/24 dynamic
```

WSL2 successfully connected to the board:

```bash
ssh root@192.168.0.110
```

The board SD boot partition was browsed remotely:

```bash
cd /run/media/boot-mmcblk1p1
ls -al
```

This confirms the development loop can now be:

```text
WSL2 build -> scp artifacts to board -> sync -> reboot -> UART boot log verification
```

## Decision

Use wired Ethernet as the primary deploy path when available.

```text
Board IP observed: 192.168.0.110
Target path:       /run/media/boot-mmcblk1p1/
```

Use Wi-Fi AP later as an optional fallback path. It is not required for the immediate U-Boot iteration loop.

Keep SD boot mode switch settings aligned with the SK-AM64B quick guide. The corrected switch setting restored `wlan0`, which indicates the boot mode configuration can affect U-Boot FDT fixups and Linux-visible peripheral status.

## Assumption

- The current board is SK-AM64B / AM642 SK.
- The active Linux DTB is `/boot/dtb/ti/k3-am642-sk.dtb`.
- The wired IP address `192.168.0.110` is DHCP-assigned and may change after lease renewal, router reboot, or network change.
- `root` SSH login is acceptable for this lab bring-up environment.

## Open Question

- Which exact U-Boot source function or board fixup path changes `mmc@fa10000/status` based on BootMode switch state?
- Is the observed MMC0 disable behavior expected TI U-Boot behavior for the wrong backup boot mode setting, or a side effect of a particular self-built configuration?
- Should the repository later contain a generalized `setup/` guide for network deployment over SSH/SCP?

## Action Item

### Verify current boot mode and Wi-Fi state after each switch change

```bash
cat /proc/device-tree/bus@f4000/mmc@fa10000/status
ip link show wlan0
dmesg | grep -Ei "mmc0|sdio|wlcore|wl18|firmware"
```

Expected healthy state:

```text
mmc@fa10000/status = okay
mmc0: new SDIO card at address 0001
wlcore / wl18xx firmware boot messages appear
wlan0 exists
```

### Deploy U-Boot artifacts from WSL2

From:

```text
~/ti/am64x/build/u-boot-sdk12/artifacts/
```

Run:

```bash
scp tiboot3.bin tispl.bin u-boot.img root@192.168.0.110:/run/media/boot-mmcblk1p1/
ssh root@192.168.0.110 "sync && reboot"
```

### Optional deploy script

```bash
#!/usr/bin/env bash
set -euo pipefail

BOARD_IP="${1:-192.168.0.110}"
BOOT_DIR="/run/media/boot-mmcblk1p1"

scp tiboot3.bin tispl.bin u-boot.img "root@${BOARD_IP}:${BOOT_DIR}/"
ssh "root@${BOARD_IP}" "cd ${BOOT_DIR} && sync && ls -l tiboot3.bin tispl.bin u-boot.img && reboot"
```

### Stronger artifact verification

On WSL2:

```bash
sha256sum tiboot3.bin tispl.bin u-boot.img
```

On board:

```bash
ssh root@192.168.0.110 \
  "sha256sum /run/media/boot-mmcblk1p1/tiboot3.bin \
             /run/media/boot-mmcblk1p1/tispl.bin \
             /run/media/boot-mmcblk1p1/u-boot.img"
```

## Board Note

### SK-AM64B boot mode switch issue

A wrong SD boot switch configuration caused `wlan0` to disappear because the running Device Tree had:

```text
/bus@f4000/mmc@fa10000/status = disabled
```

After changing `SW2.4` to ON according to the SD boot mode setting, `wlan0` appeared again.

Practical implication:

```text
BootMode switch setting is not only a Boot ROM concern.
It may affect U-Boot board logic and Linux FDT fixups.
Always verify Linux running DT after changing boot switches.
```

### Network state

Wired Ethernet on `eth0` works with DHCP through the current LAN/hub setup:

```text
eth0: Link Up, 1Gbps/Full
IP: 192.168.0.110/24
```

This enables remote SSH/SCP access from WSL2.

## Artifact

Suggested repository file:

```text
docs/boards/SK-AM64B/2026-05-12_sd-bootmode-network-deploy.md
```

Suggested optional raw-log file:

```text
docs/bringup-logs/2026-05-12_SK-AM64B_sd-bootmode-network-deploy-log.md
```

Suggested commit message:

```text
docs: SK-AM64B SD 부트모드와 네트워크 배포 절차 정리
```
