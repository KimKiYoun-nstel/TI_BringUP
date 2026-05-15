# AM64x 부트 플로우 BASE

## 목적

이 문서는 현재 AM64x 브링업 작업에서 파이프라인의 출발점으로 삼을 부트 플로우 BASE를 정의한다.

이 BASE는 목표 구조나 이상적인 설계가 아니라, 다음 근거를 기반으로 실제로 관찰되고 검증된 상태이다.

- self-built U-Boot 부트 로그
- U-Boot `printenv`
- 현재 SK-AM64B 실보드 동작 상태

앞으로 부트 플로우를 변경할 때는 모두 이 BASE 대비 변경점으로 기록해야 한다.

## BASE 범위

현재 BASE는 다음 실사용 시작 상태를 의미한다.

```text
TI prebuilt SD card layout + 현재 U-Boot environment + 동작 중인 SK-AM64B 보드
```

즉, custom deploy 로직이나 test/golden 슬롯 구조를 도입하기 전의 빠른 시작 기준점이다.

## BASE 부트 체인

현재 관찰된 상위 부트 체인은 다음과 같다.

```text
Boot ROM
  -> tiboot3.bin
  -> tispl.bin
  -> u-boot.img
  -> U-Boot environment
  -> rootfs /boot 에서 kernel Image load
  -> rootfs /boot/dtb 에서 DTB load
  -> booti 로 kernel + FDT 실행
  -> Linux rootfs mount
```

## 실제 부트 정책의 기준점

현재 부트 정책의 1차 기준은 `extlinux.conf`가 아니라 U-Boot environment 이다.

보드에서 확인한 핵심 baseline 변수는 다음과 같다.

```text
boot=mmc
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
bootcmd_ti_mmc=... run get_kern_${boot}; run get_fdt_${boot}; run get_overlay_${boot}; run run_kern;
bootpart=1:2
bootdir=/boot
bootenvfile=uEnv.txt
bootmeths=script efi extlinux
fdtfile=ti/k3-am642-sk.dtb
get_kern_mmc=load mmc ${bootpart} ${loadaddr} ${bootdir}/${name_kern}; run load_initramfs_mmc
get_fdt_mmc=load mmc ${bootpart} ${fdtaddr} ${bootdir}/dtb/${fdtfile}
name_kern=Image
run_kern=booti ${loadaddr} ${rd_spec} ${fdtaddr}
```

## BASE의 실제 의미

현재 BASE에서는 U-Boot가 다음 파일을 직접 읽는다.

- kernel: `/boot/Image`
- DTB: `/boot/dtb/ti/k3-am642-sk.dtb`

그리고 이 파일들은 다음 rootfs partition 기준으로 로드된다.

```text
bootpart=1:2
```

즉, 현재 Linux의 주 부팅 경로는 FAT boot partition의 `extlinux.conf`에 의해 결정되지 않는다.

## 관찰 근거

### self-built U-Boot 부트 로그

확인된 순서는 다음과 같다.

```text
Loaded env from uEnv.txt
Importing environment from mmc1 ...
... kernel Image read ...
... DTB read ...
Booting using the fdt blob ...
Starting kernel ...
```

이 로그는 현재 성공 경로가 다음과 같음을 보여준다.

```text
U-Boot env -> kernel Image load -> DTB load -> booti
```

### 현재 실보드 상태

현재 보드에서 확인된 값은 다음과 같다.

```text
model: Texas Instruments AM642 SK
compatible: ti,am642-sk / ti,am642
console: ttyS2,115200n8
root: PARTUUID=076c4a2a-02
```

### 현재 미디어 레이아웃

현재 rootfs 측 boot 자산은 다음을 포함한다.

```text
/boot/Image
/boot/dtb/ti/k3-am642-sk.dtb
```

현재 FAT boot partition에는 다음과 같은 파일들이 있다.

```text
tiboot3.bin
tispl.bin
u-boot.img
uEnv.txt
EFI/BOOT/grub.cfg
```

하지만 현재 검증된 Linux 부팅 경로는 `extlinux.conf` 기반이 아니다.

## OSPI와 BASE의 관계

현재 BASE의 1차 실행 경로는 SD 기반이지만, SK-AM64B bring-up 운영에서는 OSPI Flash가 recovery anchor 역할을 가질 수 있다.

즉:

```text
일상적인 boot path는 SD 기준으로 본다.
하지만 SD bootloader 실험이 실패했을 때는 OSPI의 known-good bootloader가
복구 기준점으로 사용될 수 있다.
```

따라서 SD 부팅 경로를 파이프라인 BASE로 삼더라도, 반복 작업 관점에서는 OSPI write/use 전략을 별도로 문서화해야 한다.

## 중요한 BASE 주의사항

U-Boot가 읽는 DTB 파일은 baseline 입력값일 뿐이며, Linux가 실제로 받는 최종 running device tree는 U-Boot에 의해 수정될 수 있다.

이 차이는 SK-AM64B 브링업 과정에서 이미 관찰되었다.

따라서 다음을 항상 전제로 둔다.

```text
디스크 위 DTB 파일 != 최종 runtime FDT 보장
```

## BASE DTB

현재 파이프라인 작업에서 baseline Linux DTB는 다음으로 본다.

```text
/boot/dtb/ti/k3-am642-sk.dtb
```

이 값은 다음 작업의 출발점이다.

- DTB-only build
- DTB deploy 전략 수립
- runtime FDT 비교 작업

## 아직 BASE가 아닌 것

다음 항목들은 현재 BASE가 아니라 향후 선택지 또는 설계 목표이다.

- `extlinux.conf` 기반 golden/test entry
- FAT boot partition에서 DTB를 직접 선택하는 구조
- golden/test kernel 자동 전환
- 부트 정책 자체를 재작성하는 deploy script

## 변경 관리 규칙

앞으로 아래 항목 중 하나라도 바뀌면 boot-flow 변경으로 기록해야 한다.

- `bootcmd`
- `bootcmd_ti_mmc`
- `bootpart`
- `bootdir`
- `fdtfile`
- `get_kern_*`
- `get_fdt_*`
- `run_kern`
- kernel/DTB 실제 저장 위치
- Linux가 최종적으로 보게 되는 부팅 경로
