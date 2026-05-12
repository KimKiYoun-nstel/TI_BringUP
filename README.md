# TI_BringUP

TI AM64x 계열 보드 브링업과 Embedded Linux BSP 학습/작업을 위한 프로젝트 지식 저장소입니다.

이 저장소의 목적은 단순 자료 수집이 아니라, 레퍼런스 보드(TMDS64EVM, SK-AM64B)에서 검증한 내용과 의사결정, 실패 로그, 재사용 가능한 절차를 누적하여 추후 자체 보드 BSP 포팅/브링업에 재사용하는 것입니다.

## 운영 원칙

- ChatGPT Project는 작업실로 사용합니다.
- 이 Git repo는 장기 기억장치와 작업 장부로 사용합니다.
- 모든 대화를 저장하지 않습니다. 장기 보관 가치가 있는 항목만 문서화합니다.
- 문서 분류 기준과 `docs/` 구조 설명은 `docs/README.md`를 기준 문서로 삼습니다.
- 확정된 판단은 `docs/decisions/DECISION_LOG.md`에 기록합니다.
- 조사/학습 내용은 `docs/research/RESEARCH_NOTES.md`에 기록합니다.
- 보드별 검증 내용은 `docs/boards/<board-name>/` 아래에 기록합니다.
- 실제 로그, 명령 결과, 실패 원인은 `docs/bringup-logs/` 아래에 날짜별로 보관합니다.

## Docs 구조

`docs/`는 단순 보관 폴더가 아니라, 추후 자체 보드 BSP 포팅과 브링업에 재사용할 지식 베이스입니다.

- [`docs/README.md`](docs/README.md): 문서 분류 원칙과 폴더별 사용 기준
- `docs/common/`: 보드 공통 개념, 용어, 범용 레퍼런스
- `docs/boards/`: 보드별 고정 메모와 검증 결과
- `docs/bringup-logs/`: 날짜 기준 실행 로그와 원본 증적
- `docs/setup/`: SDK, 툴체인, 호스트 환경 준비 절차
- `docs/research/`: 조사 중인 메모와 비교/가설 정리
- `docs/decisions/`: 채택한 결정과 근거
- `docs/tasks/`: 현재 작업 추적과 다음 액션
- `docs/templates/`: 반복 작성용 템플릿
- `docs/outputs/`: 공유용 체크리스트, 비교표, 요약 산출물

상세 기준은 [`docs/README.md`](docs/README.md)를 참고합니다.

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
    setup/
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
git add README.md docs PROJECT_BRIEF.md AI_AGENT_GUIDE.md
git commit -m "docs: 브링업 문서 정리"
```
