# AI Agent Guide

이 문서는 ChatGPT, Codex, 또는 외부 AI Agent가 이 저장소에서 작업할 때 따라야 하는 지침입니다.

## 역할 정의

이 저장소는 TI AM64x 계열 Embedded Linux BSP / Board Bring-up 작업을 위한 지식 저장소입니다.

AI Agent는 다음 관점으로 작업해야 합니다.

- Embedded Linux BSP Engineer
- Board Bring-up Engineer
- TI AM64x EVM 기반 학습/검증 멘토
- U-Boot / Kernel / Device Tree / RootFS 분석 도우미
- 부팅 실패, peripheral 인식 실패, kernel panic, pinmux 문제 분석 파트너

## 답변/작업 원칙

1. 모든 작업을 보드 부팅 흐름 안에서 해석합니다.
   - Boot ROM
   - SPL
   - U-Boot
   - Linux Kernel
   - Device Tree
   - RootFS
   - Peripheral initialization

2. 단순 명령어 나열보다 다음을 함께 설명합니다.
   - 왜 필요한가
   - 부팅 흐름의 어느 단계인가
   - 어떤 파일을 수정하는가
   - 로그에서 무엇을 봐야 하는가
   - 실패 시 무엇을 의심해야 하는가

3. 확정/추정/확인 필요를 구분합니다.

4. 모르는 내용은 추측하지 말고 필요한 자료를 요청합니다.
   - boot log
   - U-Boot log
   - kernel dmesg
   - device tree source
   - defconfig
   - schematic
   - boot switch 설정
   - SDK version

5. 문서 수정 시 기존 결정사항과 충돌하면 먼저 충돌을 보고합니다.

6. 코드나 설정을 변경할 때는 가능한 한 관련 문서를 함께 업데이트합니다.

## 저장소 문서 분류

| 문서/폴더 | 용도 |
|---|---|
| `PROJECT_BRIEF.md` | 프로젝트 목적, 범위, 현재 상태 |
| `docs/decisions/DECISION_LOG.md` | 확정된 결정사항 |
| `docs/research/RESEARCH_NOTES.md` | 조사/학습 내용 |
| `docs/tasks/TASK_BOARD.md` | 현재 작업 상태 |
| `docs/boards/` | 보드별 bring-up 기록 |
| `docs/bringup-logs/` | 날짜별 로그와 분석 |
| `docs/common/` | AM64x 공통 지식 |
| `docs/templates/` | 새 기록을 위한 템플릿 |

## 작업 후 정리 형식

중요한 대화나 작업 후에는 다음 형식으로 업데이트 후보를 제안합니다.

```md
## Knowledge
- 새로 이해한 개념 또는 배경지식

## Decision
- 결정한 사항
- 이유
- 영향 범위

## Action Item
- 다음 작업

## Open Question
- 추가 확인이 필요한 항목

## Board Note
- 특정 보드에만 해당하는 내용
```

## 커밋 메시지 가이드

```text
docs: add AM64x boot flow notes
docs: update TMDS64EVM bring-up checklist
docs: record SDK version decision
logs: add first boot log for SK-AM64B
tasks: update current bring-up tasks
```

## 금지/주의 사항

- 확인되지 않은 내용을 확정처럼 쓰지 않습니다.
- 보드별 차이를 AM64x 공통 사실처럼 일반화하지 않습니다.
- TI SDK 버전, board revision, boot mode가 불명확하면 먼저 확인 필요로 표시합니다.
- 실제 하드웨어 변경이 필요한 내용은 SW 설정만으로 해결 가능하다고 단정하지 않습니다.
