# AM64x TSN DSCP PCP Lab Results

## 최신 정리

- `TMDS eth0` control 경로를 유지한 상태로, `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1` topology를 실제 보드에서 구성했다.
- Host에서 SK direct SSH는 불가했지만, UART bootstrap 후 `Host -> TMDS -> SK` 제어 경로를 확보했다.
- SK는 `br-tsn` Linux bridge로 `eth0`, `eth1`을 묶었고 control IP `10.50.0.2/24`를 `br-tsn`에 올렸다.
- TMDS `eth1`은 `10.50.0.1/24`로 SK control/test port 역할을 맡고, `eth2`는 no-IP endpoint/capture port로 유지한다.
- bridge forwarding은 `TMDS eth1`에서 발생한 broadcast ARP가 `SK bridge`를 거쳐 `TMDS eth2`에서 관측되는 것으로 확인했다.
- optional 준비 항목으로 `SK ptp4l -i eth0 -i eth1` multi-interface 실행도 시작 가능한 것을 확인했다.
- namespace 기반 endpoint 분리(`ep1`, `ep2`)로 Level 1~6 DSCP/PCP 실험을 수행했다.
- DSCP `0x00`, `0x28`, `0x88`, `0xb8`는 SK bridge를 지나 그대로 보존되었다.
- 초기 DSCP/PCP 실험에서는 VLAN tag와 DSCP는 유지되었지만, CPSW sender path의 PCP는 계속 `0`으로 보였다.
- 이후 source 조사로 `RX_REMAP_VLAN` 패치는 이미 local TI SDK 12 kernel source에 들어 있고 enable되어 있음이 확인되었다.
- 추가 runtime 검증에서 문제의 핵심은 patch 부재보다 **CPSW QoS prerequisite 미충족** 쪽에 더 가까웠다.
- 실제로 `p0-rx-ptype-rrobin off` + `mqprio hw 1 mode channel` + `VLAN egress-qos-map` + `tc skbedit priority` 조건을 맞추자, SK direct sender는 다음을 실제 wire에 emit했다.
  - `SK eth1 -> TMDS eth2`: `vlan 301, p 7` / `vlan 301, p 6`
  - `SK eth0 -> TMDS eth1`: sender-side capture 기준 `vlan 300, p 7` / `vlan 300, p 6`
- 즉 **CPSW endpoint direct sender PCP emission 자체는 official QoS prerequisite 적용 후 정상 동작**했다.
- 같은 날 Test B 재검증에서 `TMDS ep2 eth2.301` 재구성 시 빠졌던 `egress-qos-map`을 복구한 뒤 다시 확인하자, `TMDS eth2(ICSSG) -> SK switchdev -> TMDS eth1` 경로의 final receiver capture에서도 `vlan 301, p 7` / `vlan 301, p 6`가 확인되었다.
- 즉 최신 기준으로는 **SK CPSW switchdev forwarding path의 end-to-end PCP preservation도 동작**한다.
- 다만 SK local `tcpdump -i eth1`, `tcpdump -i eth0`는 switchdev hardware offload 상태에서 둘 다 `0 packets captured`로 남아, SK 내부 ingress/egress frame을 host tcpdump로 직접 보는 방식은 이번 세션에서 유효하지 않았다.
- 따라서 latest maintained 판단은 다음과 같다.
  - CPSW direct sender PCP emission: 동작
  - ICSSG -> SK switchdev -> receiver PCP preservation: 동작
  - SK 내부 포트 local tcpdump visibility: 미확보
- 최신 상세 보고서는 다음 두 문서를 함께 본다.
  - `docs/2026-06-26_am64x-cpsw-qos-runtime-prerequisite-validation.md`
  - `docs/2026-06-26_testB-revalidation.md`
- SK `tc -s qdisc`와 `ethtool -S` 카운터는 traffic 전후 증가를 보여 queue/stat 관찰이 가능했다.
- `mqprio`, `taprio`, `cls_flower`, `act_skbedit` module load가 가능했고, SK `eth1`에 software mode `mqprio` qdisc 적용도 성공했다.
- background UDP 혼잡 조건에서 DSCP-only 우선순위 효과는 명확히 입증되지 않았으며, 다음 단계는 explicit `skb priority`/`tc`/`mqprio` mapping이다.

## 1. Topology

- Host/control: host office network -> `TMDS eth0`
- TMDS eth0 IP: `192.168.0.220/24`
- TMDS eth1 <-> SK eth0: link up, `1000Mb/s Full`
- TMDS eth2 <-> SK eth1: link up, `1000Mb/s Full`

## 2. Port Capability

| Board | Port | Driver | Link | Speed | PHC Index | PHC Device | HW Timestamp |
|---|---|---|---|---|---|---|---|
| TMDS | eth0 | `am65-cpsw-nuss` | up | `1000 Full` | `0` | `/dev/ptp0` | yes |
| TMDS | eth1 | `am65-cpsw-nuss` | up | `1000 Full` | `0` | `/dev/ptp0` | yes |
| TMDS | eth2 | `icssg-prueth` | up | `1000 Full` | `2` | `/dev/ptp2` | yes |
| SK | eth0 | `am65-cpsw-nuss` | up | `1000 Full` | `0` | `/dev/ptp0` | yes |
| SK | eth1 | `am65-cpsw-nuss` | up | `1000 Full` | `0` | `/dev/ptp0` | yes |

추가 관찰:

- TMDS `/dev/ptp2`는 `ICSS IEP timer`
- SK `eth0`, `eth1`은 둘 다 같은 CPSW PHC `/dev/ptp0`를 공유한다.

## 3. Control Path

- Host -> TMDS SSH: 성공 (`root@192.168.0.220`)
- TMDS -> SK SSH: 성공 (`TMDS eth1 10.50.0.1 -> SK 10.50.0.2`)
- Host -> TMDS jump host -> SK: 성공. nested SSH 방식으로 검증함
- SK control IP: 현재 `br-tsn = 10.50.0.2/24`
- Notes:
  - 초기 상태에서는 SK reachable control IP가 없었다.
  - bootstrap 단계에서 UART로 `SK eth0 = 10.50.0.2/24`를 부여해 TMDS 경유 SSH를 열었다.
  - 이후 bridge 구성 뒤 control IP를 `eth0`에서 `br-tsn`으로 옮겼다.

## 4. SK Linux Bridge

- br-tsn created: yes
- eth0 joined: yes
- eth1 joined: yes
- br-tsn IP: `10.50.0.2/24`
- bridge fdb result:
  - `70:ff:76:20:22:99 dev eth0 master br-tsn` 학습 확인 (`TMDS eth1` MAC)
  - `70:ff:76:20:22:9a dev eth1 master br-tsn` 학습 확인 (`TMDS eth2` MAC)
- L2 forwarding result:
  - `TMDS eth1`에서 `arping -I eth1 10.50.0.99` 실행
  - `TMDS eth2`에서 동일 broadcast ARP frame 관측
  - 즉 `TMDS eth1 -> SK eth0 -> br-tsn -> SK eth1 -> TMDS eth2` 방향 broadcast forwarding 확인

관측된 대표 frame:

```text
70:ff:76:20:22:99 > ff:ff:ff:ff:ff:ff, ARP who-has 10.50.0.99 tell 10.50.0.1
```

## 5. Optional Namespace Endpoint Test

- ep1 namespace: not applied
- ep2 namespace: not applied
- Notes:
  - 현재 단계에서는 control path 단순성을 유지하기 위해 `eth1`, `eth2`를 root namespace에 두었다.
  - 이후 DSCP/PCP 실험에서 endpoint 분리가 필요하면 namespace 전환을 재검토한다.

## 6. Optional gPTP Bridge Candidate Test

- SK ptp4l multi-interface command:
  - `ptp4l -i eth0 -i eth1 -f /tmp/gptp-bridge.cfg -m`
- selected PHC: `/dev/ptp0`
- SK eth0 port state: `INITIALIZING -> LISTENING`
- SK eth1 port state: `INITIALIZING -> LISTENING`
- TMDS eth1 role: not executed in this step
- TMDS eth2 role: not executed in this step
- TMDS eth2 SLAVE transition: not tested in this step
- offset/path delay: not tested in this step
- judgement:
  - SK에서 same-PHC multi-interface `ptp4l` launch 자체는 가능했다.
  - boundary/time-aware bridge 의미의 port role 분화는 아직 확인하지 않았다.

## 7. Final Judgement

- Environment setup completed: yes
- Ready for DSCP/PCP guide update: yes
- Remaining issues:
  - SK bootstrap에는 UART가 필요했다. 현재는 TMDS 경유 SSH로 운영 가능
  - TMDS `eth1`/`eth2` namespace endpoint 분리는 아직 미적용
  - full gPTP bridge behaviour는 아직 미검증

## 8. Persistence / Apply Path

이번 환경은 이제 단순 runtime-only 상태가 아니다.

### persistent rootfs files

- TMDS live rootfs installed:
  - `/etc/systemd/network/05-eth1-tsn-control.network`
  - `/etc/systemd/network/06-eth2-tsn-endpoint.network`
  - `/usr/local/sbin/ti-tsn-dscp-pcp-tmds-apply.sh`
- SK live rootfs installed:
  - `/etc/systemd/network/05-br-tsn.netdev`
  - `/etc/systemd/network/06-eth0-br-tsn-slave.network`
  - `/etc/systemd/network/07-eth1-br-tsn-slave.network`
  - `/etc/systemd/network/08-br-tsn.network`
  - `/usr/local/sbin/ti-tsn-dscp-pcp-sk-apply.sh`

repo 기준 overlay source:

- `rootfs/overlays/tmds64evm-tsn-dscp-pcp/`
- `rootfs/overlays/sk-am64b-tsn-dscp-pcp/`

### one-shot host apply

- host script:
  - `projects/tsn_dscp_pcp/board/apply_tsn_env.sh`

역할:

- overlay를 TMDS/SK live rootfs에 복사
- TMDS `systemd-networkd` 재적용
- SK `systemd-networkd` 재적용
- SK reconnect probe 수행

즉 이후 동일 topology 재적용은 다음 명령으로 수행한다.

```bash
bash projects/tsn_dscp_pcp/board/apply_tsn_env.sh
```

### reboot 관점 정리

- 현재 live rootfs에는 persistent network file이 이미 설치되었다.
- 또한 `systemd-networkd` 재기동으로 target topology가 실제로 올라오는 것까지 확인했다.
- 따라서 다음 reboot부터는 수동 `ip link add`, `ip addr add`를 다시 입력하는 구조가 아니다.
- TMDS reboot는 실제로 검증했다.
  - reboot 직후 `eth0 = 192.168.0.220/24`는 먼저 복구됨
  - `eth1`은 boot 초기에 일시적으로 `DOWN/NO-CARRIER` 상태였음
  - `ti-tsn-dscp-pcp-tmds.service`가 boot 후 실행되며 re-apply를 수행
  - 최종적으로 `eth1 = 10.50.0.1/24`, `eth2 = up` 복구 확인
  - 이후 `Host -> TMDS -> SK` SSH 경로도 다시 복구됨
- 따라서 TMDS 쪽 persistence는 **networkd static file + boot-time re-apply service** 조합으로 확인 완료다.
- SK는 persistent file/live apply 상태까지는 확인했지만, reset switch 기반 reboot 복구는 사용자가 직접 UART 관찰 중인 흐름과 함께 별도 확인 중이다.

## 기록 위치

- 실보드 환경 구성 결과와 판단은 이 문서에 누적한다.
