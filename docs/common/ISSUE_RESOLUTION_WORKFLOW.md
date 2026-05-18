# Bring-up Issue Resolution Workflow

이 문서는 TI bring-up 과정에서 발생하는 크고 작은 이슈를 **어떻게 기록하고, 어떻게 정리하고, 어디에 남길지**를 정의하는 lightweight workflow이다.

목표:

- 조사 중인 내용과 해결된 내용을 섞지 않기
- 나중에 "무슨 문제가 있었고 어떻게 끝났는가"를 빠르게 다시 찾기
- 긴 research note와 짧은 해결 히스토리를 역할별로 분리하기

## 기본 원칙

한 이슈는 보통 다음 네 층으로 나눠서 관리한다.

1. **원본 증적**
2. **조사 노트**
3. **짧은 해결 이슈 히스토리**
4. **남은 작업 추적**

이 네 층을 같은 문서에 다 몰아넣지 않는다.

## 1. 원본 증적

대상:

- UART boot log
- kernel dmesg
- U-Boot log
- 명령 결과 원문
- crash / reboot 직후 출력

저장 위치:

- `logs/runtime_log`
- `docs/bringup-logs/`

원칙:

- 원문성을 우선한다.
- 요약보다 "그때 실제로 무엇이 보였는가"를 남긴다.
- `logs/runtime_log`는 **UART 기준 boot/reboot/early runtime evidence** 용도로 본다.
- OS 부팅 이후의 steady-state 문제는 `journalctl`, `dmesg`, `/sys`, 서비스 상태, 애플리케이션 출력과 함께 교차 확인한다.

## 2. 조사 노트

대상:

- 아직 결론이 나지 않은 원인 가설
- 여러 로그/문서/코드 비교
- false start
- 조사 중 판단 변화

저장 위치:

- `docs/research/YYYY-MM-DD_<topic>.md`

원칙:

- 길어져도 괜찮다.
- 사실/가설/판단을 분리한다.
- 최종 결론이 바뀌더라도 조사 흔적은 보존한다.

## 3. 짧은 해결 이슈 히스토리

대상:

- 해결되었거나 상태가 정리된 이슈
- 나중에 1~2분 안에 다시 이해해야 하는 이슈

저장 위치:

- 보드 의존적이면 `docs/boards/<board-name>/issues/`
- 여러 보드에 그대로 재사용될 수준이면 `docs/common/` 검토

권장 파일명:

```text
YYYY-MM-DD_<short-topic>.md
```

권장 항목:

- 증상
- 1차 원인
- 조치
- 재조사 결과
- 최종 원인
- 최종 조치
- 검증
- 후속 메모

원칙:

- research note보다 훨씬 짧아야 한다.
- 이슈의 큰 흐름과 결론만 남긴다.
- 관련 상세 조사 문서 링크를 꼭 남긴다.

## 4. 남은 작업 추적

대상:

- 아직 끝나지 않은 후속 액션
- 다음 실험
- 재검토 포인트

저장 위치:

- `docs/tasks/TASK_BOARD.md`

원칙:

- 작업 보드는 짧게 유지한다.
- 해결된 이슈의 상세 내용은 task board에 남기지 않는다.
- 완료된 이슈는 issue history 문서로 승격하고, task board에는 결과만 남긴다.

## 실제 운영 순서

새 이슈가 생기면 다음 순서로 처리한다.

### Step 1. 증적 확보

- boot/reboot/early runtime 이슈면 `logs/runtime_log` 확인
- 필요 시 `docs/bringup-logs/` 에 세션/재현 기록 추가

### Step 2. 조사 시작

- `docs/research/YYYY-MM-DD_<topic>.md` 생성
- 가설, 비교, 로그, 코드 근거를 누적

### Step 3. 해결 또는 상태 정리

- 이슈가 해결되거나 원인이 충분히 정리되면
- `docs/boards/<board-name>/issues/YYYY-MM-DD_<topic>.md` 작성

### Step 4. 작업 보드 갱신

- 남은 액션은 `docs/tasks/TASK_BOARD.md` 에 추가
- 끝난 항목은 완료 처리

## 언제 skill보다 문서 workflow가 더 적합한가

다음 조건이면 skill보다 문서 workflow가 더 적합하다.

- 사람/AI 모두 같은 저장소 규칙을 따라야 함
- 조사/기록 위치가 중요함
- 판단 기준을 repo 안에 남겨야 함
- 빈번하지만 복잡하지 않은 반복 작업임

현재 이 저장소의 이슈 히스토리 관리는 여기에 해당한다.

즉 현재는 **skill보다 repo 문서 workflow가 우선**이다.

## 언제 별도 skill을 고려할 수 있는가

다음이 반복되면 그때 skill을 검토한다.

- 매번 같은 문서 세트 생성
- 같은 확인 순서 반복
- 같은 명령/로그/검증 패턴 반복
- 여러 agent가 항상 같은 방식으로 움직여야 함

예를 들면 나중에:

- issue triage
- boot-failure investigation
- rootfs deploy incident handling

이 아주 규칙적으로 굳으면 skill로 승격할 수 있다.

## 현재 저장소 기준 권장 답

현재는 다음 조합이 가장 적절하다.

1. `docs/common/ISSUE_RESOLUTION_WORKFLOW.md` 로 workflow 정의
2. `docs/templates/ISSUE_HISTORY.template.md` 로 템플릿 제공
3. `AI_AGENT_GUIDE.md` 와 `docs/README.md` 에 링크 추가

즉 지금 단계에서는

```text
skill을 새로 만들기보다는
repo 내부 workflow + template + guide link
```

가 더 가볍고 유지보수하기 쉽다.
