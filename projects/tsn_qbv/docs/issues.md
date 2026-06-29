# Qbv Issues

## 상속 이슈

1. SK local `tcpdump -i eth0/eth1`는 switchdev hardware offload 상태에서 `0 packets captured`가 재현된 적이 있다.
2. `ethtool -S eth0/eth1` priority counter는 wire PCP와 직관적으로 일치하지 않을 수 있다.
3. VLAN device를 다시 만들면 `egress-qos-map`과 `tc skbedit priority`를 다시 넣어야 한다.
4. `p0-rx-ptype-rrobin`이 다시 `on`으로 돌아가면 QoS/taprio 해석이 흔들릴 수 있다.
5. TMDS namespace helper 직후 `LOWERLAYERDOWN`처럼 보이더라도, 링크가 늦게 올라오는 경우가 있어 `ip -br link`/`ethtool`로 재확인 후 판정해야 한다.
6. 현재 baseline `mqprio map 2 2 1 0 ...`은 Phase 1의 `p0/p6/p7` TC 분리 목적과 맞지 않는다.
7. `mqprio` map/queue 구성을 바꾸는 작업은 `replace`가 아니라 `del -> add`가 필요할 수 있다.
8. `tc -s qdisc show dev eth0`는 candidate map 상태에서 traffic 후에도 `0 pkt`로 남아 해석 신뢰도가 낮다.
9. `tc -s class show dev eth0`도 같은 상황에서 `0 pkt`로 남아 판정 기준으로 쓰기 어렵다.
10. `ethtool -S eth0`의 `tx_good_frames`/`tx_octets`는 coarse activity 신호로 쓸 수 있지만, `tx_pri*`는 wire PCP와 직접 대응하지 않을 수 있다.
11. switchdev forwarding 경로에서는 `qdisc/class` 통계가 비어도, 같은 egress port를 쓰는 host-originated control path에서는 class separation이 관찰될 수 있다.
12. 현재 환경에서는 `cbs offload 1`이 `Specified device failed to setup cbs hardware offload.`로 reject 된다.
13. taprio running schedule 상태에서는 traffic mapping 변경이 `Changing the traffic mapping of a running schedule is not supported.`로 막힐 수 있다.
14. selective taprio gate mask는 control-path traffic continuity까지 깨뜨릴 수 있으므로, Phase 4 이전까지는 all-open schedule을 reusable state로 유지하는 편이 안전하다.
15. selective taprio schedule은 continuity를 완전히 끊지는 않아도 control RTT/jitter를 키울 수 있다.
16. selective taprio가 걸린 same port에서 gPTP를 직접 돌리면 `tx timestamp timeout`과 `send peer delay request failed`로 불안정할 수 있다.
17. 현재 direct `SK eth1 <-> TMDS eth2` 경로에서도 BMCA 후 `UNCALIBRATED`에서 멈추며 stable `SLAVE`는 아직 재현하지 못했다.
18. `taprio` 제거, `switch_mode=false`, PHC epoch 정렬, `tx_timestamp_timeout` 증가 후에도 SK `eth1`에서 `tx timestamp timeout`이 다시 재현될 수 있다.
19. direct path에서는 `Pdelay_Req/Resp/Resp_Follow_Up`와 `Sync/Announce`가 실제 왕복하므로, 현재 남은 문제는 frame 부재보다 ptp4l state convergence 쪽에 더 가깝다.
20. 재부팅 후 분리 검증에서는 software `bridge only`는 통과했지만 `switch_mode=true`가 들어가는 순간 `TMDS eth2`가 `UNCALIBRATED`에서 멈췄다.
21. 같은 분리 검증에서 `switch_mode=true` 상태의 SK `eth1`는 `master sync timeout`, `master tx announce timeout`를 반복했다.
22. 같은 상태에서 SK `eth1`의 `ale_drop`, `rx_port_mask_drop`가 증가해, switch_mode 경로의 포트 마스킹/forwarding 관여 가능성을 의심해야 한다.
23. endpoint Phase A 실험 중 VLAN subinterface 주소가 의도치 않게 `169.254.x.x` link-local로 돌아가는 경우가 있었다. 공존 실패 판정 전에 반드시 test IP를 다시 확인해야 한다.
24. SK CPSW endpoint에서 `hardware taprio flags 2`가 항상 reject 되는 것은 아니다. long-interval 시도는 `No fetch RAM`으로 실패했지만, TI reference와 같은 `125 us / 125 us / 250 us`, `num_tc 3`, `queues 1@0 1@1 1@2` schedule은 `SK eth1`에서 apply 성공했다.
25. TMDS ICSSG endpoint의 multi-TC hardware taprio는 기본 TX queue 상태에서는 `Queues ... exceed the 1 TX queues available`로 reject 되지만, `eth2 down -> ethtool -L eth2 tx 3 -> eth2 up` 후에는 queue prerequisite를 충족할 수 있다.
26. TMDS ICSSG endpoint는 CPSW와 같은 `500 us` cycle을 그대로 받지 않고, `cycle_time 500000 is less than min supported cycle_time 1000000` 제약이 있다. 현재 확인된 최소 동작 cycle은 `1 ms`다.
27. TMDS ICSSG sender 경로에서도 VLAN `egress-qos-map`이 없으면 `skbedit priority` counter가 증가해도 wire PCP는 `p0`로 보일 수 있다.
28. `TMDS eth1(CPSW)`는 hardware taprio driver 자체가 안 되는 것이 아니라, 현재 프로젝트에서는 `TMDS eth0`를 control 포트로 유지해야 해서 `p0-rx-ptype-rrobin off` prerequisite를 안전하게 맞추기 어렵다.
29. `TMDS eth1(CPSW)`에서 `p0-rx-ptype-rrobin`를 끄려는 시도는 현재 control-port model에서 `Device or resource busy`로 막혔다.
30. `SK eth0(CPSW) -> TMDS eth1(CPSW)`는 `500 us` hardware taprio와 gPTP coexistence까지 성공했다.
31. `SK eth1(CPSW) -> TMDS eth2(ICSSG)`의 same-port hardware taprio + gPTP는 traffic은 유지되지만 gPTP state가 `FAULTY`, `MASTER/SLAVE` 재천이를 보여 아직 stable success로 보기 어렵다.
32. `TMDS eth2(ICSSG) -> SK eth1(CPSW)`의 same-port hardware taprio + gPTP는 `timed out while polling for tx timestamp`, `send peer delay request failed`로 실패했다.
33. 같은 `TMDS eth2(ICSSG) -> SK eth1(CPSW)` 경로라도 software taprio로 바꾸면 gPTP와 traffic이 다시 공존할 수 있다.

## Phase A closeout 이후 남은 질문

1. `TMDS eth2(ICSSG)`의 hardware `taprio + gPTP` failure를 driver/timestamp path 기준으로 더 분해할 것인가
2. `SK eth1(CPSW) -> TMDS eth2(ICSSG)`의 hardware coexistence 불안정을 stable success까지 밀 것인가
3. `TMDS eth1(CPSW) -> SK eth0(CPSW)` reverse direction을 control-port model 변경 없이 안전하게 열 수 있는가
