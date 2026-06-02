# Boot Configs

이 디렉터리는 **현재 공식 baseline을 대체하지 않는** AM64x boot rehearsal 자산을 보관한다.

원칙:

- 현재 공식 baseline은 여전히 U-Boot env 기반 SD boot이다.
- 여기 있는 `extlinux.conf`, `pxelinux.cfg`, `uEnv.txt` 템플릿은 **리허설용**이다.
- 실보드에서 검증되기 전까지는 baseline replacement로 간주하지 않는다.
- `uEnv.txt` override는 임시 부팅 경로 전환용이며, 실패 시 기존 SD 경로로 복귀할 수 있어야 한다.

구성:

```text
boot-configs/
  extlinux/
  legacy/
    extlinux/
      sd/extlinux.conf
      usb/extlinux.conf
      tftp/pxelinux.cfg.default
  uenv/
    usb-manual-load-n17-initramfs.uEnv.txt
  legacy/
    uenv/
      baseline-empty.uEnv.txt
      sd-extlinux.uEnv.txt
      usb-extlinux.uEnv.txt
      usb-manual-load.uEnv.txt
      pxe-rehearsal.uEnv.txt
```

현재 기준:

- `legacy/` 아래 자산은 **이전 rehearsal path** 를 위한 archive 입니다.
- 현재 채택된 USB-only autoboot path는 `sda1` self-contained extlinux 구조이며,
  old `sd`/`usb`/`tftp` rehearsal extlinux/uEnv 자산은 direct adopted path가 아닙니다.

의도:

- `legacy/extlinux/sd/extlinux.conf`
  - SD rootfs의 `/boot/extlinux/extlinux.conf`로 배치
  - 현재 `/boot/Image`, `/boot/dtb/ti/k3-am642-sk.dtb`, `root=PARTUUID=...` 경로를 extlinux로 재현

- `legacy/extlinux/usb/extlinux.conf`
  - USB-BOOT FAT partition의 `/extlinux/extlinux.conf`로 배치
  - USB의 `Image`, `k3-am642-sk.dtb`, `root=PARTUUID=2bcf5ad2-03` 경로를 사용
  - 현재 보드에서는 `root=LABEL=usb-rootfs` 시도가 panic을 유발했고 `/dev/sda3`는 root wait hang으로 이어졌으므로, 1차 리허설은 PARTUUID + `rootdelay=30`으로 고정한다.

- `legacy/extlinux/tftp/pxelinux.cfg.default`
  - repo의 `tftp/pxelinux.cfg/default`로 배치
  - TFTP kernel/DTB + NFS rootfs 리허설용 PXE config

- `legacy/uenv/*.uEnv.txt`
  - SD FAT boot partition의 `uEnv.txt`에 임시로 복사해 `uenvcmd`를 통해 rehearsal path를 먼저 시도
  - command가 실패하면 이후 기본 `bootcmd_ti_mmc` 경로가 계속 실행되도록 설계
  - `usb-manual-load.uEnv.txt`는 bootflow/extlinux 탐색 문제가 있을 때 USB kernel/DTB를 명시적으로 load 하는 분리 진단용 템플릿이었다.

- `uenv/usb-manual-load-n17-initramfs.uEnv.txt`
  - N17 initramfs diagnostic 전용 실험 자산
  - 현재도 실험 history 보관 가치가 있어 active path 바깥에 남겨둔다.
