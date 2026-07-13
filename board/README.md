# Board Inventory Guide

`board/`는 **현재 운용 중인 보드 식별 정보와 접속 프로필**을 관리하는 공간이다.

이 디렉터리는 장기 해설 문서 저장소인 `docs/boards/`와 역할이 다르다.

## 역할 구분

- `board/`
  - 현재 실험에 쓰는 보드 식별자
  - SSH 사용자
  - 관리 IP
  - 관리용 기본 interface
  - 보드 간 직결 실험에 쓰는 interface
  - 현재 active target 여부
- `docs/boards/`
  - 보드 개요
  - 장기 메모
  - 해결된 이슈 히스토리
  - bring-up 결과 해설
- `projects/`
  - 두 개 이상 보드를 묶는 실험 단위
  - 특정 기간의 apply/test/restore 절차
  - 실험별 board matrix와 결과

## 권장 구조

```text
board/
  README.md
  inventory.yaml                  # repo 기준 보드 목록과 현재 식별자
  sk-am64b/
    README.md
    profile.yaml                  # 현재 접속/운용 프로필
  tmds64evm/
    README.md
    profile.yaml
  cpu_brd_v03_pba_260511/
    README.md
    profile.yaml
```

## 사용 원칙

- `inventory.yaml`은 repo 차원의 빠른 인덱스다.
- 상세 접속 정보는 각 `profile.yaml`에서 관리한다.
- IP는 실험 시점에 따라 바뀔 수 있으므로, 장기 해설 문서보다 여기에서 먼저 갱신한다.
- 보드별 고정 메모와 판단은 `docs/boards/<board>/`에 남긴다.
- 두 보드 이상을 함께 다루는 실험은 `projects/<project>/docs/board-matrix.md` 같은 문서로 관리한다.
