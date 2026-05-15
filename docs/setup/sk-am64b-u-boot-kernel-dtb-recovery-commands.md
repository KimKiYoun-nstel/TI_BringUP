# SK-AM64B U-Boot Kernel/DTB 복구 명령 템플릿

## 목적

이 문서는 Linux까지 정상 진입하지 못하고 **U-Boot prompt까지는 진입 가능한 상황**에서,

- SD 내부 golden kernel/DTB 세트를 사용해 복구 부팅하는 방법
- Host PC의 TFTP server에서 kernel/DTB를 받아 RAM에서 부팅하는 방법

을 현재 repo 기준으로 정리한 command template 문서이다.

## 전제

현재 baseline boot flow는 다음과 같다.

```text
boot device: mmc 1
boot partition in U-Boot: 1:2
kernel path: /boot/Image
dtb path: /boot/dtb/ti/k3-am642-sk.dtb
rootfs: PARTUUID=076c4a2a-02
console: ttyS2,115200n8
```

현재 U-Boot env에서 이미 확인된 대표 load address:

```text
loadaddr = 0x82000000
fdtaddr  = 0x88000000
```

## 사용 목적 구분

### A. SD 내부 golden 세트 수동 복구

다음 경우 사용한다.

- bootloader는 정상
- U-Boot prompt까지는 진입 가능
- SD 내부의 active kernel/DTB가 실패한 것으로 의심됨
- 같은 SD 안에 golden 세트가 존재함

### B. TFTP RAM boot 복구

다음 경우 사용한다.

- bootloader는 정상
- U-Boot prompt까지는 진입 가능
- SD 내부의 kernel/DTB 배치가 꼬였거나 golden 세트 사용이 어렵다
- Host PC TFTP server를 사용할 수 있다

## 1. SD 내부 golden 세트로 수동 복구 부팅

현재 권장 golden 경로:

```text
/boot/Image.golden
/boot/dtb/ti/k3-am642-sk.dtb.golden
```

U-Boot prompt template:

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

의미:

```text
kernel: golden kernel 사용
dtb:    golden dtb 사용
rootfs: 기존 SD rootfs 사용
```

## 2. SD 내부에서 golden kernel만 사용

DTB는 현재 active를 유지하고, kernel만 golden으로 부팅하고 싶을 때:

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb
booti 0x82000000 - 0x88000000
```

## 3. SD 내부에서 golden DTB만 사용

kernel은 현재 active를 유지하고, DTB만 golden으로 부팅하고 싶을 때:

```bash
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image
load mmc 1:2 0x88000000 /boot/dtb/ti/k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

이 template은 **DTB-only 실험 실패 복구**에 가장 직접적으로 대응한다.

## 4. TFTP를 이용한 kernel+DTB RAM 부팅

Host PC에 TFTP server가 준비되어 있고, TFTP root에 다음 파일이 있다고 가정한다.

```text
Image.golden
k3-am642-sk.dtb.golden
```

U-Boot prompt template:

```bash
setenv ipaddr 192.168.0.110
setenv serverip <HOST_PC_IP>
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
tftp 0x82000000 Image.golden
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

주의:

- `ipaddr`는 현재 보드의 recovery용 임시 IP로 다시 지정해도 된다.
- `<HOST_PC_IP>`는 TFTP server를 띄운 Host PC IP로 바꿔야 한다.
- rootfs는 여전히 SD의 `PARTUUID=076c4a2a-02`를 사용한다.

## 5. TFTP를 이용한 DTB-only RAM 부팅

kernel은 SD의 active Image를 유지하고, DTB만 TFTP에서 받아 쓰고 싶을 때:

```bash
setenv ipaddr 192.168.0.110
setenv serverip <HOST_PC_IP>
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

## 6. TFTP를 이용한 golden kernel + test DTB 조합

필요 시 다음과 같은 조합도 가능하다.

```bash
setenv ipaddr 192.168.0.110
setenv serverip <HOST_PC_IP>
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
load mmc 1:2 0x82000000 /boot/Image.golden
tftp 0x88000000 k3-am642-sk.dtb
booti 0x82000000 - 0x88000000
```

즉 TFTP는 “모든 것을 외부에서 받는 방식”뿐 아니라, **golden + test 조합 실험**에도 활용 가능하다.

## 7. 복구 후 Linux 진입 뒤 해야 할 일

Linux까지 올라오면 즉시 다음을 수행한다.

```text
1. active kernel/DTB 상태 확인
2. golden 파일과 active 파일 비교
3. 필요 시 restore-golden* mode로 active 복구
4. 문제 원인 로그 보존
```

예:

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden
./tools/install/install-kernel-to-sd.sh 192.168.0.110 restore-golden-dtb
```

## 8. 한계와 주의사항

- 현재 문서는 command template이다. 아직 실제 U-Boot prompt에서 end-to-end 실증 로그는 없다.
- TFTP recovery는 Ethernet 링크, IP 설정, TFTP root 경로, 방화벽 상태에 영향을 받는다.
- DTB-only 문제라고 생각해도 실제로는 kernel config 또는 initramfs/rootfs 문제일 수 있다.
- bootloader 문제라면 이 문서가 아니라 **OSPI recovery 경로**를 우선 사용해야 한다.

## 9. 한 줄 요약

```text
U-Boot prompt가 살아 있으면,
SD 내부 golden 세트 또는 Host PC TFTP를 이용해
kernel/DTB를 RAM으로 로드하여 복구 부팅할 수 있다.
```
