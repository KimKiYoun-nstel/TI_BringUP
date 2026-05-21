# 완료 메모

이 Phase 2 프로젝트는 Phase 1과 분리된 별도 프로젝트이며 경로는 `projects/am64x-r5f-button-event-lab` 이다.

## 구현 범위

- `am64x_r5f_button_event_lab_r5fss0_0_freertos_ti_arm_clang`용 standalone R5F CCS project name 및 output path 정리
- `MCU_GPIO0_6` 기반 R5F SW1 입력 처리, both-edge interrupt, task context 기준 30 ms debounce 구현
- `PING`, `STATUS`, `BUTTON_STATUS`, `BUTTON_WAIT`, `BUTTON_MONITOR`, `EVENT_MONITOR` 텍스트 프로토콜 구현
- A53 `r5ctl`의 button status/wait/monitor 흐름 구현
- host build/deploy script와 보드 reboot 기반 apply/restore/test script 추가
- protocol, board apply, tests, resource ownership, issues, completion 상태를 다루는 Phase 2 문서 추가

## 완료 판정 관련 메모

live-board 완료 판정에는 실제 부팅된 이미지 기준으로 다음 증적이 필요하다.

- SW1을 눌렀다 떼는 동안의 `r5ctl button monitor`
- GPIO / pinctrl ownership 확인 증적
