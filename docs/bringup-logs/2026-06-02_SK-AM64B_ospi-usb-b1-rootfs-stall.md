# 2026-06-02 SK-AM64B OSPI bootloader + USB Linux B1 결과

## 목적

OSPI에 기록된 부트로더로 부팅한 뒤, SD card absent / USB inserted 조건에서
USB의 kernel + DTB + rootfs로 Linux가 이어서 부팅되는지 확인한다.

이번 기록은 B1 실험 결과만 남긴다.

## 실험 조건

```text
Board: SK-AM64B / AM64B-SKEVM rev A
Boot mode: OSPI
SD card: absent
USB media: inserted
Expected rootfs: PARTUUID=2bcf5ad2-03
```

## UART 관찰 결과

확인된 순서는 다음과 같다.

```text
U-Boot SPL ...
Trying to boot from SPI
...
U-Boot 2026.01...
...
MMC: no card present
MMC: no card present
** Bad device specification mmc 1 **
MMC: no card present
** Bad device specification mmc 1 **
Couldn't find partition mmc 1:2
Can't set block device
```

이후 Linux kernel log가 실제로 이어졌다.

```text
xhci-hcd ... Host Controller
usbcore: registered new interface driver usb-storage
...
Waiting for root device PARTUUID=2bcf5ad2-03...
```

추가 관찰 시간 동안 다음 문자열은 보이지 않았다.

```text
VFS: Mounted root
Kernel panic
resetting ...
```

## 단계별 판단

이번 실험에서 확인된 사실은 다음과 같다.

1. OSPI bootloader chain은 정상이다.
2. SD absent 조건에서 baseline MMC 경로는 예상대로 실패한다.
3. 그 이후 kernel 자체는 시작된다.
4. 최종 rootfs mount 단계에서 `PARTUUID=2bcf5ad2-03` 대기 상태로 정지한다.

즉 이번 결과는 다음으로 정리할 수 있다.

```text
Bootloader success
  -> kernel start success
  -> USB rootfs mount not completed
```

## 기존 실험과의 관계

이 증상은 기존 `SD bootloader + USB (kernel + rootfs)` 계열 실험에서 반복적으로 보였던
`Waiting for root device PARTUUID=2bcf5ad2-03...` 패턴과 같은 계열이다.

따라서 이번 결과는 `OSPI bootloader` 자체의 문제라기보다,
현재 조건에서 `USB kernel + USB rootfs` 경로가 최종 root mount까지 안정적으로 이어지지 않는다는
증거로 취급한다.

## 결론

이번 B1 실험은 성공으로 보지 않는다.

```text
OSPI bootloader + USB Linux path:
kernel 진입까지는 확인
USB rootfs mount 완료는 미확인
실사용 경로로 채택하지 않음
```

현재 운용 결론:

- OSPI는 recovery / baseline bootloader path로 유지한다.
- USB는 독립 USB-only 부팅 경로로만 취급한다.
- `OSPI bootloader + USB kernel/rootfs` 조합은 현 시점에서 추가 추적 우선순위를 낮춘다.
