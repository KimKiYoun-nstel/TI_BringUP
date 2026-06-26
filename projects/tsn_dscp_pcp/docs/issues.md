# AM64x TSN DSCP PCP Lab Issues

## 현재 이슈

- 초기 상태에서 Host -> SK direct SSH는 불가했다.
- SK reachable control IP가 없어 UART bootstrap이 필요했다.
- `TMDS eth1`, `eth2`를 endpoint namespace로 분리하면 root namespace 기반 단순 SSH/test 절차가 복잡해질 수 있다.
- SK bridge는 L2 forwarding을 확인했지만, 이것만으로 TSN switch 또는 gPTP time-aware bridge를 확정하지는 않는다.
- persistent file은 live rootfs에 설치했지만, cold boot 직후 자동 복구 로그는 후속 세션에서 별도 보강 가능하다.
- TMDS는 boot 초기에 `eth1` bring-up race가 있어, 단순 `.network` 파일만으로는 재부팅 직후 desired state가 즉시 안 올라올 수 있었다.
- 이를 보완하기 위해 `ti-tsn-dscp-pcp-tmds.service` boot-time re-apply service를 추가했다.
- Test B 재현 시 `TMDS ep2 eth2.301`을 다시 만들면 `egress-qos-map`도 반드시 다시 넣어야 한다. 이 설정이 빠지면 sender-side부터 `p0`가 나와 false fail처럼 보일 수 있다.
- `10.301.0.x/24`, `10.300.0.x/24` 같은 표기는 유효한 IPv4가 아니다. 실제 시험에는 `10.31.0.x/24`, `10.30.0.x/24`를 사용해야 한다.
- SK `tcpdump -i eth0`, `tcpdump -i eth1`는 switchdev hardware offload 상태에서 `0 packets captured`가 나올 수 있다. 따라서 SK local capture 부재를 곧바로 forwarding failure로 단정하지 않는다.
