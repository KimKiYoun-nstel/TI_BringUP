# AM64x TSN C Case C5 Path B Resource Ownership Audit v1

## 목적

Path 1 결과로 `PowerClock_init()` 단계의 `PRU_ICSSG1` clock request는
`remoteproc-hosted` 환경에서 app이 직접 다시 요청하면 안 되는 ownership/runtime model issue임이 확인됐다.

이 문서는 그 다음 단계인 Path 2 관점에서,

- donor `gptp_icssg_switch`가 어떤 resource를 직접 소유한다고 가정하는지
- 현재 TMDS Linux + remoteproc runtime이 무엇을 이미 소유/초기화하고 있는지
- Path B에서 어떤 항목을 `R5F_OWNS`, `PRECONFIGURED_BY_HOST`, `SKIP_IN_REMOTEPROC`로 봐야 하는지

를 1차 정리한 audit 문서다.

이번 v1의 초점은 현재 최신 blocker인

```text
EnetUdma_openRxCh
Enet_open failed
```

에 가장 직접 연결된 항목들이다.

## 현재 최신 사실

실보드에서 다음이 확인됐다.

1. U-Boot temporary `fdt set`는 실제 Linux DT에 반영된다.
2. `firmware-name = gptp_icssg_linux_remoteproc_r5f0_0_test.out` override도 정상 반영된다.
3. `module=82` clock request 전체를 remoteproc-hosted policy로 skip하면
   - `PowerClock_init clock set done`
   - `System_init call done`
   - `Board_init call done`
   - `Drivers_open done`
   - `Board_driversOpen done`
   - `EnetApp_mainTask entry`
   까지 진행된다.
4. 그 다음 최신 blocker는 다음이다.

```text
EnetUdma_openRxCh:2324
EnetHostPortDma_open:120
Icssg_openDma:743
Icssg_open:1075
EnetPer_open:1224
Enet_open failed
Assertion @ Line: 500 in syscfg/ti_enet_open_close.c
```

즉 현재 stop point는 clock set이 아니라 `Enet_open()` 내부의 DMA open path다.

## donor inventory 요약

기준 donor:

```text
workspace/mcu_plus_sdk_am64x_12_00_00_27/source/networking/enet/core/examples/tsn/
  gptp_icssg_app/gptp_icssg_switch/am64x-evm/r5fss0-0_freertos/ti-arm-clang/
```

### 1. clocks/power

donor는 다음을 직접 enable/configure한다고 가정한다.

- `I2C0`
- `I2C1`
- `PRU_ICSSG1`
- `UART0`

특히 `PRU_ICSSG1`에 대해 다음 clock request를 명시한다.

- `clk0 CORE = 333333333`, parent fixed
- `clk19 UCLK = 192000000`
- `clk3 IEP = 200000000`, parent fixed

근거:

- `.../generated/ti_power_clock_config.c`

### 2. pinmux

donor는 다음 pinmux를 직접 잡는 전제를 가진다.

- `I2C0`, `I2C1`
- `PRU_ICSSG1_MDIO0`
- `PRU_ICSSG1_IEP0`
- `PRU_ICSSG1_RGMII1` 전체
- `PRU_ICSSG1_RGMII2` 전체
- `UART0`
- `MCU_GPIO0_5`

근거:

- `.../generated/ti_pinmux_config.c`
- `.../example.syscfg`

### 3. MDIO/PHY

donor는 `ICSSG1 switch` 기준으로 다음을 직접 제어한다.

- `300b2400.mdio` manual mode
- PHY addr `15` for port 1
- PHY addr `3` for port 2
- PHY driver `DP83869`

근거:

- `.../generated/ti_enet_open_close.c`
- `.../generated/ti_board_config.c`

### 4. UDMA / RX/TX resources

donor는 `PKTDMA_0` 위에 다음 resource를 직접 연다.

- TX channel 2개
- RX flow 4개
- ICSSG1 switch SoC DMA capability 전제
  - `4 TX channels`
  - `9 RX flows`

근거:

- `.../generated/ti_drivers_config.c`
- `.../generated/ti_enet_dma_init.c`
- `.../generated/ti_enet_config.c`
- `.../generated/ti_enet_soc.c`

### 5. PRU / RTU / TX_PRU firmware

donor는 `ICSSG1 switch` slice 0/1용 PRU/RTU/TX_PRU firmware load까지 R5F stack이 소유하는 구조다.

근거:

- `.../generated/ti_enet_soc.c`

### 6. dedicated memory placement

donor linker는 다음을 `MSRAM` dedicated section으로 둔다.

- `.icss_mem`
- `.enet_dma_mem`

근거:

- `.../linker.cmd`
- `.../gptp_icssg_switch.release.map`

## 현재 Path B / Linux live inventory

실보드 관찰 기준:

- Linux `Machine model` marker가 U-Boot 수정값과 일치
- `78000000.r5f`는 test ELF를 실제로 로드
- Linux netdev는 `eth0` only
- `PRU_ICSSG1` device 82는 `DEVICE_STATE_ON`
- `clk0=333333333`, `clk19=192000000`, `clk3=225000000`
- PRU/RTU/TX_PRU remoteproc (`300b4000.pru`, `30084000.rtu`, `3008a000.txpru`, `300b8000.pru`, `30086000.rtu`, `3008c000.txpru`)는 모두 `offline`
- Linux global UDMA driver는 이미 올라와 있음
  - `485c0100.dma-controller`
  - `485c0000.dma-controller`

### 특히 중요한 live 사실 1: clock은 이미 준비돼 있음

`k3conf dump clock 82` 기준:

- `clk0 CORE = 333333333 READY`
- `clk19 UCLK = 192000000 READY`
- `clk3 IEP = 225000000 READY`

즉 donor가 다시 set하려던 값들 중 적어도 일부는 이미 host/TIFS runtime이 준비한 상태다.

### 특히 중요한 live 사실 2: Linux가 ICSSG1 MDIO를 여전히 probe함

현재 Linux에는 다음 device가 존재한다.

```text
/sys/bus/platform/devices/300b2400.mdio
/sys/bus/mdio_bus/devices/300b2400.mdio:0f
```

dmesg에도 다음이 나온다.

```text
davinci_mdio 300b2400.mdio: Configuring MDIO in manual mode
davinci_mdio 300b2400.mdio: phy[15]: device 300b2400.mdio:0f, driver TI DP83869
```

즉 `icssg1-eth`를 꺼서 `eth1/eth2` 생성을 막아도,
Linux는 여전히 `ICSSG1 MDIO controller + PHY15`를 probe하고 있다.

이건 `MDIO/PHY ownership`이 아직 완전히 R5F로 넘어오지 않았음을 의미한다.

### 특히 중요한 live 사실 3: current stop point는 UDMA RX channel open

trace상 최신 실패는 `Enet_open()` 내부에서,

- `EnetUdma_openRxCh`
- `EnetHostPortDma_open`

로 이어지는 RX DMA open path다.

즉 현재 우선순위는 `PKTDMA/RM ownership` 쪽이 가장 높다.

### 특히 중요한 live 사실 4: SYSFW RM table상 `ICSSG_1 PKTDMA` 자원은 `A53_2`에만 배정됨

이번 실보드에서 `k3conf dump rm`으로 `PKTDMA_0`의 `ICSSG_1` 관련 subtype을 직접 확인했다.

결과:

```text
type=30 subtype=40  RESASG_SUBTYPE_PKTDMA_ICSSG_1_TX_CHAN
  -> A53_2 [34 + 8]

type=30 subtype=55  RESASG_SUBTYPE_PKTDMA_ICSSG_1_RX_CHAN
  -> A53_2 [25 + 4]

type=30 subtype=56  RESASG_SUBTYPE_PKTDMA_FLOW_ICSSG_1_RX_CHAN
  -> A53_2 [112 + 64]

type=30 subtype=21  RESASG_SUBTYPE_PKTDMA_RING_ICSSG_1_TX_CHAN
  -> A53_2 [104 + 8]

type=30 subtype=29  RESASG_SUBTYPE_PKTDMA_RING_ICSSG_1_RX_CHAN
  -> A53_2 [224 + 64]
```

반대로 같은 출력에서 `MAIN_0_R5_0`, `MAIN_0_R5_1` 등 R5 host 쪽 할당은 보이지 않았다.

이건 매우 강한 의미를 가진다.

```text
현재 SYSFW RM 관점에서는
ICSSG_1 switch용 PKTDMA 자원이 A53 host에 배정되어 있고,
Path B R5F app이 donor처럼 직접 열려고 하면 ownership 충돌이 날 가능성이 높다.
```

## `A53_2` allocation의 출처 추적

이번 턴에서 이 allocation이 어디서 오는지 1차로 추적했다.

### 1. Linux host 자체가 `A53_2`를 사용한다

`k3-am64-main.dtsi`의 `dmsc` 노드는 다음을 사용한다.

```text
ti,host-id = <12>
```

그리고 `tisci_hosts.h`에서

```text
TISCI_HOST_ID_A53_2 = 12
```

로 정의된다.

즉 Linux/TISCI 기본 host는 `A53_2`다.

근거:

- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am64-main.dtsi:210-216`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/include/tisci/am64x_am243x/tisci_hosts.h:74-80`

### 2. Linux DT의 `icssg1-eth`는 `main_pktdma` 자원을 직접 소비하는 구조다

`k3-am642-evm.dts`의 `icssg1_eth` node는 다음을 가진다.

- `compatible = "ti,am642-icssg-prueth"`
- `dmas = <&main_pktdma ...>`
- `dma-names = "tx0-0" ... "rx0" "rx1"`

즉 Linux ICSSG1 PRUETH 경로 자체가 `main_pktdma`의 `ICSSG_1` TX/RX 자원을 쓰는 모델이다.

근거:

- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-evm.dts:193-231`

### 3. 기본 RM boardcfg가 실제로 `ICSSG_1 PKTDMA`를 `A53_2`에 배정한다

`sciclient_defaultBoardcfg_rm_linux.c`에는 다음 엔트리가 직접 들어 있다.

```text
PKTDMA_RING_ICSSG_1_TX_CHAN   start=104  num=8   host=A53_2
PKTDMA_RING_ICSSG_1_RX_CHAN   start=224  num=64  host=A53_2
PKTDMA_ICSSG_1_TX_CHAN        start=34   num=8   host=A53_2
PKTDMA_ICSSG_1_RX_CHAN        start=25   num=4   host=A53_2
PKTDMA_FLOW_ICSSG_1_RX_CHAN   start=112  num=64  host=A53_2
```

근거:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c:725-728`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c:809-812`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c:881-884`
- `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c:1043-1052`

### 4. 이 RM boardcfg는 boot firmware packaging 경로에 실리는 형식이다

U-Boot K3 SYSFW loader는 `rm-cfg.bin`을 별도 boardcfg artifact로 다룬다.

또 binman DTS도 `rm-cfg` -> `rm-cfg.bin` packaging 노드를 가진다.

즉 이 allocation은 단순히 Linux driver가 runtime에 우연히 만든 상태가 아니라,
부트 체인에서 SYSFW로 전달되는 RM boardcfg 정책과 연결된다고 보는 것이 타당하다.

근거:

- `workspace/ti-u-boot-sdk12/arch/arm/mach-k3/r5/sysfw-loader.c:29-49`
- `workspace/ti-u-boot-sdk12/arch/arm/dts/k3-binman.dtsi:32-53`

## 현재 해석 강화

이제는 단순 추정이 아니라 다음 흐름으로 이해하는 것이 가장 자연스럽다.

```text
Linux host-id = A53_2
Linux icssg1_eth DT = main_pktdma(ICSSG_1) consumer 모델
default RM boardcfg = ICSSG_1 PKTDMA resources -> A53_2
live k3conf dump rm = same result
Path B app = same resources를 R5FSS0_0 owner 전제로 open 시도
=> EnetUdma_openRxCh ownership mismatch
```

즉 현재 `EnetUdma_openRxCh` blocker는

- 단순 channel count mismatch
- random runtime glitch

보다는,

- **TI Linux baseline boot chain이 ICSSG1 PKTDMA ownership을 A53_2에 주는 정책**
- **Path B가 donor standalone 전제로 R5FSS0_0 ownership을 가정하는 구조**

사이의 충돌로 보는 것이 가장 설득력 있다.

## 해결 결과

이후 실보드에서 다음 순서로 실제 해결을 진행했다.

1. `board/ti/am64x/rm-cfg.yaml`의 `ICSSG_1 PKTDMA` 관련 resource를 직접 수정
2. 처음에는 `MAIN_0_R5_0 (35)`로 옮겼지만, Path B app의 PM/RM request는 `secure`가 아니라 `non-secure` context로 나간다는 점을 추가 확인했다.
3. `Sciclient_getCurrentContext()` 기준으로 PM/RM/UDMA 계열 message는 기본적으로 `SCICLIENT_NON_SECURE_CONTEXT`를 사용한다.
4. `sciclient_fmwSecureProxyMap.c` 기준 `R5FSS0_0`의 non-secure host는 `MAIN_0_R5_1 (36)`이다.
5. 그래서 최종적으로는 `A53_2 (12)`를 유지하면서, 같은 `ICSSG_1 PKTDMA` range를 `MAIN_0_R5_1 (36)`에도 중복 배정했다.

핵심 수정 대상:

```text
PKTDMA_RING_ICSSG_1_TX_CHAN
PKTDMA_RING_ICSSG_1_RX_CHAN
PKTDMA_ICSSG_1_TX_CHAN
PKTDMA_ICSSG_1_RX_CHAN
PKTDMA_FLOW_ICSSG_1_RX_CHAN
```

수정 파일:

```text
workspace/ti-u-boot-sdk12/board/ti/am64x/rm-cfg.yaml
```

### 왜 `35`가 아니라 `36`인가

근거:

- `sciclient_soc_priv.h`
  - `SCICLIENT_HOST_ID = TISCI_HOST_ID_MAIN_0_R5_0`
- 그러나 `sciclient.c`의 `Sciclient_getCurrentContext()`는
  - `BOARD_CONFIG*` 계열만 secure context
  - 그 외 대부분의 PM/RM/UDMA request는 non-secure context
- `sciclient_fmwSecureProxyMap.c`에서
  - `SCICLIENT_NON_SECURE_CONTEXT -> TISCI_HOST_ID_MAIN_0_R5_1`

즉 현재 Path B에서 실제 `PKTDMA` open request를 날리는 host는 `35`가 아니라 `36`으로 보는 것이 맞다.

### 적용 후 live 확인

새 boot chain으로 부팅 후 `k3conf dump rm` 결과:

```text
type=30 subtype=40  PKTDMA_ICSSG_1_TX_CHAN
  A53_2       [34 + 8]
  MAIN_0_R5_1 [34 + 8]

type=30 subtype=55  PKTDMA_ICSSG_1_RX_CHAN
  A53_2       [25 + 4]
  MAIN_0_R5_1 [25 + 4]

type=30 subtype=56  PKTDMA_FLOW_ICSSG_1_RX_CHAN
  A53_2       [112 + 64]
  MAIN_0_R5_1 [112 + 64]
```

즉 `A53_2 only`였던 RM allocation이 실제로 `MAIN_0_R5_1`까지 확장됐다.

### 최종 실보드 결과

temporary U-Boot override로 test firmware를 다시 boot한 결과,
기존 blocker였던

```text
EnetUdma_openRxCh
Enet_open failed
```

는 사라졌다.

최신 trace는 다음까지 진행한다.

```text
Mdio_open
Open MAC port 1
Open MAC port 2
PHY 3 is alive
PHY 15 is alive
[RPROC_TRACE] stage=icssg_init state=open code=0 per_idx=0 inst=1 mac_ports=2
default RX flow started
[RPROC_TRACE] stage=gptp_state state=ok code=0 starting TSN modules
[RPROC_TRACE] stage=gptp_state state=ok code=0 all TSN modules started
[RPROC_TRACE] stage=gptp_state state=ok code=0 TSN and gPTP tasks started
[RPROC_TRACE] stage=gptp_state state=task_enter code=0 netdev_count=2
MAC Port 2: link up
MAC Port 1: link up
domain=0, offset=0nsec, hw-adjrate=0ppb
```

즉 현재 Path B는 최소한 다음 단계까지는 실제로 통과한 것으로 본다.

```text
A remoteproc load
B firmware bootstrap
C Enet/ICSSG init
D PHY link up
초기 gPTP runtime task start
```

### baseline 영향

`A53_2` allocation을 완전히 제거하지 않고 `MAIN_0_R5_1`를 추가한 형태로 수정했기 때문에,
기본 Linux boot 경로도 유지된다.

실제로 baseline boot에서는 `icssg1-eth`가 다시 정상적으로 올라왔고,
temporary override boot에서만 test firmware가 해당 resource를 사용했다.

## 현재 상태 요약

```text
RM ownership mismatch: 해결
Path B remoteproc gPTP firmware bootstrap + Enet/PHY/gPTP task start: 확인
```

남은 항목은 더 이상 초기 blocker 해결이 아니라,

- 장기 채택용 boot/ownership policy 정리
- MDIO probe 정합성 재검토
- memory placement parity(.icss_mem/.enet_dma_mem) 필요성 재검토

같은 안정화/채택 단계로 보는 것이 맞다.

### project-side requested resource와의 직접 충돌

현재 Path B generated config는 분명히 `R5FSS0_0` 기준으로 resource를 요청한다.

근거:

- `ti_enet_init.c`
  - `selfCoreId = CSL_CORE_ID_R5FSS0_0`
  - `numTxCh = 2`
  - `numRxCh = 1`
  - `numRxFlows = 4`
- `ti_enet_soc.c`
  - switch RM default partition도 `coreId = CSL_CORE_ID_R5FSS0_0`
  - `numTxCh = ENET_SYSCFG_TX_CHANNELS_NUM`
  - `numRxFlows = ENET_SYSCFG_RX_FLOWS_NUM`

즉 현재 상황은 다음처럼 정리된다.

```text
Path B app request owner: R5FSS0_0
SYSFW RM allocation owner: A53_2
```

이건 `EnetUdma_openRxCh` 실패를 설명하는 1차 근거로 충분하다.

## Ownership Audit Table v1

| Resource | Donor file | Donor action | Linux current state | Risk | Path B policy | Verification | Result |
|---|---|---|---|---|---|---|---|
| PRU_ICSSG1 clk0 | `generated/ti_power_clock_config.c` | parent/rate set | `READY 333333333`, parent=2 | High | `SKIP_IN_REMOTEPROC` + `PRECONFIGURED_BY_HOST` | live trace + `k3conf` | 확정 |
| PRU_ICSSG1 clk19 UCLK | `generated/ti_power_clock_config.c` | rate set | `READY 192000000`, get_freq success | High | `SKIP_IN_REMOTEPROC` 우선 후보 | live trace + `k3conf` | 강한 후보 |
| PRU_ICSSG1 clk3 IEP | `generated/ti_power_clock_config.c` | parent/rate set | `READY 225000000`, current parent=4 | High | `SKIP_IN_REMOTEPROC` 우선 후보 | live trace + `k3conf` | 강한 후보 |
| PRU_ICSSG1 module enable | `generated/ti_power_clock_config.c` | module enable | `DEVICE_STATE_ON` | Medium | `R5F_OWNS` 가능 | live trace | 현재 통과 |
| ICSSG1 MDIO ctrl (`300b2400.mdio`) | `generated/ti_enet_open_close.c` | manual MDIO control | Linux platform device가 probe 중 | High | `UNRESOLVED` | dmesg + sysfs | ownership 충돌 후보 |
| ICSSG1 PHY15/PHY3 | `generated/ti_board_config.c` | DP83869 access | Linux가 `300b2400.mdio:0f` 생성 | High | `UNRESOLVED` | dmesg + `/sys/bus/mdio_bus/devices` | ownership 충돌 후보 |
| PKTDMA RX/TX resources | `generated/ti_enet_dma_init.c`, `generated/ti_enet_soc.c`, `ti_enet_init.c` | R5FSS0_0가 TX 2 / RX flow 4 open 요청 | Linux global UDMA driver active, SYSFW RM table의 ICSSG_1 PKTDMA resource는 `A53_2`에만 배정 | High | `UNRESOLVED` | trace stop point + `k3conf dump rm` | 현재 최신 blocker, ownership 충돌 강한 증거 |
| PRU/RTU/TX_PRU fw for ICSSG1 | `generated/ti_enet_soc.c` | R5 stack이 load | Linux remoteproc는 현재 offline | Medium | `R5F_OWNS` 가능 | remoteproc state | 현재 직접 충돌 증거 없음 |
| `.icss_mem` | donor `linker.cmd` | MSRAM dedicated placement | Path B는 dedicated section 없음 | High | `UNRESOLVED` | linker/map compare | 후속 검토 필요 |
| `.enet_dma_mem` | donor `linker.cmd` | MSRAM dedicated placement | Path B는 generic DDR `.bss` | High | `UNRESOLVED` | linker/map compare | 후속 검토 필요 |

## 현재 판단

### 1. Path 2 방향은 맞다

이미 다음 패턴이 반복 확인됐다.

- donor standalone init 그대로 사용
- remoteproc-hosted runtime에서 ownership mismatch 발생
- 특정 set request skip 시 다음 단계로 진행
- 곧바로 다음 low-level resource request에서 유사 mismatch 발생

즉 지금 문제는 개별 값 튜닝이 아니라,

```text
standalone donor init 전체를
remoteproc-hosted ownership policy로 다시 분류해야 하는 단계
```

다.

### 2. 현재 최신 우선순위는 `UDMA/RM ownership`

현재 trace는 `Enet_open()` 내부에서 `EnetUdma_openRxCh`로 막힌다.

이제는 단순 가능성 수준을 넘어서 다음 해석이 가장 강하다.

1. `PKTDMA ICSSG_1 TX/RX/flow/ring` resource가 SYSFW RM table에서 `A53_2`에 배정되어 있다.
2. Path B app은 그 자원을 `R5FSS0_0` owner 전제로 연다.
3. 따라서 `PKTDMA RX channel open permission / RM grant mismatch`가 현재 1순위 root cause 후보다.

### 3. 그러나 MDIO/PHY ownership도 동시에 unresolved다

비록 최신 stop point는 UDMA지만,
현재 Linux가 `300b2400.mdio`와 `phy15`를 계속 probe 중이라는 사실은
Path B에서 `MDIO/PHY` ownership도 아직 깨끗하게 분리되지 않았음을 뜻한다.

즉 다음 단계는 `UDMA`만 보고 끝내면 안 되고,
`MDIO/PHY`도 Path 2 표에서 unresolved 항목으로 유지해야 한다.

## 다음 작업 제안

다음 턴 우선순위는 아래 순서가 맞다.

1. `ICSSG_1 PKTDMA resource가 왜 A53_2에 배정돼 있는지` 출처 확인
   - Linux DT / boardcfg / host model / baseline firmware 정책 확인
2. `R5FSS0_0`가 해당 resource를 합법적으로 가져갈 수 있는 경로가 있는지 확인
   - host reassignment 가능 여부
   - 별도 boardcfg 전제 여부
3. `300b2400.mdio` Linux probe를 Path B ownership 모델에서 어떻게 다룰지 결정
4. `.icss_mem` / `.enet_dma_mem` donor parity 복원 필요성 재평가

현재 기준 한 줄 결론은 다음이다.

```text
Path 2는 올바른 방향이다.
clock ownership issue를 넘긴 뒤 드러난 최신 blocker는 UDMA/RM ownership 쪽이며,
동시에 MDIO/PHY ownership도 아직 unresolved 상태다.
```
