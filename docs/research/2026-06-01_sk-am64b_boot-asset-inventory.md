# 2026-06-01 SK-AM64B Boot Asset Inventory

## 목적

이 문서는 이번 bring-up/boot 실험 과정에서 repo에 누적된 자산을
다음 기준으로 분류한다.

1. **채택 유지**
2. **실험 자산이지만 보관 가치 있음**
3. **현재 선택한 부트 경로와 어긋나는 잔여물 / 재검토 필요**

핵심 목표는 단순히 "USB vs SD 결과"를 요약하는 것이 아니라,
**TI SDK 원본 대비 실제로 무엇을 바꿨는지**와
**어떤 파일이 현재 성공 경로에 기여했고 어떤 파일은 중간 실험 잔여물인지**를 정리하는 것이다.

---

## 분류 기준

### A. 채택 유지

현재 시점의 성공 경로 또는 baseline 이해에 직접 필요한 자산.

### B. 실험 자산이지만 보관 가치 있음

현재 최종 경로에는 직접 쓰이지 않더라도,
원인 분석/재현성/향후 회귀 비교를 위해 보관 가치가 있는 자산.

### C. 재검토 필요

현재 최종 경로와 직접 맞지 않거나,
중간 실험 전용인데 사용 의도가 불명확해진 자산.
삭제 또는 archive 이동 후보.

---

## 1. Bootloader / USB boot 관련 자산

### 채택 유지

#### [docs/boards/SK-AM64B/boot-flow-baseline.md](/home/nstel/ti/TI_Bringup/docs/boards/SK-AM64B/boot-flow-baseline.md)

- baseline SD boot source of truth
- 현재 TI-style mmc/env 부트 경로 이해에 필요

#### [docs/boards/SK-AM64B/usb-rom-boot-prep.md](/home/nstel/ti/TI_Bringup/docs/boards/SK-AM64B/usb-rom-boot-prep.md)

- USB ROM boot media preparation
- `sda1` self-contained ROMBOOT 구조
- SPL/U-Boot patch 적용 이력 기록

#### [docs/research/2026-06-01_sk-am64b_sd-vs-usb-boot-status.md](/home/nstel/ti/TI_Bringup/docs/research/2026-06-01_sk-am64b_sd-vs-usb-boot-status.md)

- SD baseline vs USB-only autoboot 비교
- TI prebuilt 대비 차이
- SD inserted/absent 의미 정리

#### [tools/build/build-u-boot.sh](/home/nstel/ti/TI_Bringup/tools/build/build-u-boot.sh)

- current reproducible U-Boot build entrypoint
- watchdog-enabled A53 build option 포함

#### [tools/install/prepare-sk-am64b-usb-rom-boot-media.sh](/home/nstel/ti/TI_Bringup/tools/install/prepare-sk-am64b-usb-rom-boot-media.sh)

- 현재 성공 구조에 맞춘 USB media staging helper
- `sda1` ROMBOOT + `sda2` BOOT 동시 관리

#### [bsp/u-boot/dts/k3-am642-sk-u-boot-usbrom.dtsi](/home/nstel/ti/TI_Bringup/bsp/u-boot/dts/k3-am642-sk-u-boot-usbrom.dtsi)

- USB ROM boot rehearsal용 SPL DTS override trace
- `usb2-only`, host, high-speed, no usb3 phy path

#### [bsp/u-boot/patches/9999-sk-am64b-usb-boot-policy-rehearsal.patch](/home/nstel/ti/TI_Bringup/bsp/u-boot/patches/9999-sk-am64b-usb-boot-policy-rehearsal.patch)

- USB-first boot policy separation의 intent 기록
- 현재는 patch text 자체가 "rehearsal" 성격이지만,
  boot policy 분리 개념을 문서화하는 가치가 있다.

#### [bsp/u-boot/patches/0003-am64x-sk-u-boot-force-usb2-high-speed-host-path.patch](/home/nstel/ti/TI_Bringup/bsp/u-boot/patches/0003-am64x-sk-u-boot-force-usb2-high-speed-host-path.patch)

- 현재 U-Boot workspace diff에서 replay 가치가 있는 SPL DTS override를 patch로 승격한 것
- clean baseline에서 SK USB ROM boot SPL path를 다시 만들 때 필요

#### [bsp/u-boot/patches/0004-usb-cdns3-skip-usb3-phy-in-usb2-only-mode.patch](/home/nstel/ti/TI_Bringup/bsp/u-boot/patches/0004-usb-cdns3-skip-usb3-phy-in-usb2-only-mode.patch)

- 현재 U-Boot workspace diff에서 replay 가치가 있는 Cadence core driver patch를 patch로 승격한 것
- `usb2-only` path를 code level에서 재현할 때 필요

#### [bsp/u-boot/patches/series](/home/nstel/ti/TI_Bringup/bsp/u-boot/patches/series)

- 기존 0001/0002에 더해 0003/0004를 추가함
- 다만 9999 policy patch는 아직 rehearsal 성격이 강해 series 밖에 둔 상태

#### [logs/provenance/u-boot/2026-06-01_sk-am64b-usb-rom-boot-driver-experiment.md](/home/nstel/ti/TI_Bringup/logs/provenance/u-boot/2026-06-01_sk-am64b-usb-rom-boot-driver-experiment.md)

- Cadence core driver 실험 provenance
- bootloader 변경의 이유와 범위를 기록

### 실험 자산이지만 보관 가치 있음

#### [bsp/u-boot/configs/am64x-watchdog.config](/home/nstel/ti/TI_Bringup/bsp/u-boot/configs/am64x-watchdog.config)

- watchdog 실험 cycle에 중요
- USB/SD 어느 경로에서도 수동 실험에 재사용 가능

#### [docs/boards/SK-AM64B/usb-boot-experiment-cycle.md](/home/nstel/ti/TI_Bringup/docs/boards/SK-AM64B/usb-boot-experiment-cycle.md)

- 단일 실험 cycle 정의
- 현재는 USB root/rootwait/N17 계열에서 유도되었지만,
  watchdog 기반 boot experiment 일반 규칙으로 보관 가치 있음

### 재검토 필요

#### [tools/install/set-uenv-rehearsal-mode.sh](/home/nstel/ti/TI_Bringup/tools/install/set-uenv-rehearsal-mode.sh)

- SD FAT `uEnv.txt` override 전환 helper
- 현재 최종 성공 USB-only autoboot는 `sda1` extlinux 기준이므로,
  이 helper는 USB-only final path와는 직접 맞지 않음
- 유지할지, “legacy rehearsal helper” 로만 남길지 재검토 필요

#### [boot-configs/uenv/*](/home/nstel/ti/TI_Bringup/boot-configs/uenv)

- 대부분 SD baseline 위에 임시 rehearsal command를 얹는 구조
- 최종 USB-only self-contained extlinux 경로와 직접 맞지 않음
- 중간 실험 재현에는 유용하지만 최종 path 기준으론 legacy 성격

---

## 2. kernel / DTB / initramfs 관련 자산

### 채택 유지

#### [tools/build/build-kernel.sh](/home/nstel/ti/TI_Bringup/tools/build/build-kernel.sh)

- USB boot config fragment merge path 포함
- 현재 USB 실험 kernel build 재현에 필요

#### [bsp/linux/configs/am64x-usb-boot.config](/home/nstel/ti/TI_Bringup/bsp/linux/configs/am64x-usb-boot.config)

- USB storage boot에 필요한 built-in kernel config 집합
- 성공 경로를 설명할 때 유지 필요

#### [bsp/linux/dts/k3-am642-sk-usb-root.dts](/home/nstel/ti/TI_Bringup/bsp/linux/dts/k3-am642-sk-usb-root.dts)

- USB root rehearsal용 DT trace
- 최종 autoboot는 `k3-am642-sk.dtb` 이름을 사용했지만,
  중간 실험을 재현할 때 필요

#### [bsp/linux/patches/0002-arm64-dts-ti-k3-am642-sk-add-usb-root-variant.patch](/home/nstel/ti/TI_Bringup/bsp/linux/patches/0002-arm64-dts-ti-k3-am642-sk-add-usb-root-variant.patch)

- 현재 kernel workspace의 replay 가치가 있는 diff를 patch로 승격한 것
- `k3-am642-sk-usb-root.dts`와 Makefile build entry를 baseline에서 다시 적용 가능하게 함

#### [bsp/linux/patches/series](/home/nstel/ti/TI_Bringup/bsp/linux/patches/series)

- 기존 `r5f-status-shm` patch에 이어 USB-root variant patch를 추가함

### 실험 자산이지만 보관 가치 있음

#### [bsp/linux/configs/am64x-usb-root-diag-initramfs.config](/home/nstel/ti/TI_Bringup/bsp/linux/configs/am64x-usb-root-diag-initramfs.config)

- N17 initramfs 진입 실험용
- 최종 USB-only autoboot에 direct input은 아니지만,
  pre-root 관찰 자산으로 가치 있음

#### [rootfs/initramfs/sk-am64b-usb-root-diag/init.c](/home/nstel/ti/TI_Bringup/rootfs/initramfs/sk-am64b-usb-root-diag/init.c)

- `/init` 기반 pre-root USB readiness 관찰 실험 자산

#### [tools/build/build-sk-am64b-usb-root-diag-initramfs.sh](/home/nstel/ti/TI_Bringup/tools/build/build-sk-am64b-usb-root-diag-initramfs.sh)

- 위 initramfs build helper

#### [tools/install/install-sk-am64b-usb-root-diag-initramfs.sh](/home/nstel/ti/TI_Bringup/tools/install/install-sk-am64b-usb-root-diag-initramfs.sh)

- N17 initramfs deploy helper

#### [tools/install/install-sk-am64b-usb-root-n17-assets.sh](/home/nstel/ti/TI_Bringup/tools/install/install-sk-am64b-usb-root-n17-assets.sh)

- N17 kernel/DTB/initramfs sample deployment용

#### [boot-configs/uenv/usb-manual-load-n17-initramfs.uEnv.txt](/home/nstel/ti/TI_Bringup/boot-configs/uenv/usb-manual-load-n17-initramfs.uEnv.txt)

- N17 전용 manual rehearsal asset

#### [docs/research/2026-06-01_sk-am64b_usb-root-next-actions.md](/home/nstel/ti/TI_Bringup/docs/research/2026-06-01_sk-am64b_usb-root-next-actions.md)

- N16/N17 가설과 결과 정리

#### [docs/research/2026-05-28_sk-am64b_usb-boot-case-matrix.md](/home/nstel/ti/TI_Bringup/docs/research/2026-05-28_sk-am64b_usb-boot-case-matrix.md)

- 실패/성공 케이스 matrix
- 장기 보관 가치 높음

### 재검토 필요

#### [tools/install/install-extlinux-rehearsal-assets.sh](/home/nstel/ti/TI_Bringup/tools/install/install-extlinux-rehearsal-assets.sh)

- `usb` target은 원래 `sda2` USB-BOOT rehearsal 구조를 전제로 함
- 현재 최종 성공 구조는 `sda1` self-contained extlinux라 directly aligned 되지 않음
- helper를 새 성공 구조에 맞게 확장할지, legacy rehearsal helper로 둘지 결정 필요

#### [tools/install/prepare-usb-rehearsal-media.sh](/home/nstel/ti/TI_Bringup/tools/install/prepare-usb-rehearsal-media.sh)

- `sda3` rootfs 복제 자체는 여전히 유효
- 다만 “SD bootloader + USB kernel/rootfs” 실패 경로에서 출발한 helper라 설명 정리가 더 필요

#### [docs/setup/sk-am64b-extlinux-pxe-rehearsal.md](/home/nstel/ti/TI_Bringup/docs/setup/sk-am64b-extlinux-pxe-rehearsal.md)

- SD extlinux / USB extlinux / PXE rehearsal 전체를 다룸
- 현재 최종 성공 path는 이 문서의 초기 가정 중 일부를 이미 넘어섰음
- final chosen path와의 관계를 보강하거나 archival note를 붙일 필요 있음

---

## 3. rootfs overlay / service / unrelated-but-modified 자산

### 실험 자산이지만 보관 가치 있음

#### [rootfs/overlay/](/home/nstel/ti/TI_Bringup/rootfs/overlay)
#### [rootfs/overlays/](/home/nstel/ti/TI_Bringup/rootfs/overlays)

- 현재 대화에서 직접 USB boot 성공에 기여한 것으로 입증된 것은 아님
- 그러나 repo 운영상 rootfs overlay area는 별도 목적이 있으므로 삭제 대상은 아님

### 재검토 필요

#### `rpmsg`, `lab service policy`, `phase4`, `r5f` 관련 deploy/test 스크립트들

- 예: `tools/install/test-sk-am64b-rpmsg.sh` 등
- 현재 USB/SD boot 경로 정리와 직접 관련은 약함
- boot summary 문서에는 “non-boot related assets”로 분리 기재하는 편이 좋음

---

## 4. 실질적인 keep / remove recommendation

### Keep as adopted

- `docs/boards/SK-AM64B/boot-flow-baseline.md`
- `docs/boards/SK-AM64B/usb-rom-boot-prep.md`
- `docs/research/2026-06-01_sk-am64b_sd-vs-usb-boot-status.md`
- `tools/build/build-u-boot.sh`
- `tools/build/build-kernel.sh`
- `tools/install/prepare-sk-am64b-usb-rom-boot-media.sh`
- `bsp/u-boot/dts/k3-am642-sk-u-boot-usbrom.dtsi`
- `bsp/u-boot/patches/0003-am64x-sk-u-boot-force-usb2-high-speed-host-path.patch`
- `bsp/u-boot/patches/0004-usb-cdns3-skip-usb3-phy-in-usb2-only-mode.patch`
- `bsp/u-boot/patches/series`
- `bsp/linux/configs/am64x-usb-boot.config`
- `bsp/linux/patches/0002-arm64-dts-ti-k3-am642-sk-add-usb-root-variant.patch`
- `bsp/linux/patches/series`

### Keep as experiment history

- `docs/research/2026-05-28_sk-am64b_usb-boot-case-matrix.md`
- `docs/research/2026-06-01_sk-am64b_usb-root-next-actions.md`
- `docs/boards/SK-AM64B/usb-boot-experiment-cycle.md`
- `rootfs/initramfs/*`
- `tools/build/build-sk-am64b-usb-root-diag-initramfs.sh`
- `tools/install/install-sk-am64b-usb-root-diag-initramfs.sh`
- `tools/install/install-sk-am64b-usb-root-n17-assets.sh`
- `boot-configs/uenv/usb-manual-load-n17-initramfs.uEnv.txt`

### Rework or mark as legacy

- `tools/install/install-extlinux-rehearsal-assets.sh`
- `tools/install/set-uenv-rehearsal-mode.sh`
- `boot-configs/uenv/*` (except N17-specific if needed)
- `docs/setup/sk-am64b-extlinux-pxe-rehearsal.md`

이 자산들은 삭제보다는,
현재 최종 USB-only path 이전의 **legacy rehearsal path** 로 라벨링하는 것이 더 안전하다.

---

## 5. 현재 가장 정확한 정리

```text
1. TI baseline은 SD-first env boot policy다.
2. 현재 성공한 USB boot는 단순 fallback이 아니라,
   USB-specific media layout + U-Boot USB-first policy build까지 포함한 별도 경로다.
3. SD bootloader + USB kernel/rootfs 조합은 최종 채택 경로가 아니며,
   관련 자산 상당수는 experimental/legacy classification이 맞다.
4. 따라서 지금 필요한 것은 USB-only success path를 채택 자산으로 고정하고,
   그 외 실험 자산은 history/legacy로 재라벨링하는 것이다.
```

---

## 6. clean baseline 재시작 관점의 현재 상태

현재 시점에서는 다음 문장이 성립한다.

```text
workspace diff를 그대로 끌고 가지 않더라도,
repo 안의 patch/config/dts/docs/provenance 자산만으로
TI SDK baseline clean tree 위에 필요한 변경을 다시 적용할 수 있는 방향으로
정리가 진행된 상태다.
```

다만 주의점은 다음과 같다.

1. 문서/patch 승격은 많이 진행되었지만, 모든 실험 자산이 final adopted path인 것은 아니다.
2. 특히 `9999-sk-am64b-usb-boot-policy-rehearsal.patch` 는 아직 series에 넣지 않은 rehearsal patch다.
3. clean restart에서 어떤 patch를 base로 볼지 별도 정책 결정이 필요하다.

## 7. 현재 최종 base workspace 정의

사용자 요구 기준의 base workspace는 다음처럼 정리되었다.

### U-Boot base workspace

목표:

```text
1. bootdelay = 5
2. SD-first boot policy 유지
3. watchdog는 source patch가 아니라 build option/config fragment로 활성화
```

현재 실제 workspace 상태:

```text
branch: base-sd-watchdog
HEAD: ecaf8c660ef (bootdelay=5 patch 적용 상태)
status: clean
```

즉 U-Boot base workspace는 **baseline + bootdelay 5 patch만 적용된 clean 상태**다.

watchdog는 workspace source diff가 아니라 다음 build 경로로 얻는다.

```text
tools/build/build-u-boot.sh all-watchdog
bsp/u-boot/configs/am64x-watchdog.config
```

따라서 현재 U-Boot base의 본질은:

```text
source tree = SD-first baseline 유지
build option = watchdog enabled build 가능
```

### kernel base workspace

목표:

```text
USB boot 실험용 DTS/config는 workspace에 남기지 않음
repo 자산으로만 관리
```

현재 실제 workspace 상태:

```text
branch: base-clean
HEAD: c214492085504176b9c252a7175e4e60b4b442af
status: clean
```

즉 kernel base workspace는 **TI SDK baseline clean 상태**다.

### base replay 기준

이제 clean baseline에서 다시 시작할 때는 다음처럼 이해하면 된다.

```text
U-Boot base:
  series에 포함된 것은 현재 0002 (bootdelay 5)만 적용
  watchdog는 build option/config fragment로 활성화

kernel base:
  series 미적용 clean baseline 유지

USB 실험 자산:
  repo patch/config/dts/doc/helper로만 선택 적용
```

즉 현재는:

1. base workspace는 최대한 얇게 유지
2. USB 실험 변경은 repo 자산으로만 보관
3. 필요 시 clean baseline 위에 선택 적용

하는 운영 모델로 정리된 상태다.

```text
U-Boot base:
  0002 + watchdog config fragment

kernel base:
  no patch

USB-specific experiments:
  0003/0004, linux 0002, media/scripts/docs를 선택 적용
```

처럼 **base와 experiment를 분리**해서 선택 적용하면 된다.
