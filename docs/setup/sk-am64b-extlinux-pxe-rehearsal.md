# SK-AM64B extlinux / PXE 리허설 가이드

## 목적

이 문서는 현재 **env 기반 SD boot baseline을 폐기하지 않고**, extlinux/PXE 경로를 추가 리허설하는 절차를 정리한다.

이 문서의 기본 전제는 다음과 같다.

```text
공식 baseline:
  SD card + U-Boot env + /boot/Image + /boot/dtb/ti/k3-am642-sk.dtb + SD rootfs

리허설 목표:
  1. SD extlinux boot 확인
  2. USB extlinux + USB rootfs boot 확인
  3. PXE(TFTP kernel/DTB + NFS rootfs) 경로 준비
```

## 현재 확인된 사실

- 보드 SSH: `root@192.168.0.110` 접속 가능
- 현재 `/proc/cmdline`: `root=PARTUUID=076c4a2a-02`
- 현재 rootfs: `/dev/mmcblk1p2`
- USB:
  - `/dev/sda2` = `USB-BOOT`
  - `/dev/sda3` = `usb-rootfs`
- host TFTP:
  - `tftpd-hpa` active
  - root = repo의 `tftp/`
- host NFS:
  - 아직 설치/활성화되지 않음

## 왜 `uEnv.txt`를 쓰는가

현재 보드는 persistent U-Boot env를 Linux에서 직접 다루기 어렵고, 실제 boot log에서도 `Loaded env from uEnv.txt`가 확인되어 있다.

따라서 rehearsal에서는 다음 원칙을 사용한다.

```text
1. extlinux/PXE asset는 별도 파일로 준비
2. SD FAT partition의 uEnv.txt 에 임시 uenvcmd 를 넣어 rehearsal 경로를 먼저 시도
3. rehearsal command가 실패하면 기존 bootcmd_ti_mmc 경로가 계속 실행되도록 유지
4. 검증 후 uEnv.txt 를 baseline-empty 상태로 복원
```

## SD extlinux 리허설

SD extlinux는 FAT partition이 아니라 **현재 실제 kernel/DTB가 있는 rootfs `/boot` 경로**를 사용한다.

이유:

- 현재 baseline artifact와 경로를 그대로 재사용할 수 있다.
- FAT partition에 DTB를 중복 복사하지 않아도 된다.

배치:

```text
/boot/extlinux/extlinux.conf
kernel=/boot/Image
fdt=/boot/dtb/ti/k3-am642-sk.dtb
root=PARTUUID=076c4a2a-02
```

절차:

```bash
./tools/install/install-extlinux-rehearsal-assets.sh 192.168.0.110 sd
./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 sd-extlinux
ssh root@192.168.0.110 reboot
```

성공 확인:

```bash
cat /proc/cmdline
findmnt /
```

주의:

- SD extlinux 성공은 **baseline replacement 승인**이 아니다.
- 우선은 extlinux path도 현재 SD 구조를 재현할 수 있다는 증명만 의미한다.

## USB extlinux + USB rootfs 리허설

### 1. USB rootfs 준비

```bash
./tools/install/prepare-usb-rehearsal-media.sh 192.168.0.110
```

### 2. USB boot asset 준비

```bash
./tools/install/install-extlinux-rehearsal-assets.sh 192.168.0.110 usb
```

배치 결과:

```text
/run/media/USB-BOOT-sda2/Image
/run/media/USB-BOOT-sda2/k3-am642-sk.dtb
/run/media/USB-BOOT-sda2/extlinux/extlinux.conf
```

현재 1차 리허설에서는 USB root 지정을 다음처럼 고정한다.

```text
root=PARTUUID=2bcf5ad2-03
```

이유:

```text
root=LABEL=usb-rootfs 시도에서
"Disabling rootwait; root= is invalid"
"VFS: Cannot open root device ... unknown-block(0,0)"
panic이 관찰되었기 때문이다.

이후 root=/dev/sda3 시도에서는 panic 대신
"Waiting for root device /dev/sda3..."
상태로 멈췄다.

현재 보드에서는 USB xHCI/USB storage enumeration이 늦게 올라오는 정황이 있으므로,
PARTUUID + rootdelay=30 조합으로 다시 시도한다.
```

### 3. USB-first rehearsal 활성화

```bash
./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 usb-extlinux
ssh root@192.168.0.110 reboot
```

성공 확인:

```bash
cat /proc/cmdline
findmnt /
lsblk -f
```

성공 기준:

```text
root=PARTUUID=2bcf5ad2-03
/ 가 usb-rootfs partition 으로 mount
```

실패 시 기대 fallback:

```text
USB extlinux 경로 실패
-> uenvcmd 종료
-> 기존 bootcmd_ti_mmc 경로 실행
-> SD rootfs 로 부팅
```

### 4. USB extlinux 실패 시 분리 진단

USB extlinux 자산은 준비되어 있는데 실제 reboot 후 여전히 SD로 복귀하면, 실패 지점을 두 층으로 나눠 본다.

```text
1. bootflow/extlinux discovery 실패
2. USB kernel/DTB load 또는 usb-rootfs mount 실패
```

이를 분리하기 위해 manual USB load 모드를 별도로 사용한다.

```bash
./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 usb-manual
ssh root@192.168.0.110 reboot
```

이 모드는 `uenvcmd`에서 다음을 직접 수행한다.

```text
usb start
load usb 0:2 ${loadaddr} /Image
load usb 0:2 ${fdtaddr} /k3-am642-sk.dtb
bootargs=root=PARTUUID=2bcf5ad2-03 rootdelay=30 ...
booti
```

판정:

- manual USB mode 성공 + USB extlinux mode 실패
  - USB boot 자체는 가능
  - extlinux discovery/path/bootflow 쪽 문제일 가능성 높음

- manual USB mode도 실패
  - U-Boot USB load 또는 kernel rootfs mount 쪽 문제를 우선 의심

## PXE(TFTP + NFS rootfs) 리허설

현재 session에서는 다음까지 준비 가능하다.

- TFTP root = repo `tftp/`
- `tftp/pxelinux.cfg/default` 생성
- `uEnv.txt`에 `dhcp; pxe get; pxe boot` rehearsal command 주입

그러나 실제 `NFS rootfs` boot 성공 검증은 아직 block 상태다.

이유:

```text
host 에 nfs-kernel-server / rpcbind 미설치
passwordless sudo 없음
```

따라서 PXE/NFS는 현재 다음 상태로 분류한다.

```text
TFTP/PXE asset 준비 가능
NFS rootfs 실증은 host 권한 확보 후 진행 필요
```

## 복원

리허설 후 항상 baseline `uEnv.txt`로 되돌린다.

```bash
./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 baseline
```

## 한 줄 결론

```text
이 리허설의 목적은 baseline 교체가 아니라,
현 구조 위에서 extlinux/PXE/USB/NFS path가 추가로 가능한지 증명 자산을 만드는 것이다.
```

## USB root 전용 DTB variant

USB rootfs boot가 다음 단계까지 좁혀졌다면:

```text
- U-Boot는 USB storage를 읽을 수 있음
- USB BOOT / USB rootfs 내용도 존재함
- SD의 known-good kernel+DTB + USB rootfs 조합도 userspace까지 못 감
- rootdelay 증가로도 해결되지 않음
```

다음 원인 후보는 early USB host/PHY/SerDes bring-up 이다.

이를 분리하기 위해 workspace에는 다음 전용 DTS variant를 추가한다.

```text
arch/arm64/boot/dts/ti/k3-am642-sk-usb-root.dts
```

의도:

```text
- baseline k3-am642-sk.dts 유지
- USB root rehearsal에서만 USB3/SerDes 경로 의존성 축소
- usbss0에 ti,usb2-only 부여
- usb0를 host/high-speed로 고정
- usb3 phy(phys/phy-names) override 제거
```

빌드 예:

```bash
./tools/build/build-kernel.sh dtbs
```

생성 기대 파일:

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-sk-usb-root.dtb
```

이 DTB는 USB root rehearsal에서만 사용하고, 현재 baseline DTB인
`k3-am642-sk.dtb`는 그대로 유지한다.
