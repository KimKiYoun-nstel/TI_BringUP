# tools/install 실행 가이드

## 목적

이 문서는 `tools/install/` 아래 스크립트를 실제로 사용하는 작업자를 위한 짧은 operator guide이다.

여기서는:

- deploy 명령
- golden 승격/복구 명령
- U-Boot 수동 복구 command template 문서 위치

를 빠르게 찾을 수 있도록 정리한다.

## 주요 스크립트

### bootloader deploy

```bash
./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --dry-run
./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --reboot
```

### kernel/DTB deploy

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 all --dry-run
./tools/install/install-kernel-to-sd.sh 192.168.0.110 all --reboot
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
```

### kernel modules deploy

```bash
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy --dry-run
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy --verify-post-deploy
```

### golden 운용

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 promote-golden
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden-image
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden-dtb
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 promote-golden
./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 restore-golden
```

### post-deploy 검증

```bash
./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 all
./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 image-only
./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 dtb-only
./tools/install/verify-kernel-modules-postdeploy.sh 192.168.0.110 6.18.13-gc21449208550
```

## U-Boot 복구 command

아래 명령은 **U-Boot prompt에서 직접 copy & paste** 해서 사용하는 현재 기준 복구 템플릿이다.

### 1. SD golden kernel+DTB로 복구 부팅

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

### 2. SD golden kernel만 사용

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb
booti 0x82000000 - 0x88000000
```

### 3. SD golden DTB만 사용

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

### 4. TFTP kernel+DTB RAM boot

현재 확인된 host TFTP server IP 기준:

```text
HOST PC: 192.168.0.246
BOARD:   192.168.0.110
```

```bash
setenv ipaddr 192.168.0.110
setenv serverip 192.168.0.246
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
tftp 0x82000000 Image.golden
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

### 5. TFTP DTB-only RAM boot

```bash
setenv ipaddr 192.168.0.110
setenv serverip 192.168.0.246
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

### 6. TFTP test DTB + SD golden kernel 조합

```bash
setenv ipaddr 192.168.0.110
setenv serverip 192.168.0.246
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

주의:

- host IP가 바뀌면 `serverip`를 다시 바꿔야 한다.
- bootloader 문제일 때는 이 command보다 **OSPI recovery 경로**를 우선 사용한다.

## 사용 전 체크

- OSPI known-good bootloader 존재 여부 확인
- boot mode switch 현재 상태 기록
- UART 접근 가능 여부 확인
- 실제 overwrite 대상 경로 확인

## 한 줄 요약

```text
Linux가 살아 있으면 install script,
Linux가 죽고 U-Boot prompt가 살아 있으면 recovery command template을 사용한다.
```
