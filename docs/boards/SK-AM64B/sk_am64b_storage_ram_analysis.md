# SK-AM64B 보드 RAM / SD 카드 / Flash 저장공간 분석 노트

## 1. 분석 대상

보드 부팅 후 확인한 Linux 파일시스템 및 블록 디바이스 상태를 기준으로, SK-AM64B 보드에서 다음 항목을 구분한다.

- RAM, 즉 LPDDR4 메인 메모리
- microSD 카드의 boot/rootfs 파티션
- OSPI Flash 영역
- Linux 가상 파일시스템 및 tmpfs 영역
- `/`, `/tmp`, `/run`, `/var/volatile` 등의 실제 저장 위치

이 문서는 TI AM64x 계열 보드 브링업 관점에서, 현재 보드가 어떤 저장장치에서 부팅했고 어떤 영역이 휘발성/비휘발성인지 이해하기 위한 정리 문서이다.

---

## 2. 현재 확인된 디스크/파티션 상태

### 2.1 `lsblk -f` 결과

```text
NAME        FSTYPE FSVER LABEL UUID                                 FSAVAIL FSUSE% MOUNTPOINTS
mtdblock0
mtdblock1
mtdblock2
mtdblock3
mtdblock4
mtdblock5
mtdblock6
mmcblk1
|-mmcblk1p1 vfat         boot  384E-543A                              94.3M    26% /run/media/boot-mmcblk1p1
`-mmcblk1p2 ext4         root  7a81c518-bc75-4400-aaa9-69af7ec61b74   19.3G    28% /
```

### 2.2 `findmnt /` 결과

```text
TARGET SOURCE         FSTYPE OPTIONS
/      /dev/mmcblk1p2 ext4   rw,relatime
```

### 2.3 `/proc/cmdline` 결과

```text
console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait
```

### 2.4 `df -h` 결과

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        29G  8.0G   20G  30% /
devtmpfs        921M     0  921M   0% /dev
tmpfs           938M     0  938M   0% /dev/shm
tmpfs           375M  9.1M  366M   3% /run
tmpfs           938M  4.0K  938M   1% /tmp
none            1.0M     0  1.0M   0% /run/credentials/systemd-journald.service
tmpfs           938M  4.0K  938M   1% /var/volatile
none            1.0M     0  1.0M   0% /run/credentials/systemd-resolved.service
none            1.0M     0  1.0M   0% /run/credentials/systemd-networkd.service
none            1.0M     0  1.0M   0% /run/credentials/serial-getty@ttyS2.service
none            1.0M     0  1.0M   0% /run/credentials/getty@tty1.service
/dev/mmcblk1p1  128M   34M   95M  27% /run/media/boot-mmcblk1p1
tmpfs           188M  4.0K  188M   1% /run/user/0
```

---

## 3. 핵심 결론

현재 SK-AM64B 보드는 microSD 카드에서 부팅되어 있으며, SD 카드의 두 파티션이 다음과 같이 사용되고 있다.

```text
/dev/mmcblk1
├── /dev/mmcblk1p1  vfat  LABEL=boot  → boot 파티션
└── /dev/mmcblk1p2  ext4  LABEL=root  → root filesystem 파티션
```

현재 root filesystem은 `/dev/mmcblk1p2`이며, Linux에서는 `/dev/root`로도 표시된다.

```text
/dev/root = /dev/mmcblk1p2 = SD 카드의 rootfs 파티션
```

따라서 `/` 전체의 기본 저장 위치는 SD 카드의 ext4 파티션이다. 다만 `/tmp`, `/run`, `/dev`, `/var/volatile` 등 일부 디렉터리는 부팅 후 RAM 기반 파일시스템 또는 커널 가상 파일시스템으로 별도 mount되어 SD 카드 영역이 아니다.

---

## 4. RAM의 의미

여기서 말하는 RAM은 일반적인 장비에서 말하는 DDR RAM과 같은 개념이다.

SK-AM64B 보드 기준으로는 다음을 의미한다.

```text
보드 위에 실장된 2GB LPDDR4 메모리
```

이 RAM은 AM64x SoC 내부에 포함된 대용량 메모리가 아니다. AM64x SoC 외부에 별도 LPDDR4 메모리 칩으로 실장되어 있으며, AM64x의 DDR 컨트롤러를 통해 접근된다.

개념적으로는 다음과 같다.

```text
[AM64x SoC]
   |
   | DDR/LPDDR4 interface
   |
[외부 LPDDR4 2GB memory]
```

PC에 비유하면 다음과 같다.

```text
CPU  = AM64x SoC
RAM  = 보드 위 LPDDR4 2GB
SSD  = microSD / OSPI Flash
```

---

## 5. SK-AM64B의 RAM 용량

SK-AM64B 보드의 메인 RAM 용량은 다음과 같다.

```text
2GB LPDDR4
```

Linux에서 `tmpfs` 크기가 약 938MB로 보이는 것은 전체 RAM이 938MB라는 의미가 아니다. 일반적으로 Linux는 tmpfs의 기본 최대 크기를 전체 사용 가능 RAM의 약 절반 수준으로 잡는다.

```text
tmpfs 약 938MB × 2 ≈ 약 1.8GB
```

실제 2GB 전체가 Linux `MemTotal`로 그대로 보이지 않는 이유는 일부 메모리가 다음 용도로 예약되기 때문이다.

- Linux kernel
- device tree reserved-memory
- CMA 영역
- remoteproc/R5F/M4F firmware 영역
- secure firmware 또는 bootloader가 예약한 영역
- framebuffer 또는 DMA buffer 용도

확인 명령은 다음과 같다.

```sh
free -h
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|CmaTotal|CmaFree"
dmesg | grep -iE "memory|ddr|lpddr|cma"
```

---

## 6. OSPI Flash와 RAM의 차이

RAM과 OSPI Flash는 완전히 다른 성격의 메모리이다.

| 구분 | SK-AM64B에서의 예 | 휘발성 | 주요 용도 |
|---|---|---:|---|
| RAM | 2GB LPDDR4 | 전원 차단 시 사라짐 | Linux 실행 메모리, 프로세스, page cache, tmpfs |
| microSD | `/dev/mmcblk1` | 전원 차단 후 유지 | boot partition, root filesystem |
| OSPI Flash | `/dev/mtdblock0` ~ `/dev/mtdblock6` | 전원 차단 후 유지 | 부트로더 저장, flash boot, firmware 저장 |
| SoC 내부 SRAM | AM64x 내부 SRAM | 전원 차단 시 사라짐 | Boot ROM/SPL 초기 단계, R5F/MCU 일부 용도 |

현재 `lsblk -f`에서 확인된 `mtdblock0` ~ `mtdblock6`는 OSPI Flash 영역으로 판단된다.

```text
mtdblock0
mtdblock1
mtdblock2
mtdblock3
mtdblock4
mtdblock5
mtdblock6
```

이들은 RAM이 아니라 비휘발성 Flash 계열 저장장치이다.

OSPI 파티션 이름은 다음 명령으로 확인한다.

```sh
cat /proc/mtd
```

---

## 7. `/` 아래 경로별 실제 저장 위치

현재 `/`는 `/dev/mmcblk1p2`에 mount되어 있으므로 기본적으로 SD 카드 rootfs 영역이다.

그러나 일부 디렉터리는 별도 파일시스템이 mount되어 있다. 이 경우 해당 디렉터리 아래는 SD 카드가 아니라 별도 mount된 파일시스템을 사용한다.

### 7.1 SD 카드에 저장되는 영역

다음 경로들은 기본적으로 `/dev/mmcblk1p2` ext4 rootfs에 저장된다.

```text
/etc
/home
/root
/usr
/opt
/var
/boot
/bin  -> /usr/bin
/sbin -> /usr/sbin
/lib  -> /usr/lib
```

예를 들어 다음 파일은 SD 카드에 저장되며 재부팅 후에도 유지된다.

```sh
echo "sd test" > /root/sd-test.txt
sync
reboot
```

재부팅 후 확인:

```sh
cat /root/sd-test.txt
```

### 7.2 RAM 기반 영역

다음 경로들은 RAM 기반 또는 커널 가상 파일시스템이다.

```text
/dev
/dev/shm
/run
/tmp
/var/volatile
/run/user/0
```

예를 들어 다음 파일들은 재부팅 후 사라진다.

```sh
echo "ram test" > /tmp/ram-test.txt
echo "run test" > /run/run-test.txt
echo "volatile test" > /var/volatile/volatile-test.txt
sync
reboot
```

재부팅 후 확인:

```sh
ls /tmp/ram-test.txt
ls /run/run-test.txt
ls /var/volatile/volatile-test.txt
```

### 7.3 커널 가상 파일시스템

다음 경로들은 실제 저장장치가 아니라 커널이 제공하는 가상 정보 인터페이스이다.

```text
/proc
/sys
```

예:

```text
/proc/cpuinfo
/proc/meminfo
/sys/class/...
```

이 파일들은 SD 카드에도 RAM 파일로도 저장되는 일반 파일이 아니라, 커널 내부 상태를 파일처럼 보여주는 인터페이스이다.

---

## 8. `df -h`를 기준으로 한 판단법

Linux에서 어떤 경로가 SD 카드인지 RAM인지 판단할 때는 `ls -al /`의 출력만 보면 안 된다.

가장 중요한 기준은 다음이다.

```text
df -h 또는 findmnt에서 별도 mount point로 보이는 경로는 별도 파일시스템이다.
```

현재 기준으로 보면 다음과 같다.

| Mount point | Filesystem | 실제 위치 | 재부팅 후 유지 여부 |
|---|---|---|---|
| `/` | `/dev/mmcblk1p2` ext4 | SD 카드 rootfs | 유지 |
| `/run/media/boot-mmcblk1p1` | `/dev/mmcblk1p1` vfat | SD 카드 boot 파티션 | 유지 |
| `/dev` | devtmpfs | RAM/커널 device filesystem | 재생성 |
| `/dev/shm` | tmpfs | RAM | 사라짐 |
| `/run` | tmpfs | RAM | 사라짐 |
| `/tmp` | tmpfs | RAM | 사라짐 |
| `/var/volatile` | tmpfs | RAM | 사라짐 |
| `/run/user/0` | tmpfs | RAM | 사라짐 |
| `/proc` | procfs | 커널 가상 파일시스템 | 실제 저장 없음 |
| `/sys` | sysfs | 커널 가상 파일시스템 | 실제 저장 없음 |

---

## 9. `/boot`와 `/run/media/boot-mmcblk1p1`의 차이

현재 SD 카드에는 boot 파티션과 root 파티션이 따로 있다.

```text
/dev/mmcblk1p1  → vfat boot 파티션
/dev/mmcblk1p2  → ext4 rootfs 파티션
```

따라서 다음 두 경로는 서로 다르다.

```text
/boot
/run/media/boot-mmcblk1p1
```

`/boot`는 `/dev/mmcblk1p2` rootfs 안에 존재하는 일반 디렉터리이다.

반면 `/run/media/boot-mmcblk1p1`는 `/dev/mmcblk1p1` boot 파티션이 자동 mount된 위치이다.

확인 명령:

```sh
ls -al /boot
ls -al /run/media/boot-mmcblk1p1
find /run/media/boot-mmcblk1p1 -maxdepth 2 -type f -print
```

AM64x SD 부팅에서는 보통 boot 파티션에 다음과 같은 파일들이 위치할 수 있다.

```text
tiboot3.bin
tispl.bin
u-boot.img
Image
*.dtb
uEnv.txt
boot.scr
extlinux/extlinux.conf
```

단, 현재 보드에서는 다음 경로가 존재하지 않았다.

```text
/run/media/boot-mmcblk1p1/extlinux/extlinux.conf
```

따라서 현재 이미지는 `extlinux.conf` 방식이 아니라 `uEnv.txt`, `boot.scr`, 또는 U-Boot 환경변수 기반으로 kernel/DTB를 로딩하고 있을 가능성이 있다.

---

## 10. Board Bring-up 관점에서의 의미

현재 상태는 SD 카드 부팅 경로가 정상적으로 동작하고 있음을 의미한다.

부팅 흐름 관점에서는 다음 단계가 통과된 상태이다.

```text
Boot ROM
  ↓
SPL / tiboot3.bin
  ↓
DDR/LPDDR4 초기화
  ↓
U-Boot
  ↓
Linux Kernel + Device Tree
  ↓
/dev/mmcblk1p2 rootfs mount
  ↓
systemd/userspace 진입
```

특히 Linux shell까지 정상 진입했기 때문에 다음 항목은 1차적으로 정상이라고 판단할 수 있다.

- Boot mode 설정
- SD 카드 인식
- SPL 로딩
- LPDDR4 초기화
- U-Boot 실행
- Kernel 로딩
- Device Tree 적용
- MMC1 SD interface 동작
- ext4 root filesystem mount
- userspace 실행

---

## 11. 로그 저장 시 주의사항

Board Bring-up 중 로그를 저장할 때는 저장 위치를 주의해야 한다.

### 11.1 재부팅 후 사라지는 위치

```sh
dmesg > /tmp/dmesg.log
journalctl > /run/journal.log
```

위와 같은 위치는 RAM 기반이므로 재부팅 후 사라질 수 있다.

### 11.2 재부팅 후 유지되는 위치

```sh
mkdir -p /root/logs
dmesg > /root/logs/dmesg.log
journalctl -b > /root/logs/journal-current-boot.log
sync
```

`/root`, `/home`, `/opt`, `/etc` 등은 SD 카드 rootfs에 저장되므로 재부팅 후에도 유지된다.

단, SD 카드 wear를 줄이기 위해 대량 로그를 지속적으로 쓰는 경우에는 별도 저장 정책이 필요하다.

---

## 12. 추가 확인 명령 모음

### 12.1 SD 카드 파티션 확인

```sh
lsblk -f
findmnt /
mount | grep mmc
cat /proc/cmdline
```

### 12.2 RAM 확인

```sh
free -h
cat /proc/meminfo | head -30
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|CmaTotal|CmaFree"
```

### 12.3 부팅 로그에서 메모리/MMC 확인

```sh
dmesg | grep -iE "memory|ddr|lpddr|cma"
dmesg | grep -iE "mmc|sdhci|root|EXT4|VFS"
```

### 12.4 OSPI Flash 확인

```sh
cat /proc/mtd
ls -al /dev/mtd*
```

### 12.5 boot 파티션 확인

```sh
ls -al /run/media/boot-mmcblk1p1
find /run/media/boot-mmcblk1p1 -maxdepth 2 -type f -print
```

---

## 13. 최종 요약

현재 SK-AM64B 보드는 microSD 카드의 `/dev/mmcblk1p2`를 root filesystem으로 사용 중이다.

```text
/dev/root = /dev/mmcblk1p2 = SD 카드 rootfs
```

`/` 아래 대부분의 일반 디렉터리는 SD 카드에 저장되지만, `/tmp`, `/run`, `/dev`, `/var/volatile` 등은 부팅 후 RAM 기반 파일시스템 또는 커널 가상 파일시스템으로 별도 mount된다.

RAM은 AM64x SoC 내부의 대용량 메모리가 아니라, 보드 위에 실장된 외부 2GB LPDDR4 메모리이다. OSPI Flash는 이 RAM과 다르며, 전원 차단 후에도 내용이 유지되는 비휘발성 Flash 저장장치이다.

Board Bring-up 관점에서 현재 상태는 SD 부팅, LPDDR4 초기화, kernel 로딩, rootfs mount, userspace 진입이 정상적으로 완료된 상태로 볼 수 있다.
