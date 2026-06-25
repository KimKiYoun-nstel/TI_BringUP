# AM64x gPTP Lab Plan

## 목표

1. `SK-AM64B eth1 <-> TMDS64EVM eth2` direct link를 고정 검증 경로로 둔다.
2. 양쪽 `ptp4l` 상태 전이와 MASTER/SLAVE 형성을 확인한다.
3. SLAVE 쪽 offset/path delay 안정화를 확인한다.
4. `phc2sys`로 `CLOCK_REALTIME` 동기화 여부를 확인한다.
5. local L2 switch 경유에서는 frame 송수신과 형상 완성 여부를 direct 경로와 분리해서 판단한다.

## 진행 순서

1. 보드 inventory/profile 최신화
2. `SK eth1`, `TMDS eth2` link/hardware timestamp 재확인
3. `/tmp/gptp.cfg` 생성
4. 양쪽 `ptp4l` 실행
5. `MASTER/SLAVE` 상태 전이 기록
6. SLAVE `phc2sys` 실행
7. 필요 시 `tcpdump`로 `0x88f7` frame 캡처

## 현재 주의 사항

- control port는 `SK eth0`, `TMDS eth0`로 유지한다.
- TMDS64EVM은 `eth2`가 down 상태로 부팅될 수 있다.
- `TMDS eth0`, `TMDS eth1`은 local L2에 연결되어 있어도 direct gPTP canonical 경로는 `TMDS eth2`로 유지한다.
- PHC 초기 epoch가 wall clock와 다르면 MASTER 측에서 먼저 보정해야 한다.
