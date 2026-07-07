# AM64x TSN C Case Plan

## 목표

1. TMDS64EVM에서 `eth1`/`eth2`를 같은 `ICSSG1 dual-port`로 구성 가능한지 확인한다.
2. Linux에서 `ICSSG Ethernet netdev` 생성 경로를 끄고도 `R5F remoteproc`는 유지할 수 있는지 확인한다.
3. `MCU+ SDK`의 `gptp_icssg_switch` 또는 `gptp_icssg_dualmac` 예제를 빌드한다.
4. 이후 `resource_table`, `memory map`, `reserved-memory` 차이를 정리해 `remoteproc` 적용 경로로 연결한다.

## 현재 우선순위

### 1순위: C0 + C1

- `gptp_icssg_*` 예제 위치, build target, 출력 형식 확인
- TMDS 현재 `eth0/eth1/eth2` driver / PHC 상태 재수집
- `k3-am642-evm-icssg1-dualemac.dtbo` 적용 경로 확인
- overlay 적용 후 `eth1`, `eth2`가 모두 `icssg-prueth`인지 확인

### 2순위: C2

- C Case용 Linux DT/overlay 초안 작성
- Linux `ICSSG` probe만 막고 `R5F remoteproc`는 유지하는 최소 수정 지점 확인

### 3순위: C3 + C4

- firmware build
- `readelf -S`, `readelf -l`, linker map 확인
- `remoteproc` load 가능성 분리 판단

## 바로 실행할 명령

### C0: local SDK inventory

```bash
cd ~/ti/TI_Bringup/workspace/mcu_plus_sdk_am64x_12_00_00_27

grep -R "gptp_icssg" -n source/networking/enet/core/examples/tsn
grep -R "resource_table" -n source/networking/enet/core/examples/tsn/gptp_icssg_app
grep -R "CONFIG_ENET_ICSS0\|CONFIG_ENET_ICSS1\|DUAL MAC" -n \
  source/networking/enet/core/examples/tsn/gptp_icssg_app
```

### C1: TMDS Linux baseline

```bash
bash projects/tsn_c_case/board/collect_tmds_c1_baseline.sh
```

### C1: overlay 적용 후 확인 예정 항목

```text
- ip -br link
- ethtool -i eth1
- ethtool -i eth2
- ethtool -T eth1
- ethtool -T eth2
- /sys/class/ptp mapping
- dmesg 중 icssg/prueth/phy/remoteproc 관련 로그

현재 상태:

- 2026-06-30에 U-Boot 임시 `name_overlays` 변경으로 `icssg1-dualemac` 적용 시험을 수행했다.
- 결과는 `eth1`, `eth2` 모두 `icssg-prueth`로 확인되었고, `dual EMAC mode` dmesg도 확보했다.
- 따라서 남은 C1 항목은 "지속 적용 방식 선택"이지, feasibility 자체는 아니다.
```

## 산출물 원칙

- 실행 로그는 `projects/tsn_c_case/logs/` 아래에 저장
- 장기 판단은 `projects/tsn_c_case/docs/`에 정리
- TMDS/SK 공통 topology 사실은 필요 시 `projects/tsn_dscp_pcp/docs/board-matrix.md`를 참조
