# AM64x Qbu Baseline

## 목적

이 문서는 Qbu 검증에 앞서 실제 보드에 적용한 clean baseline 조건을 고정한다.

이 baseline은 단순 관찰 문서가 아니라,
현재 SK/TMDS 보드가 **무슨 설정으로 올라와 있어야 Qbu 결과를 해석 가능하게 볼 수 있는지**를 정의하는 기준 문서다.

## 적용 일시

- 작업 세션 기준: 2026-07-08

## 왜 baseline 정리가 필요했는가

기존 Qbv/DSCP-PCP 실험의 자동 적용 자산이 두 보드 rootfs에 남아 있었다.

- SK-AM64B
  - `br-tsn` bridge 생성 파일 존재
  - `eth0`, `eth1`를 `br-tsn`에 붙이는 `.network` 파일 존재
  - `br-tsn`에 `10.50.0.2/24`를 부여하는 `.network` 파일 존재
- TMDS64EVM
  - `eth1`에 `10.50.0.1/24`를 부여하는 `.network` 파일 존재
  - `eth2` endpoint profile `.network` 파일 존재
  - `ti-tsn-dscp-pcp-tmds.service`가 boot 후 `systemd-networkd`를 다시 restart하도록 구성됨

이 상태는 보드 자체의 이상이 아니라,
이전 TSN 실험을 자동 재현하기 위한 설정이 아직 살아 있는 상태였다.

문제는 이 설정이 남아 있으면 Qbu 결과가 다음 중 무엇 때문인지 분리하기 어렵다는 점이다.

1. 새로 적용한 Qbu/MAC Merge 설정
2. 기존 TSN bridge / IP profile
3. boot 후 재적용되는 `systemd-networkd` 상태

따라서 이번 baseline 정리는 **고장 수리**가 아니라 **시험 조건 정렬**이다.

## 실제 적용한 board-side 변경

### SK-AM64B

다음 파일을 비활성화 backup 이름으로 이동했다.

- `/etc/systemd/network/05-br-tsn.netdev` -> `05-br-tsn.netdev.qbu-disabled`
- `/etc/systemd/network/06-eth0-br-tsn-slave.network` -> `06-eth0-br-tsn-slave.network.qbu-disabled`
- `/etc/systemd/network/07-eth1-br-tsn-slave.network` -> `07-eth1-br-tsn-slave.network.qbu-disabled`
- `/etc/systemd/network/08-br-tsn.network` -> `08-br-tsn.network.qbu-disabled`

추가로 다음 파일을 생성했다.

- `/etc/systemd/network/09-eth0-l2only.network`

의도:

- `eth0`를 DHCP나 bridge slave가 아니라 L2-only 테스트 포트로 고정
- `eth1`는 기존 `/etc/systemd/network/11-eth1-l2only.network`를 그대로 사용

추가 runtime 정리:

- stale `br-tsn` bridge 삭제
- `eth0`, `eth1`의 `p0-rx-ptype-rrobin`을 `off`로 설정

### TMDS64EVM

다음 파일을 비활성화 backup 이름으로 이동했다.

- `/etc/systemd/network/05-eth1-tsn-control.network` -> `05-eth1-tsn-control.network.qbu-disabled`
- `/etc/systemd/network/06-eth2-tsn-endpoint.network` -> `06-eth2-tsn-endpoint.network.qbu-disabled`

다음 서비스는 disable 상태로 전환했다.

- `ti-tsn-dscp-pcp-tmds.service`

의도:

- `eth1`는 기존 `/etc/systemd/network/11-eth1-l2only.network`로 매치
- `eth2`는 기존 `/etc/systemd/network/12-eth2-l2only.network`로 매치
- `eth0`는 기존 `/etc/systemd/network/10-eth.network`로 유지되어 control DHCP를 계속 사용

추가 runtime 정리:

- `eth0`, `eth1`의 `p0-rx-ptype-rrobin`을 `off`로 설정
- `eth2`의 FPE TX는 disable 상태로 정리

## Persistent Baseline 조건

이 문서의 persistent rootfs 변경은
`rootfs/overlays/*-qbu-clean-baseline/`의 script로 관리한다. `p0-rx-ptype-rrobin`,
MAC Merge, TX channel 수, qdisc, IP address는 persistent baseline이 아니라 각 시험 run의
runtime 설정이다.

### SK-AM64B

- control plane: UART
- `systemd-networkd`: active
- TSN auto-apply service: `not-found`
- `br-tsn`: 없음
- IPv4 address
  - `eth0`: 없음
  - `eth1`: 없음
- qdisc
  - `eth0`, `eth1`: 기본 `mq` + `pfifo_fast`
- MM state
  - `eth0`
    - `pMAC enabled: off`
    - `TX enabled: off`
    - `Verify enabled: off`
    - `tx-min-frag-size: 60`
  - `eth1`
    - `pMAC enabled: off`
    - `TX enabled: off`
    - `Verify enabled: off`
    - `tx-min-frag-size: 60`
의미:

- SK는 두 data port 모두 IP 없는 L2-only CPSW endpoint 상태다.
- Qbu 실험 시 필요한 설정만 이후 수동으로 올리면 된다.

### TMDS64EVM

- control plane
  - UART 또는 `eth0` runtime DHCP
- `systemd-networkd`: active
- TSN auto-apply service: `disabled`
- IPv4 address
  - `eth0`: control connection 방식에 따라 runtime 할당
  - `eth1`: 없음
  - `eth2`: 없음
- qdisc
  - `eth0`, `eth1`, `eth2`: 기본 `mq` + `pfifo_fast`
- MM state
  - `eth1`
    - `pMAC enabled: off`
    - `TX enabled: off`
    - `Verify enabled: off`
    - `tx-min-frag-size: 60`
  - `eth2`
    - `pMAC enabled: on`
    - `TX enabled: off`
    - `Verify enabled: off`
    - `tx-min-frag-size: 64`
의미:

- TMDS는 `eth0` control을 유지하면서,
  `eth1`, `eth2`를 IP 없는 L2-only data port로 분리한 상태다.

## Current Physical Pair Interpretation

현재 확인된 배선은 다음과 같다.

```text
Canonical:   SK eth1 <-> TMDS eth1 (CPSW <-> CPSW)
Comparative: SK eth0 <-> TMDS eth2 (CPSW <-> ICSSG)
```

TMDS `eth2` ICSSG는 `pMAC enabled: on`을 idle state에서도 보일 수 있어 canonical clean
baseline이 아니다. actual-Qbu certificate와 새 검증의 기준은 canonical CPSW pair다.

## Baseline 판정

```text
rootfs isolation baseline: managed
physical mapping: confirmed
runtime Qbu setting: each test run applies and removes it
```

정확한 clean managed base, runtime minimum state, physical connection, acceptance rule은
[CLEAN_BASE_CONTRACT.md](CLEAN_BASE_CONTRACT.md)를 따른다.
