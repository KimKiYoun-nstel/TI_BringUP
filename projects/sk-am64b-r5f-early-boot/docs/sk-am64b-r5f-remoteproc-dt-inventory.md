# SK-AM64B R5F Remoteproc DT Inventory

## 목적

이 문서는 현재 local Linux DTS 기준으로
SK-AM64B의 R5F remoteproc / reserved-memory / mailbox 구성을 정리한다.

이 단계는 early boot attach 가능성 판단을 위한 inventory 이며,
DT patch를 아직 적용하지 않는다.

## 기준 파일

- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-sk.dts`
- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am64-main.dtsi`
- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am64-ti-ipc-firmware.dtsi`

## 핵심 구조

### 1. SK board DTS는 IPC firmware include를 사용한다

`k3-am642-sk.dts` 마지막에 다음 include가 들어간다.

```text
#include "k3-am64-ti-ipc-firmware.dtsi"
```

의미:

- SK-AM64B의 R5F enable 상태는 board DTS 본문만 보면 부족하다.
- 실제 `mboxes`, `memory-region`, `status = "okay"`는 include 파일까지 함께 봐야 한다.

### 2. SoC main dtsi의 기본 R5F node

`k3-am64-main.dtsi`에는 다음 node가 정의되어 있다.

| 항목 | 값 | 비고 |
|---|---|---|
| cluster | `main_r5fss0` | base `0x78000000` |
| core0 node | `main_r5fss0_core0` | `r5f@78000000` |
| core1 node | `main_r5fss0_core1` | `r5f@78200000` |
| core0 firmware-name | `am64-main-r5f0_0-fw` | local baseline firmware name |
| core1 firmware-name | `am64-main-r5f0_1-fw` | secondary core |

기본 main dtsi에서는 cluster/core status가 disabled 로 정의된다.

### 3. IPC firmware include가 status/memory/mailbox를 enable 한다

`k3-am64-ti-ipc-firmware.dtsi`에서 다음이 확인되었다.

| 항목 | 값 | 비고 |
|---|---|---|
| `&main_r5fss0` | `status = "okay"` | cluster enable |
| `&main_r5fss0_core0` | `status = "okay"` | core0 enable |
| `&main_r5fss0_core0` mailbox | `mailbox0_cluster2 + mbox_main_r5fss0_core0` | kick/notify 경로 |
| `&main_r5fss0_core0` memory-region | `a0000000` DMA + `a0100000` memory | core0 carveout |
| `&main_r5fss0_core1` | `status = "okay"` | core1 enable |
| `&main_r5fss1_core0/core1` | `status = "okay"` | r5fss1도 enable |

## reserved-memory inventory

현재 확인된 주요 carveout:

| 용도 | 주소 | 크기 | 출처 |
|---|---|---|---|
| `main_r5fss0_core0_dma_memory_region` | `0xa0000000` | `0x00100000` | `k3-am642-sk.dts` |
| `main_r5fss0_core0_memory_region` | `0xa0100000` | `0x00f00000` | `k3-am642-sk.dts` |
| `main_r5fss0_core1_dma_memory_region` | `0xa1000000` | `0x00100000` | `k3-am64-ti-ipc-firmware.dtsi` |
| `main_r5fss0_core1_memory_region` | `0xa1100000` | `0x00f00000` | `k3-am64-ti-ipc-firmware.dtsi` |
| `rtos_ipc_memory_region` | `0xa5000000` | `0x00800000` | `k3-am64-ti-ipc-firmware.dtsi` |

## mailbox inventory

현재 확인된 mailbox cluster:

| 항목 | 값 |
|---|---|
| core0 mailbox | `mailbox0_cluster2 / mbox_main_r5fss0_core0` |
| core1 mailbox | `mailbox0_cluster2 / mbox_main_r5fss0_core1` |

## firmware-name inventory

현재 baseline firmware-name:

| core | firmware-name |
|---|---|
| `78000000.r5f` | `am64-main-r5f0_0-fw` |
| `78200000.r5f` | `am64-main-r5f0_1-fw` |
| `78400000.r5f` | `am64-main-r5f1_0-fw` |
| `78600000.r5f` | `am64-main-r5f1_1-fw` |

## 판단

확정된 사실:

- SK-AM64B baseline DTS는 이미 R5F remoteproc + IPC firmware 경로를 enable 한다.
- core0 기준 firmware 이름과 memory-region, mailbox 구성이 source 상에 존재한다.

중요 해석:

- attach 목표라면 remoteproc node를 단순 disable 하는 접근은 맞지 않다.
- early boot 실험에서는 SBL/R5F/Linux가 같은 memory map을 보도록
  linker/resource table/reserved-memory를 맞추는 쪽이 핵심이다.

주의:

- `remoteproc1 == 78000000.r5f` 같은 index는 probe 순서에 따라 달라질 수 있다.
- 따라서 후속 service/script에서는 번호 고정보다 `name` 기반 확인이 바람직하다.
