# Projects Guide

`projects/`는 **보드 하나 또는 여러 보드를 묶는 실험 단위**를 관리하는 공간이다.

특히 다음 조건이면 `projects/<name>/`를 새로 만드는 것이 적합하다.

- apply / test / restore 절차가 실험 단위로 반복될 때
- 두 개 이상 보드의 연결 관계를 함께 기록해야 할 때
- 결과와 실패 원인을 project 범위 안에서 분리 관리하고 싶을 때
- repo 전역 문서보다 더 강한 실험 경계가 필요할 때

## 언제 `projects/`가 맞는가

- SK-AM64B 단독 RPMsg 검증
- SK-AM64B <-> TMDS64EVM gPTP 직결 실험
- custom board boot chain 분리 검증
- board + host helper + deploy/apply script를 함께 관리하는 실습형 작업

## 권장 구조

```text
projects/<project>/
  README.md
  docs/
    plan.md
    board-matrix.md
    results.md
    issues.md
  board/
    apply/restore/test helper script
  logs/
    raw log or captured artifacts if needed
```

## board-matrix 문서 권장 내용

- 참여 보드 ID
- 각 보드의 관리 IP와 관리 interface
- 실험용 직결 interface
- master/slave 또는 requester/responder 같은 역할
- 현재 실험 시점의 active topology

## 현재 예시

- `projects/sk-am64b-rpmsg-test/`: 단일 보드 실험형 project
- `projects/am64x-custom-board-emmc-boot-lab/`: custom board boot 실험형 project
- `projects/am64x-gptp-eth1-lab/`: 다중 보드 직결 gPTP 실험형 project
