# AM64x TSN DSCP PCP Lab

## 목적

이 프로젝트는 `SK-AM64B`를 TSN switch candidate로, `TMDS64EVM`을 control + dual endpoint로 두고
DSCP/PCP 확인을 위한 사전 환경 구성과 후속 실험을 관리하기 위한 작업 구역이다.

현재 단계의 1차 목표는 다음이다.

- `TMDS eth0` control 경로 유지
- `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1` 구성 확인
- `TMDS -> SK` 제어 경로 확보
- `SK` Linux bridge 기반 L2 forwarding 환경 구성
- 이후 DSCP/PCP 실험을 위한 기준 topology 정리

## 기준 문서

- `.agents/am64x_sk_tsn_switch_tmds_endpoint_env_setup.md`

## 문서

- `docs/plan.md`: 환경 구성 목표와 진행 순서
- `docs/board-matrix.md`: 포트 역할, PHC, 현재 토폴로지
- `docs/results.md`: 확인 결과와 판정
- `docs/issues.md`: 실패/주의사항 기록

## 적용 자산

- host-side one-shot apply:
  - `board/apply_tsn_env.sh`
- persistent rootfs overlay:
  - `rootfs/overlays/tmds64evm-tsn-dscp-pcp/`
  - `rootfs/overlays/sk-am64b-tsn-dscp-pcp/`

이 프로젝트의 network topology는

- live rootfs에 설치되는 `systemd-networkd` 파일
- 보드 내부 `/usr/local/sbin/ti-tsn-dscp-pcp-*.sh` apply script
- host에서 실행하는 `board/apply_tsn_env.sh`

조합으로 관리한다.

## 현재 가정

- `TMDS eth0`는 office/control 네트워크를 유지한다.
- Host는 `TMDS eth0`로 접속하고, SK는 TMDS를 jump host로 사용해 접근한다.
- `SK eth0`, `SK eth1`은 같은 CPSW PHC `/dev/ptp0`를 공유하는 switch candidate port다.
- `TMDS eth1`은 CPSW endpoint, `TMDS eth2`는 ICSSG endpoint 후보다.

## 현재 상태

- 물리 연결은 `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1`로 정리했다.
- `TMDS eth0`는 `192.168.0.220/24` control port로 유지했다.
- SK direct host SSH는 현재 불가하며, 최종 제어 경로는 `Host -> TMDS -> SK`로 확보했다.
- bootstrap 단계에서는 SK reachable IP가 없어서 UART로 `eth0` 임시 IP를 부여한 뒤 TMDS 경유 SSH를 열었다.
- 현재 SK는 `br-tsn` Linux bridge를 사용하고, control IP는 `br-tsn`에 `10.50.0.2/24`로 올려 두었다.
- 현재 TMDS는 `eth1 = 10.50.0.1/24`, `eth2 = no IP` 상태로 endpoint/control test용으로 둔다.

## Persistence 정리

- 처음 구성은 runtime `ip` 명령으로 bootstrap 했다.
- 이후에는 두 보드의 live rootfs에 `systemd-networkd` persistent 파일을 설치했다.
- 따라서 다음부터는 **reboot 때마다 수동으로 bridge/IP를 다시 입력하는 구조가 아니라**, rootfs에 들어간 network profile이 자동 적용되는 형태다.
- TMDS는 boot 직후 `eth1`이 잠깐 `DOWN/NO-CARRIER`로 보일 수 있어 boot-time re-apply service를 추가했다.
- 이 service가 실행된 뒤 `eth1 = 10.50.0.1/24`, `eth2 = up`, `Host -> TMDS -> SK` 경로가 다시 복구되는 것까지 확인했다.
- 또한 같은 상태를 즉시 재적용하려면 host에서 다음 스크립트를 실행하면 된다.

```bash
bash projects/tsn_dscp_pcp/board/apply_tsn_env.sh
```
