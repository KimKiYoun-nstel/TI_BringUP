# P3 Qbu/IET Timing Variance 원인분리 결과

## 목적과 범위

50 Mbit/s preemptible + 50 Mbit/s express의 드문 express loss와 active/degraded 혼재가
MAC Merge activation 자체의 failure인지, sender userspace generator scheduling/burst timing의
영향인지 분리했다. 기존 rate matrix는 반복하지 않고 동일 rate, 1472 B packet, 300 s duration만
사용했다.

SK receiver는 CPU1이 offline이므로 receiver-side CPU A/B는 수행하지 않았다. TMDS sender는
CPU0/CPU1이 online이고, 관찰된 CPSW TX IRQ에서 preemptible TC2는 CPU0, express TC3는 CPU1에서
증가했다. CPU-split 조건은 각각의 iperf3 client를 해당 CPU로 고정했다.

## 실행 정보

| 항목 | 값 |
|---|---|
| Campaign ID | `QBU_1G_TIMING_VARIANCE_01` |
| Raw artifact | `artifacts/p3-qbu-timing-variance-20260803-retry-kst` |
| Path | TMDS `eth1` CPSW sender -> SK `eth1` CPSW receiver |
| On-case | 50 Mbit/s preemptible + 50 Mbit/s express, 1472 B, 300 s x 3 |
| Control | IET off, 동일 offered rate, 30 s x 1, `control-pass` |
| Overall result | `valid: true`, completed 13 runs |

각 run은 UART-only board control/stage, target-side SHA-256 verification, traffic 종료 뒤 cleanup,
bounded SSH raw artifact transfer, test-IP reset 순서를 따랐다. Campaign 종료 뒤 양 board의 `eth1`은
test IP 없음, MM off, default `mq/pfifo_fast`로 확인했다.

## 결과

| Sender condition | Classification | Preemptible loss min/median/max | Express loss min/median/max | Assembly/SMD error | 판정 |
|---|---|---:|---:|---|---|
| scheduler default, iperf3 default 1000 us | `active` 2, `degraded` 1 | 0 / 0 / 0 | 0 / 0 / 1 | SMD error 발생 run 있음 | timing-sensitive |
| preemptible CPU0, express CPU1, 1000 us | `active` 1, `degraded` 2 | 0 / 0 / 0 | 0 / 2 / 7 | SMD error max 7 | CPU split 단독은 악화 |
| scheduler default, 100 us pacing | `active` 2, `degraded` 1 | 0 / 0 / 0 | 0 / 0 / 8 | SMD error max 7 | pacing 단독은 해결 아님 |
| preemptible CPU0, express CPU1, 100 us pacing | `active` 3 | 0 / 0 / 0 | 0 / 0 / 0 | assembly/SMD error 0 | 이 표본에서는 loss-free |


1. 50M/50M loss는 preemptible offered rate 부족이나 MAC Merge inactive로 설명되지 않는다.
   모든 on run에서 preemptible loss는 0이고 Qbu counter causality가 성립했다.
2. CPU affinity와 burst interval은 독립적으로 loss를 제거하지 못했다. 특히 CPU split만 적용한
   조건은 express median loss 2, max 7로 default보다 나빴다.
3. CPU split과 100 us pacing의 결합만 900 aggregate seconds에서 loss/error 없이 반복됐다.
   따라서 current evidence는 sender userspace scheduler placement와 generator burst timing의
   **상호작용**이 express loss에 영향을 준다는 것을 지지한다.
4. 이는 IRQ affinity, NAPI/softirq scheduling, CPSW queue service 중 어느 하나를 단독 원인으로
   확정하지 않는다. receiver CPU1 offline 상태도 receiver-side isolation을 제한한다.


`TMDS: UDP 5002 CPU0 + UDP 5003 CPU1 + iperf3 pacing 100 us`는 다음 진단/confirmation run의
조건으로 유지한다. 그러나 이 3-repeat 결과만으로 production loss-free profile을 채택하지
않는다. production acceptance에는 사전 loss/error bound, 더 긴 duration/repeat, CPU/IRQ online
topology의 고정 및 교란 부하 조건이 필요하다.

## Incomplete Attempt

`artifacts/p3-qbu-timing-variance-20260803-kst`의 첫 off control은 board traffic과 cleanup은
완료했지만 TMDS `eth0` control-link recovery 전에 artifact transfer를 시작해 `No route to host`로
failure-stop 됐다. summary aggregate에는 포함하지 않았다. raw evidence는 이후 UART로 test IP만
일시 복구해 양 board에서 회수했고 즉시 제거했다.

이 incident에 따라 artifact collector는 cleanup 뒤 TMDS management link recovery를 host-side 총
90초 bound 안에서 재시도한다. 이 변경은 traffic/Qbu setup/counter criterion을 바꾸지 않는다.
