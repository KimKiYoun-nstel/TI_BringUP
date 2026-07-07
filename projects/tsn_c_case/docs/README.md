# TSN C Case Docs Guide

## 먼저 볼 문서

- `closure-status.md`
  - 프로젝트 마감 기준의 최종 상태, workspace residue, boot image 연관성
- `2026-07-06_gptp-bridge-fresh-start-validation.md`
  - donor-equivalent bridge gPTP 여부를 가른 최종 기능 검증 문서
- `phase1-summary.md`
  - Path B bring-up 성공 범위와 patch/provenance 자산을 고정한 중간 단계 문서
- `resource-ownership-audit.md`
  - RM ownership root cause와 최종 해결 근거
- `powerclock-trace-result.md`
  - 초기 `PowerClock_init()` blocker 분석과 remoteproc-hosted skip 정책 근거

위 문서들이 현재 사람이 직접 보고 판단해야 하는 canonical 문서다.

중요한 구분:

- `phase1-summary.md`는 bring-up 성공 범위를 정리한 문서다.
- 최종 기능 결론은 `2026-07-06_gptp-bridge-fresh-start-validation.md`와
  `closure-status.md` 기준으로 본다.

## archive 문서

- `archive/` 아래 문서는 단계별 진행 중 남긴 작업 메모와 중간 판단 기록이다.
- 일부 문서는 당시 시점의 가설이나 미완료 상태를 기준으로 작성됐으므로,
  현재 최종 상태와 충돌할 수 있다.
- archive 문서는 필요할 때만 참조하고, 현재 판단은 항상 상위 3개 canonical 문서 기준으로 본다.
