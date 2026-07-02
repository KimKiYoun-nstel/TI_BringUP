# AM64x TSN C Case C0 SDK Example Inventory

## 목적

이 문서는 C Case의 C0 단계로서, 현재 local `MCU+ SDK AM64x 12.00.00` 안에 `ICSSG gPTP` 관련 example이 실제로 존재하는지, 어떤 target으로 빌드되는지, 어떤 산출물을 내는지 정리한다.

## 결론 요약

- `gptp_icssg_switch` example이 존재한다.
- `gptp_icssg_dualmac` example이 존재한다.
- 두 example 모두 `am64x-evm`, `r5fss0-0_freertos`, `ti-arm-clang` target으로 local build 성공을 확인했다.
- 두 example 모두 `ICSSG1` RGMII1/RGMII2 pinmux를 전제로 한다.
- 다만 현재 source 흔적상 이 example들은 `Linux remoteproc` 전용 example이라기보다 `MCU+ SDK boot image / mcelf` 출력 중심이다.
- `resource_table` 흔적이 보이지 않아, `build success`와 `remoteproc load 가능`은 분리해서 다뤄야 한다.

## 확인한 example 위치

### switch

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/
  source/networking/enet/core/examples/tsn/
    gptp_icssg_app/gptp_icssg_switch/
      am64x-evm/r5fss0-0_freertos/ti-arm-clang/
```

### dualmac

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/
  source/networking/enet/core/examples/tsn/
    gptp_icssg_app/gptp_icssg_dualmac/
      am64x-evm/r5fss0-0_freertos/ti-arm-clang/
```

## build target 등록 상태

`makefile.am64x` 기준으로 두 example이 모두 정식 build combo에 등록되어 있다.

### target 이름

```text
gptp_icssg_switch_am64x-evm_r5fss0-0_freertos_ti-arm-clang
gptp_icssg_dualmac_am64x-evm_r5fss0-0_freertos_ti-arm-clang
```

## 실제 build command

SDK root에서 다음 명령으로 빌드했다.

```bash
make -f makefile.am64x gptp_icssg_switch_am64x-evm_r5fss0-0_freertos_ti-arm-clang
make -f makefile.am64x gptp_icssg_dualmac_am64x-evm_r5fss0-0_freertos_ti-arm-clang
```

## build 결과

### switch

- build log:
  - `projects/tsn_c_case/logs/2026-06-30_c0_build_gptp_icssg_switch.log`
- 확인한 산출물:
  - `gptp_icssg_switch.release.out`
  - `gptp_icssg_switch.release.map`
  - `gptp_icssg_switch.release.lnkxml`
  - `gptp_icssg_switch.release.mcelf.hs_fs`
  - `gptp_icssg_switch.release.mcelf_xip`

### dualmac

- build log:
  - `projects/tsn_c_case/logs/2026-06-30_c0_build_gptp_icssg_dualmac.log`
- 확인한 산출물:
  - `gptp_icssg_dualmac.release.out`
  - `gptp_icssg_dualmac.release.map`
  - `gptp_icssg_dualmac.release.lnkxml`
  - `gptp_icssg_dualmac.release.mcelf.hs_fs`
  - `gptp_icssg_dualmac.release.mcelf_xip`

### build 판정

- switch: 성공
- dualmac: 성공

## example 설정 차이

### 1. switch example

- `CONFIG_ENET_ICSS0`만 사용한다.
- `PRU_ICSS1` 단일 instance를 사용한다.
- `RGMII1`, `RGMII2` pin suggestion이 둘 다 들어 있다.
- app main은 `ENET_SYSCFG_NUM_PERIPHERAL == 1` 가정의 switch path를 사용한다.

의미:

- 하나의 `ICSSG1` instance를 switch 모드로 열고 두 MAC port를 함께 다루는 방향이다.

### 2. dualmac example

- `CONFIG_ENET_ICSS0`, `CONFIG_ENET_ICSS1` 두 peripheral을 만든다.
- 둘 다 `DUAL MAC` 모드다.
- 두 peripheral 모두 같은 `PRU_ICSS1` instance를 공유한다.
- `CONFIG_ENET_ICSS1` 쪽은 `dualMacPortSelected = ENET_MAC_PORT_2`로 설정된다.

의미:

- 하나의 `ICSSG1` 하드웨어를 Linux netdev 관점처럼 포트별로 쪼개어 다루는 구성에 가깝다.

## Linux/board 자산과의 대응

현재 TMDS Linux baseline에서는:

- `eth1`: CPSW
- `eth2`: ICSSG single EMAC

반면 Linux DTS에는 이미 다음 overlay가 있다.

- `k3-am642-evm-icssg1-dualemac.dtbo`

또한 TMDS live SD rootfs에는 이미 다음 PRU Ethernet firmware blob이 존재한다.

- `ti-pruss/am64x-sr2-pru0-prueth-fw.elf`
- `ti-pruss/am64x-sr2-rtu0-prueth-fw.elf`
- `ti-pruss/am64x-sr2-txpru0-prueth-fw.elf`
- `ti-pruss/am64x-sr2-pru1-prueth-fw.elf`
- `ti-pruss/am64x-sr2-rtu1-prueth-fw.elf`
- `ti-pruss/am64x-sr2-txpru1-prueth-fw.elf`

의미:

- **C1 Linux dual-port feasibility 확인만 놓고 보면**, bootloader 재빌드 없이 `DTB/DTBO 적용 경로`만 바꾸는 것으로 시도할 가능성이 높다.
- rootfs도 **PRU Ethernet firmware 기준으로는** 그대로 재사용 가능성이 높다.

## 사용자 질문에 대한 현재 답

### Q1. "icssg를 통해 eth1,2를 제어하는 건 linux dtb만 변경하면 되는 거겠지?"

현재 증거 기준 답:

- **C1 Linux dual-port enable 검증 범위라면 거의 그렇다.**
- 더 정확히는 `kernel DTB/DTBO + U-Boot에서 어떤 DTB/overlay를 올릴지`의 boot 설정 변경이 핵심이다.
- 즉 source 수정 관점에서는 `Linux DTS` 쪽이 맞고, bootloader binary 재빌드는 지금 단계에서 필요해 보이지 않는다.

주의:

- 지금 U-Boot env의 `name_overlays`에는 `onboard-clkgen`만 들어 있다.
- 따라서 실제 적용에는 다음 둘 중 하나가 필요하다.
  - `name_overlays`에 `k3-am642-evm-icssg1-dualemac.dtbo` 추가
  - pre-merged DTB를 별도로 사용

### Q2. "rootfs도 그대로여도 되고?"

현재 증거 기준 답:

- **C1까지는 대체로 그대로 갈 가능성이 높다.**
- 이유는 TMDS live rootfs에 이미 `ti-pruss/am64x-sr2-*prueth-fw.elf`들이 있기 때문이다.

단, **전체 C Case**로 가면 얘기가 달라진다.

- C2 이후 `Linux가 ICSSG를 잡지 않게` 바꾸는 단계
- C4 이후 `R5F firmware`를 `remoteproc`로 올리는 단계

에서는 custom firmware를 `/lib/firmware`에 두는 방식 등으로 rootfs 개입이 필요할 수 있다.

즉:

- `C1 Linux dual-port 확인`: rootfs 유지 가능성 높음
- `C4 remoteproc firmware load`: rootfs 변경 가능성 있음

### Q3. "부트로더도 재사용 가능할 거 같고"

현재 증거 기준 답:

- **예, C1 단계에서는 재사용 가능성이 높다.**
- 현재 U-Boot는 overlay 적용 메커니즘과 SD boot 경로를 이미 갖고 있다.
- 지금 필요한 건 bootloader binary 교체보다 `어떤 DTB/DTBO를 선택할지`다.

## remoteproc 관점의 주의점

현재 `gptp_icssg_*` source 아래에서는 `.resource_table` 흔적을 찾지 못했다.

의미:

- 이 example은 현재 확인 기준으로 `Linux remoteproc` 전용 예제가 아니다.
- `.out`, `.mcelf.hs_fs`가 만들어졌다고 해서 Linux에서 바로 `echo start > /sys/class/remoteproc/.../state` 할 수 있는 상태라고 보면 안 된다.

따라서 C0의 결론은 다음과 같다.

```text
example exists        = yes
local build succeeds  = yes
remoteproc-ready      = not yet proven
```

## C0 판정

### 확정

- `gptp_icssg_switch` 존재
- `gptp_icssg_dualmac` 존재
- local SDK에서 둘 다 빌드 성공
- TMDS Linux dual-port 검증에 필요한 DT overlay와 rootfs PRU firmware도 이미 존재

### 미확정

- Linux remoteproc load 가능성
- resource table 필요 여부
- firmware memory map과 Linux reserved-memory 정합성

## 다음 액션

1. `k3-am642-evm-icssg1-dualemac.dtbo` 적용 후 C1 재부팅 검증
2. `eth1` / `eth2`가 모두 `icssg-prueth`인지 확인
3. 그 뒤 C2 ownership 분리 초안으로 이동
