# SK-AM64B R5F Early Boot Runtime Dependency Map

## 목적

이 문서는 `SBL OSPI Linux`가 성공한 뒤,
그 이후 Linux prompt까지 이어지는 runtime dependency가 어디에 걸려 있는지 정리한다.

핵심 질문:

```text
이 프로젝트에서 bootloader 이후 kernel / DTB / rootfs / bootcmd 가 의미 있게 동작하는가?
```

답:

```text
그렇다.
다만 SBL-side App_loadLinuxImages failure root cause와,
그 이후 Linux boot/runtime dependency는 분리해서 봐야 한다.
```

## 1. 현재 검증된 큰 흐름

현재 validated 흐름은 다음 두 구간으로 나뉜다.

### A. project-managed early boot chain

```text
OSPI SBL
  -> OSPI linux appimage 내부 BL31 / OP-TEE / A53 SPL load
  -> U-Boot SPL
  -> U-Boot proper
```

이 구간의 핵심 issue는 이전에 `App_loadLinuxImages status=-1` 였고,
현재는 clean canonical set에서 이 구간이 통과함을 확인했다.

### B. post-SBL Linux boot/runtime chain

```text
U-Boot proper boot policy
  -> kernel / FDT selection
  -> rootfs mount
  -> systemd/services
  -> remoteproc attach / RPMsg / checker app behavior
```

이 구간은 SBL 내부 image load 성공 이후의 dependency다.

## 2. 현재 U-Boot proper에서 의미 있는 부분

현재 local A53 chain output에서 확인된 default boot command:

```text
CONFIG_BOOTCOMMAND="run envboot; run bootcmd_ti_mmc; bootflow scan -lb"
```

즉 현재 validated Linux boot는
U-Boot proper가 SD/MMC 쪽 boot asset을 계속 활용하는 구조다.

현재 board 확인 결과:

- `/run/media/boot-mmcblk1p1/uEnv.txt`
  - comment-only
  - 강한 override를 하지 않음
- `/run/media/boot-mmcblk1p1/EFI/BOOT/grub.cfg`
  - `linux /Image root=PARTUUID=076c4a2a-02 rootwait rootfstype=ext4 console=ttyS2,115200`

즉 현재 Linux boot는 다음 dependency를 가진다.

```text
OSPI에서 A53 chain까지 살아난 뒤,
실제 kernel/rootfs 진입은 SD boot asset과 boot policy에 다시 의존한다.
```

## 3. kernel / DTB / rootfs 가 왜 의미가 있나

### kernel

현재 running kernel:

```text
Linux 6.18.13-gc21449208550
```

이 kernel은 이후 remoteproc attach, reserved-memory 해석, IPC-only attach behavior에 직접 영향이 있다.

### DTB

U-Boot log에는 FDT load가 분명히 보인다.

```text
Working FDT set to 88000000
Loading Device Tree ...
```

즉 DTB selection path도 post-bootloader chain의 일부다.
현재 boot partition top-level에서 명시적인 `.dtb` 파일을 바로 찾지는 못했지만,
실제 boot에서는 FDT가 로드되고 있으므로 boot asset path에 포함된 dependency로 봐야 한다.

### rootfs

현재 rootfs:

- `/dev/mmcblk1p2 on /`
- kernel cmdline의 `root=PARTUUID=076c4a2a-02`

이 rootfs는 다음에 영향을 준다.

- 로그인 prompt 도달 여부
- remoteproc attach 후 user-space 관찰 환경
- checker app 실행 경로
- systemd 서비스와 baseline noise

## 4. 그래서 이 프로젝트에서 무엇이 project scope 인가

### project의 direct scope

- SBL / R5F / A53 chain image generation과 deploy set 관리
- `App_loadLinuxImages`가 통과하는 early boot chain closure
- 이후 custom R5F heartbeat / RPMsg follow-up

### project의 indirect but meaningful dependency

- U-Boot proper boot policy
- boot partition asset (`uEnv.txt`, `EFI/BOOT/grub.cfg`, `Image`, FDT path)
- kernel / rootfs 조합

## 5. 해석 원칙

현재 project에서 판단할 때는 다음처럼 나눠서 본다.

```text
1. SBL-side image load failure
   -> SBL / linux appimage lineage 문제로 우선 본다

2. SBL은 통과했는데 Linux prompt 이후 behavior가 다름
   -> U-Boot boot policy, kernel, DTB, rootfs, services 의존성까지 포함해서 본다
```

즉 `bootcmd / kernel / rootfs`는 현재 프로젝트에서 의미가 있다.
단, 그것이 항상 SBL-side root cause인 것은 아니다.
