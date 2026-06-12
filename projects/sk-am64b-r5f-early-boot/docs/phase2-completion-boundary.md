# Phase2 Completion Boundary

## 목적

이 문서는 현재 repo에서 **로컬로 끝낼 수 있는 Phase2 범위**와
반드시 board/UART 확인이 필요한 마지막 경계를 분리한다.

## repo 안에서 완료 가능한 항목

- heartbeat draft source 정리
- heartbeat SHM ABI 정리
- heartbeat local buildable draft 검증
- Linux appimage 입력/ staging 정책 정리
- R5F multicore appimage generation helper 연결
- Linux appimage generation helper 연결
- dry-run / local image generation 산출물 확보
- TI cfg absolute offset model에 맞춘 write 절차 정리

## board-side가 반드시 필요한 항목

Phase2의 완료 조건 중 다음은 repo 로컬만으로는 닫을 수 없다.

1. SBL이 R5F app을 Linux보다 먼저 load/start 하는지
2. 이후 A53 Linux가 실제로 boot 하는지
3. Linux boot 이후에도 R5F heartbeat가 유지되는지
4. UART 상에서 `SBL -> R5F -> A53 Linux` 흐름이 보이는지

즉 Phase2를 repo 기준으로는 "artifact set ready" 까지 밀 수 있지만,
최종 완료 판정은 board/UART 검증이 있어야 닫힌다.

## 현재 해석

현재 시점의 가장 현실적인 표현은 다음이다.

```text
Phase2 early-boot closure:
  LPDDR4 reginit + dual-boot OSPI Linux boot verified

Phase2 follow-up pending:
  custom firmware/application behavior verification
```

이 follow-up 항목은 당분간 root task board가 아니라
`projects/sk-am64b-r5f-early-boot/` 내부 문서에서만 언급한다.
