# Linux provenance - 2026-07-02 TMDS64EVM TSN C Case ICSSG1 R5F owner overlay

## 대상 변경

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/Makefile
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-evm-icssg1-r5f-owner.dtso
```

## workspace 상태

```text
workspace path : /home/nstel/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12
branch         : base-clean
head           : c2144920855
dirty files    :
  - arch/arm64/boot/dts/ti/Makefile
  - arch/arm64/boot/dts/ti/k3-am642-evm-icssg1-r5f-owner.dtso
```

## export 상태

```text
main repo patch : bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch
series entry    : not added
```

`series`에 넣지 않은 이유:

- 현재 실보드 성공 경로는 temporary U-Boot `fdt set` override 기반이다.
- 이 overlay는 같은 ownership 분리를 정식 DT 자산으로 재적용할 수 있게 보관한 것이다.

## overlay 내용

다음을 disable 한다.

```text
cpsw_port2
mdio_mux_1
icssg1_eth
```

또한 `/aliases`에서 `ethernet1`, `ethernet2`를 삭제해 Linux netdev alias 혼선을 줄인다.

## 검증 메모

적용 명령 기준:

```bash
git -C workspace/ti-linux-kernel-sdk12 apply \
  bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch

tools/build/build-kernel.sh
tools/install/install-kernel-to-sd.sh
```

실보드 bring-up 성공 자체는 이 overlay를 SD에 영구 반영하지 않고,
U-Boot에서 temporary `fdt set`를 적용하는 방식으로 수행했다.

따라서 현재 이 patch의 의미는 다음과 같다.

1. 검증에 사용한 DT change set의 repo 고정
2. 이후 persistent DTB/DTBO 경로로 옮길 때의 직접 적용 자산 확보
