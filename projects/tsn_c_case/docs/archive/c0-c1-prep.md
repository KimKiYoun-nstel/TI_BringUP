# AM64x TSN C Case C0/C1 준비 메모

## 목적

이 문서는 C Case를 실제 실행하기 전에, 현재 repo 기준으로 이미 확인된 사실과 아직 남은 blocker를 정리한다.

## 이미 확인된 사실

### 0. 2026-06-30 baseline 수집 완료

- 수집 로그:
  - `projects/tsn_c_case/logs/reference/2026-06-30_165223_tmds_c1_linux_baseline.txt`
- 수집 결과 핵심:
  - `eth0`: `am65-cpsw-nuss`
  - `eth1`: `am65-cpsw-nuss`
  - `eth2`: `icssg-prueth`
  - `eth2` link up
  - `remoteproc0..8` 기준 M4F / R5F가 모두 `running`
  - `icssg1-eth: TI PRU ethernet driver initialized: single EMAC mode`

의미:

- 오늘 수집 결과는 아직 `ICSSG dual-port` 상태가 아니라 baseline `single EMAC` 상태다.
- 따라서 다음 실행 단계는 dualmac overlay 적용 전후 비교가 된다.

### 0.1 2026-06-30 temporary dualmac overlay boot 검증 완료

- 방법:
  - U-Boot에서 `saveenv` 없이 일시적으로 `name_overlays`를 다음처럼 변경했다.
  - `ti/k3-am642-evm-onboard-clkgen-pcie-serdes.dtbo ti/k3-am642-evm-icssg1-dualemac.dtbo`
- 이후 `run bootcmd`로 Linux를 부팅했다.

- 확인 결과:
  - `eth1`: `icssg-prueth`
  - `eth2`: `icssg-prueth`
  - `dmesg`: `TI PRU ethernet driver initialized: dual EMAC mode`
  - `eth1` / `eth2` 둘 다 link up
  - `ethtool -T eth1`, `ethtool -T eth2` 기준 둘 다 hardware timestamp 가능
  - `/sys/class/ptp/ptp2` = `ICSS IEP timer`

- 부수 효과:
  - 기존 CPSW `eth1` control/test port 역할은 이번 부팅에서 ICSSG dual EMAC 구성으로 대체되었다.
  - 현재 적용은 `saveenv` 없이 한시적 boot env 변경만 사용했으므로, 다음 cold/warm reboot에서 자동 유지되는 상태는 아니다.

의미:

- C1의 핵심 질문인 `TMDS64EVM에서 ICSSG dual-port Linux 구성이 가능한가`에 대해 현재 증거상 `yes`로 판정할 수 있다.
- 즉 Level 1 feasibility의 절반인 `TMDS ICSSG dual port 가능성`은 확보되었다.

### 1. TMDS baseline Ethernet 상태

- `eth0`: `am65-cpsw-nuss`, control port
- `eth1`: `am65-cpsw-nuss`, CPSW endpoint
- `eth2`: `icssg-prueth`, ICSSG endpoint
- `eth2`는 기존 TSN 실험에서 `/dev/ptp2`와 `ICSS IEP timer`를 사용했다.

근거:

- `projects/tsn_dscp_pcp/docs/results.md`
- `projects/tsn_dscp_pcp/docs/board-matrix.md`

### 2. TMDS dual-port overlay 자산 존재

- Linux DTS에 `k3-am642-evm-icssg1-dualemac.dtso`가 존재한다.
- 이 overlay는 `cpsw_port2`를 disable하고 `icssg1_emac1`를 enable한다.

의미:

- C1의 핵심 질문인 "TMDS에서 ICSSG dual-port Linux 구성이 가능한가"를 repo 자산만으로 검증할 수 있다.

### 3. MCU+ SDK example 자산 존재

- `gptp_icssg_dualmac`
- `gptp_icssg_switch`

의미:

- C0에서 example inventory를 문서화할 수 있고, C3 build 대상으로 바로 사용할 수 있다.

## 아직 남은 blocker

### 1. remoteproc 적합성은 아직 미확정

- `gptp_icssg_*` example은 build target이 존재하지만, 현재 흔적상 `ipc_rpmsg_echo_linux`처럼 명시적인 `.resource_table` 설정이 보이지 않는다.
- linker / memory 배치도 Linux `reserved-memory`와 바로 맞지 않을 가능성이 있다.

의미:

- `example build success`와 `Linux remoteproc load success`를 같은 단계로 보면 안 된다.

### 2. C Case용 Linux ownership 분리 자산은 아직 없음

- 현재 repo에는 `ICSSG dual-port Linux enable` overlay는 있지만,
- `Linux prueth probe disable + R5F remoteproc 유지` 목적의 C Case 전용 overlay는 아직 없다.

## 지금 바로 필요한 로그

- U-Boot env: `name_overlays`, `fdtfile`, `boot_targets`, `bootcmd`
- TMDS `ip -br link`
- TMDS `ethtool -i eth0/eth1/eth2`
- TMDS `ethtool -T eth1/eth2`
- TMDS `/sys/class/ptp/*`
- TMDS `dmesg` 중 `icssg|prueth|phy|remoteproc|firmware`

현재 이 항목들의 baseline 1차 수집본은 이미 확보되었다.

## 실행 순서 권장안

1. 현재 baseline C1 로그 수집
2. `icssg1-dualemac` overlay 적용 경로 확인
3. overlay 적용 후 `eth1/eth2 -> icssg-prueth` 여부 확인
4. 그 뒤에야 C2 ownership 분리 초안 작성

## 현재 판정

- C0 example inventory는 완료했다.
- C1의 `TMDS dual-port Linux evidence`도 임시 boot env 방식으로 확보했다.
- 이제 다음 핵심 단계는 `C2 ownership 분리`다.
