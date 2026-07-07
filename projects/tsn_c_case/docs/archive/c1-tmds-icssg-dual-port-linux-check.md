# AM64x TSN C Case C1 TMDS ICSSG Dual-Port Linux Check

## 목적

TMDS64EVM에서 `ICSSG1 dual-port Linux` 구성이 실제로 가능한지 확인한다.

## 시험 방식

이번 시험은 영구 변경이 아니라, U-Boot prompt에서 `name_overlays`를 일시 변경하는 방식으로 수행했다.

```text
기존:
  ti/k3-am642-evm-onboard-clkgen-pcie-serdes.dtbo

임시 적용:
  ti/k3-am642-evm-onboard-clkgen-pcie-serdes.dtbo
  ti/k3-am642-evm-icssg1-dualemac.dtbo
```

`saveenv`는 사용하지 않았다.

## 부팅 전 baseline

- `eth1`: `am65-cpsw-nuss`
- `eth2`: `icssg-prueth`
- `dmesg`: `single EMAC mode`

근거:

- `projects/tsn_c_case/logs/reference/2026-06-30_165223_tmds_c1_linux_baseline.txt`

## 부팅 후 확인 결과

### link 이름과 상태

```text
eth1 UP
eth2 UP
```

### driver

```text
eth1 -> icssg-prueth
eth2 -> icssg-prueth
```

### timestamp / PHC

- `ethtool -T eth1`: hardware timestamp 가능
- `ethtool -T eth2`: hardware timestamp 가능
- `Hardware timestamp provider index: 2`
- `/sys/class/ptp/ptp2`: `ICSS IEP timer`

### dmesg 핵심 문구

```text
icssg-prueth icssg1-eth: TI PRU ethernet driver initialized: dual EMAC mode
icssg-prueth icssg1-eth eth2: Link is Up - 1Gbps/Full - flow control off
icssg-prueth icssg1-eth eth1: Link is Up - 1Gbps/Full - flow control off
```

## 판정

### 확정

- TMDS64EVM에서 `k3-am642-evm-icssg1-dualemac.dtbo`를 사용해 `ICSSG1 dual-port Linux` 구성이 가능하다.
- `eth1`, `eth2` 모두 `icssg-prueth`로 올라온다.
- 두 포트 모두 hardware timestamp capability를 유지한다.

### 주의

- 이번 검증은 Linux가 ICSSG를 소유한 상태다.
- 즉 이것은 **C1 feasibility 확인**이지, 아직 C Case의 최종 목표인 `R5F firmware 단독 ownership`은 아니다.
- 기존 `TMDS eth1` control/test 역할은 이번 부팅에서 유지되지 않는다.
- 현재 적용 방식은 일시적 boot env 변경이므로 재부팅 후 자동 유지되지 않는다.

## 다음 단계

1. C2: Linux `ICSSG Ethernet probe`만 막는 DT 초안 작성
2. R5F `remoteproc` 유지 조건 확인
3. 이후 C3/C4로 진행
