# AM64x TSN C Case C2 Linux DT Ownership Plan

## 목적

Linux가 `ICSSG Ethernet netdev`를 만들지 않도록 하면서, `R5F remoteproc`는 유지하는 C2용 DT 후보를 정리한다.

## 현재 후보

workspace kernel source에 다음 overlay 후보를 추가했다.

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/
  k3-am642-evm-icssg1-r5f-owner.dtso
```

## 후보 overlay 의도

이 overlay는 다음 세 가지만 수행한다.

1. `cpsw_port2` disable
2. `mdio_mux_1` disable
3. `icssg1_eth` disable

추가로 `ethernet1`, `ethernet2` alias를 제거해 Linux 쪽에서 남은 netdev alias 혼선을 줄인다.

## 왜 이 지점을 고르는가

### 유지해야 하는 것

- `main_r5fss0`, `main_r5fss1`
- 각 `main_r5fss*_core*`
- `reserved-memory`
- mailbox / remoteproc 관련 node

이들은 `k3-am64-ti-ipc-firmware.dtsi`에서 `status = "okay"`로 열리며, 이번 후보에서는 건드리지 않는다.

### 끄려는 것

- Linux `icssg-prueth` probe
- Linux `eth1` / `eth2` 생성 경로
- Linux CPSW port2 ownership

## 핵심 가정

이 후보는 다음을 전제로 한다.

1. 최종 C Case에서 ICSSG pinmux / MDIO / mux GPIO / PHY handling은 R5 firmware가 맡는다.
2. Linux는 ICSSG Ethernet runtime owner가 아니다.
3. Linux는 `remoteproc host` 역할만 유지한다.

즉 이 overlay는 `Linux가 ICSSG Ethernet을 사용하지 않는다`는 전제를 source 수준에서 먼저 표현한 것이다.

## C1과의 관계

- C1에서는 `k3-am642-evm-icssg1-dualemac.dtbo`로 Linux dual EMAC feasibility를 확인했다.
- C2 후보는 그 다음 단계로, 반대로 Linux ownership을 끄는 방향이다.

둘의 역할은 다르다.

```text
C1: Linux가 ICSSG dual-port를 잡을 수 있는가?
C2: Linux가 ICSSG를 안 잡게 만들 수 있는가?
```

## compile 상태

다음 direct `gcc -E + dtc` 경로로 overlay compile 성공을 확인했다.

출력:

```text
workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-evm-icssg1-r5f-owner.dtbo
```

주의:

- Kbuild target 이름으로 직접 `.dtbo`를 부르는 방식은 현재 workspace에서 바로 먹지 않아 direct `dtc` 경로를 사용했다.

## 2026-06-30 live boot simulation 결과

새 DTBO 파일을 board에 복사하지 않고, U-Boot에서 base DT + onboard overlay를 로드한 뒤 아래 3개를 `fdt set`으로 수동 적용해 C2 의미를 검증했다.

```text
/bus@f4000/ethernet@8000000/ethernet-ports/port@2 -> status = "disabled"
/mdio-mux-1 -> status = "disabled"
/icssg1-eth -> status = "disabled"
```

### boot 후 확인 결과

- `ip -br link`:
  - `eth0`만 남음
  - `eth1`, `eth2` 미생성
- `/sys/class/remoteproc/*`:
  - `5000000.m4fss`, `78000000.r5f`, `78200000.r5f`, `78400000.r5f`, `78600000.r5f` 모두 `running`
- `dmesg`:
  - `remoteproc` / `R5F` bring-up 정상
  - `icssg-prueth` driver init 흔적 없음

### 의미

- Linux ICSSG Ethernet ownership 제거: 확인
- Linux CPSW port2 ownership 제거: 확인
- R5F remoteproc 유지: 확인

즉 **C2의 핵심 의미는 live boot 기준으로 이미 검증되었다.**

다만 아직 남은 것은:

- 실제 `k3-am642-evm-icssg1-r5f-owner.dtbo` 파일을 boot path에 넣는 운영 방식 선택
- 이후 custom `R5 firmware`를 실제로 로드했을 때 pinmux/MDIO ownership이 맞는지 확인

## 아직 미검증 항목

1. 실제 `r5f-owner.dtbo` 파일을 boot media 경로에 넣어도 같은 결과가 나오는지
2. boot 후 다른 service가 예상 밖으로 깨지지 않는지 장시간 관찰
3. 이후 custom R5 firmware가 실제로 pinmux/MDIO를 문제 없이 가져가는지

## 다음 실기 검증 절차

1. `r5f-owner.dtbo`를 실제 boot path에 태울 적용 방식 결정
2. custom R5 firmware artifact 준비
3. 아래 항목 확인

```text
- /sys/class/remoteproc/*
- dmesg | grep -iE 'remoteproc|r5f|icssg|prueth|phy|firmware'
- firmware trace/log
- ICSSG port link up 여부
```

## 현재 판정

- source 후보 작성: 완료
- compile 확인: 완료
- live boot 의미 검증: 완료
- boot artifact 적용 방식: 미완료
