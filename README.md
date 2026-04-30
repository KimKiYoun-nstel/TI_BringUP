# TI_BringUP

TI AM64x 계열 보드 브링업과 Embedded Linux BSP 학습/작업을 위한 프로젝트 지식 저장소입니다.

이 저장소의 목적은 단순 자료 수집이 아니라, 레퍼런스 보드(TMDS64EVM, SK-AM64B)에서 검증한 내용과 의사결정, 실패 로그, 재사용 가능한 절차를 누적하여 추후 자체 보드 BSP 포팅/브링업에 재사용하는 것입니다.

## 운영 원칙

- ChatGPT Project는 작업실로 사용합니다.
- 이 Git repo는 장기 기억장치와 작업 장부로 사용합니다.
- 모든 대화를 저장하지 않습니다. 장기 보관 가치가 있는 항목만 문서화합니다.
- 확정된 판단은 `docs/decisions/DECISION_LOG.md`에 기록합니다.
- 조사/학습 내용은 `docs/research/RESEARCH_NOTES.md`에 기록합니다.
- 보드별 검증 내용은 `docs/boards/<board-name>/` 아래에 기록합니다.
- 실제 로그, 명령 결과, 실패 원인은 `docs/bringup-logs/` 아래에 날짜별로 보관합니다.

## 시작 구조

```text
TI_BringUP/
  README.md
  AI_AGENT_GUIDE.md
  PROJECT_BRIEF.md
  docs/
    common/
    boards/
    decisions/
    research/
    tasks/
    bringup-logs/
    templates/
    outputs/
```

## 현재 대상 보드

- TI TMDS64EVM
- TI SK-AM64B
- 추후 자체 개발 보드

## 빠른 사용법

새로운 대화나 작업 후 다음 질문으로 정리합니다.

```text
이번 대화에서 장기 보관할 항목만 Knowledge / Decision / Action Item / Open Question / Board Note 형식으로 정리해줘.
```

정리된 내용은 관련 Markdown 파일에 반영하고 커밋합니다.

```bash
git add docs PROJECT_BRIEF.md AI_AGENT_GUIDE.md
git commit -m "docs: update bring-up notes"
```
