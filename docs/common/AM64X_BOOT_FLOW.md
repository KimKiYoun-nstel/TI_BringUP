# AM64x Boot Flow

AM64x 계열 Embedded Linux 부팅 흐름을 Board Bring-up 관점에서 정리합니다.

## 전체 흐름

```text
Power On
  -> Boot ROM
  -> SPL / tiboot3 / initial bootloader stage
  -> U-Boot proper
  -> Linux Kernel + Device Tree
  -> RootFS
  -> User space
```

## 단계별 확인 포인트

| 단계 | 역할 | 실패 시 의심 지점 |
|---|---|---|
| Boot ROM | boot mode에 따라 boot media 선택 | boot switch, boot media, image format |
| SPL | DDR/clock/pinmux 등 초기화 | DDR 설정, board config, PMIC/power, UART pinmux |
| U-Boot | kernel/dtb/rootfs 로딩 | env, storage, network, bootcmd |
| Kernel | driver probe, filesystem mount | device tree, driver config, clock/reset, pinmux |
| RootFS | init/systemd 실행 | rootfs path, filesystem, init, service |

## 로그 분석 기준

- 아무 로그도 없음:
  - 전원, UART 연결, boot mode, boot image 위치 확인
- SPL 로그까지만 나옴:
  - DDR 초기화, 다음 stage image 로딩 확인
- U-Boot prompt까지 나옴:
  - bootcmd, kernel image, dtb, rootfs 설정 확인
- Kernel panic:
  - rootfs mount, init, device tree, driver probe 확인
