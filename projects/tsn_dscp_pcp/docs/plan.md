# AM64x TSN DSCP PCP Lab Plan

## 목표

1. `TMDS eth0` control port를 유지한다.
2. `TMDS eth1 <-> SK eth0`, `TMDS eth2 <-> SK eth1` 물리 연결 기준으로 포트 capability를 확인한다.
3. `TMDS -> SK` SSH 제어 경로를 확보한다.
4. `SK`에서 `br-tsn` Linux bridge를 구성하고 L2 forwarding을 확인한다.
5. 이후 DSCP/PCP 실험의 기준 환경으로 문서화한다.

## 진행 순서

1. 포트 link/driver/PHC 상태 확인
2. TMDS 경유 SK 제어 경로 확보
3. SK bridge 구성
4. TMDS endpoint 포트 설정
5. bridge forwarding 및 optional gPTP bridge candidate 확인
6. 결과 문서화

## 현재 주의 사항

- `TMDS eth0` down, IP flush, bridge join 금지
- Host에서 SK direct SSH는 현재 불가 상태일 수 있음
- 필요 시 초기 bootstrap은 별도 경로를 사용하더라도 최종 제어 경로는 `Host -> TMDS -> SK`로 정리한다.
