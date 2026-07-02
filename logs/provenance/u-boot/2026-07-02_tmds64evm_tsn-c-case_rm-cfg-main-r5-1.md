# 2026-07-02 TMDS64EVM TSN C Case U-Boot RM ownership fix

## 대상 변경

```text
workspace/ti-u-boot-sdk12/board/ti/am64x/rm-cfg.yaml
```

## workspace 상태

```text
workspace path : /home/nstel/ti/TI_Bringup/workspace/ti-u-boot-sdk12
branch         : base-sd-watchdog
head           : ecaf8c660ef
dirty file     : board/ti/am64x/rm-cfg.yaml
```

## export 상태

```text
main repo patch : bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch
series entry    : not added
```

`series`에 넣지 않은 이유:

- 이 변경은 TMDS64EVM TSN C Case용 resource sharing 정책이다.
- baseline 전체 replay 기본값으로 바로 올리기보다, project-specific patch로 먼저 보관한다.

## 변경 요지

`ICSSG_1 PKTDMA` 관련 resource를 baseline `A53_2 (12)`에 남겨두고,
동일 range를 `MAIN_0_R5_1 (36)`에도 추가 배정했다.

대상 resource:

```text
PKTDMA_RING_ICSSG_1_TX_CHAN
PKTDMA_RING_ICSSG_1_RX_CHAN
PKTDMA_ICSSG_1_TX_CHAN
PKTDMA_ICSSG_1_RX_CHAN
PKTDMA_FLOW_ICSSG_1_RX_CHAN
```

## build / deploy 메모

적용 명령 기준:

```bash
git -C workspace/ti-u-boot-sdk12 apply \
  bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch

tools/build/build-u-boot.sh
tools/install/install-bootloader-to-sd.sh
```

재빌드 artifact:

```text
out/u-boot/artifacts/tiboot3.bin
out/u-boot/artifacts/tispl.bin
out/u-boot/artifacts/u-boot.img
```

실보드 반영 경로:

```text
/run/media/boot-mmcblk1p1/tiboot3.bin
/run/media/boot-mmcblk1p1/tispl.bin
/run/media/boot-mmcblk1p1/u-boot.img
```

## 실보드 결과

`k3conf dump rm` 기준으로 `ICSSG_1 PKTDMA` range에
`A53_2`와 `MAIN_0_R5_1`가 동시에 표시되는 것을 확인했다.

이후 Path B firmware boot에서 기존 blocker였던
`EnetUdma_openRxCh` / `Enet_open failed`는 재현되지 않았다.
