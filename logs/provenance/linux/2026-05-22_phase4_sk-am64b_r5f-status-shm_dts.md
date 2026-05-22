# Linux provenance - 2026-05-22 phase4 SK-AM64B r5f-status-shm DTS

## 대상 변경

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-sk.dts
```

추가 node:

```text
r5f-status-shm@a5800000
  reg  = 0xa5800000 size 0x1000
  type = shared-dma-pool
  attr = no-map
```

## workspace 상태

```text
workspace path : /home/nstel/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12
branch         : ti-linux-6.18.y
head           : c214492085504176b9c252a7175e4e60b4b442af
baseline tag   : ti-sdk-12.00.00.07.04-baseline
dirty file     : arch/arm64/boot/dts/ti/k3-am642-sk.dts
```

## export 상태

```text
main repo patch : bsp/linux/patches/0001-arm64-dts-ti-k3-am642-sk-add-r5f-status-shm.patch
series entry    : bsp/linux/patches/series
```

## build / deploy 메모

실검증 과정에서는 다음을 수행했다.

1. workspace DTS 기반으로 `dtc` 검증
2. `install-kernel-to-sd.sh ... dtb-only --reboot` 수행
3. running DT에 SHM node가 바로 반영되지 않아, 검증에 사용한 DTB를 `/boot/dtb/ti/k3-am642-sk.dtb`로 수동 반영 후 재부팅
4. 이후 reserved-memory 반영 확인

## 실보드 결과

최종 실보드 기준 확인:

```text
/sys/firmware/devicetree/base/reserved-memory/r5f-status-shm@a5800000 존재
reg = 0xa5800000 / 0x1000
/proc/iomem : 9e800000-a5800fff : reserved
```

상세 로그:

```text
docs/bringup-logs/2026-05-22_SK-AM64B_phase4_shm_vtm_live_validation.md
```

## 주의

```text
old DTB 상태에서 new Phase 4 firmware를 boot하면 a5800000가 System RAM일 수 있다.
따라서 DTB 선반영이 필수다.
```
