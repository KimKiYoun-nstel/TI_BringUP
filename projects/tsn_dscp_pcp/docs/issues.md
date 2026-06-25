# AM64x TSN DSCP PCP Lab Issues

## 현재 이슈

- 초기 상태에서 Host -> SK direct SSH는 불가했다.
- SK reachable control IP가 없어 UART bootstrap이 필요했다.
- `TMDS eth1`, `eth2`를 endpoint namespace로 분리하면 root namespace 기반 단순 SSH/test 절차가 복잡해질 수 있다.
- SK bridge는 L2 forwarding을 확인했지만, 이것만으로 TSN switch 또는 gPTP time-aware bridge를 확정하지는 않는다.
- persistent file은 live rootfs에 설치했지만, cold boot 직후 자동 복구 로그는 후속 세션에서 별도 보강 가능하다.
- TMDS는 boot 초기에 `eth1` bring-up race가 있어, 단순 `.network` 파일만으로는 재부팅 직후 desired state가 즉시 안 올라올 수 있었다.
- 이를 보완하기 위해 `ti-tsn-dscp-pcp-tmds.service` boot-time re-apply service를 추가했다.
