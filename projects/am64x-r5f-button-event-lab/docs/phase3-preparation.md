# Phase 3 준비 메모

## 목적

이 문서는 현재 저장소에 남아 있는 Phase 1/2 자산을 기준으로,
Phase 3 상태 모델 / command protocol 정리를 **어떤 기준선에서 시작해야 하는지**를
명확히 하기 위한 준비 문서다.

이번 문서는 새 아키텍처를 처음부터 설계하기보다,
이미 구현된 Phase 2 baseline 위에 Phase 1 기능을 어떻게 재통합할지 정리하는 데 초점을 둔다.

## 현재 기준선

현재 저장소에서 Phase 3의 직접 출발점으로 볼 수 있는 프로젝트는
`projects/am64x-r5f-button-event-lab`이다.

이유:

- Phase 2 프로젝트는 이미 `rpmsg_chrdev` endpoint `14`를 사용한다.
- A53 `r5ctl`은 단발 command path와 persistent monitor path를 모두 가진다.
- R5F firmware는 ISR에서 직접 RPMsg send를 하지 않고, task context에서 event를 전송한다.
- reboot 기반 apply/restore/test 흐름이 이미 정리되어 있다.

현재 확인된 baseline은 다음과 같다.

```text
Target R5F      : 78000000.r5f
Firmware name   : am64-main-r5f0_0-fw
RPMsg service   : rpmsg_chrdev
RPMsg endpoint  : 14
A53 CLI         : r5ctl
Phase 2 input   : SK-AM64B SW1 -> MCU_GPIO0_6
Phase 1 output  : MCU_GPIO0_8
```

## 수정된 전제

기존 `.agents/phase3_status_protocol_plan.md`는 Phase 2 input을
`MCU_GPIO0_7 / MCU Connector Pin 11`로 가정하고 있다.

하지만 현재 저장소의 실제 Phase 2 구현과 문서는 다음 기준을 사용한다.

```text
Input source : SK-AM64B SW1
Input GPIO   : MCU_GPIO0_6
Signal type  : active-low
```

따라서 Phase 3 준비는 **`MCU_GPIO0_7` 가정이 아니라 `SW1 -> MCU_GPIO0_6` baseline** 위에서 진행해야 한다.

이 전제 수정은 문서와 구현 모두에 영향을 준다.

- `status`의 input 관련 필드
- `event` payload 예시
- regression test 절차
- resource ownership 설명
- SYSFW RM 관련 주의사항

## Phase 3에서 유지할 것

다음 항목은 현재 baseline에서 유지하는 편이 안전하다.

1. 문자열 기반 command protocol
2. `rpmsg_chrdev` 단일 service / endpoint 사용
3. reboot 기반 firmware 적용 흐름
4. R5F trace를 통한 디버그 관찰 방식
5. ISR 최소화 + deferred event send 구조

문자열 기반 protocol은 현재처럼 trace 확인과 CLI 수동 검증이 쉽고,
Phase 1/2 자산을 그대로 이어가기 좋다.

## Phase 3에서 먼저 정리할 것

Phase 3는 새 프로젝트를 만드는 단계가 아니라,
현재 Phase 2 baseline에 상태 모델과 GPIO output 기능을 재통합하는 단계로 보는 것이 적절하다.

우선순위는 다음과 같다.

### 1. 상태 모델 추가

R5F firmware 내부에 최소 상태 구조를 둔다.

권장 관리 항목:

```text
- firmware version
- uptime
- output gpio id / cached state
- input gpio id / last stable state
- event count
- last event type / gpio / timestamp
- last command id or request id
- last error
```

### 2. Protocol shape 정리

외형은 text command를 유지하되, 내부 개념은 다음을 명확히 구분한다.

```text
request
response
event
status code
request id
```

특히 request id 또는 sequence 개념은 Phase 3에서 우선 검토해야 한다.
현재 Phase 1 문서에 남아 있는 late reply / stale reply 위험을 줄이기 위해서다.

### 3. Phase 1 GPIO output 재통합

현재 Phase 2 firmware는 `GPIO_*` 명령을 `ERR UNSUPPORTED_CMD`로 처리한다.
Phase 3에서는 이를 단순 복원하기보다,
상태 모델과 error handling 안으로 다시 넣어야 한다.

즉 다음 순서가 적절하다.

```text
ping/status
  -> gpio list/get/set
  -> event get/monitor
```

### 4. CLI 구조 정리

최소 CLI 목표는 다음으로 둔다.

```text
r5ctl ping
r5ctl status
r5ctl gpio list
r5ctl gpio get <id>
r5ctl gpio set <id> <0|1>
r5ctl event get
r5ctl event monitor
```

단, 내부 구현은 현재처럼
단발 command path와 persistent event monitor path를 분리해 유지하는 편이 낫다.

## 권장 아키텍처 방향

### 단일 endpoint 유지

현재 repo 기준으로는 command/response와 event stream을 별도 endpoint로 쪼개기보다,
**하나의 endpoint에서 message type으로 구분**하는 편이 자연스럽다.

이유:

- 현재 Phase 2 구조가 이미 그 방향에 가깝다.
- host side `event monitor` 흐름을 크게 바꾸지 않아도 된다.
- 추가 endpoint 관리보다 request/reply 식별 문제가 더 우선이다.

### status는 hybrid policy 사용

`status`는 전부 hardware readback으로 밀기보다,
cached state 중심 + 필요한 readback만 보조 정보로 두는 편이 안전하다.

예:

- event count / last event / last error -> cached state
- output last commanded state -> cached state
- input stable state -> cached state
- 실제 GPIO readback -> 가능하면 별도 field 또는 보조 정보

그 이유는 현재 output 쪽 connector-level 검증과 input ownership 검증이
완전히 닫힌 상태가 아니기 때문이다.

## 구현 전 체크리스트

Phase 3 구현 시작 전 다음을 먼저 확인한다.

1. Phase 3 baseline 프로젝트를 `projects/am64x-r5f-button-event-lab`로 확정한다.
2. input baseline을 `SW1 -> MCU_GPIO0_6`로 문서에 명시한다.
3. Phase 1 output target `MCU_GPIO0_8`을 재사용할지 확인한다.
4. request id / sequence 도입 여부를 먼저 결정한다.
5. event queue depth와 timeout 정책을 정한다.
6. regression 기준을 jumper 기반이 아니라 현재 Phase 2 baseline 기준으로 다시 적는다.
7. boot image / SYSFW RM 변경이 다시 필요한지 확인한다.

## 검증 기준

Phase 3 준비 완료 판정은 다음 질문에 답할 수 있으면 된다.

1. 어떤 프로젝트를 Phase 3 베이스로 삼는가?
2. input baseline이 무엇인가?
3. output baseline이 무엇인가?
4. status/event/error format을 어디까지 text로 유지할 것인가?
5. timeout / stale reply 위험을 어떻게 다룰 것인가?
6. 어떤 문서와 어떤 로그를 Phase 3 regression evidence로 사용할 것인가?

구현 이후의 기능 검증은 별도 Phase 3 test 문서에서 상세화한다.

## 리스크와 확인 필요 항목

### 1. SYSFW RM 의존성

`SW1 -> MCU_GPIO0_6` interrupt 경로는 단순 firmware 수정만으로 끝나는 주제가 아니다.
boot image와 SYSFW RM 설정 상태가 실제 보드 baseline과 맞는지 계속 확인해야 한다.

### 2. stale reply 위험

긴 command 또는 timeout 이후 늦은 응답이 다음 command에 섞일 가능성은
Phase 3 protocol에서 반드시 줄여야 한다.

### 3. output mapping 검증 수준

`MCU_GPIO0_8`은 현재 Phase 1 baseline의 output target이지만,
board connector 관점의 완전한 확정값이라고 단정하지는 않는다.

### 4. 문서 위치 혼선

초기 계획 문서는 `r5f-hw-control/` 같은 별도 트리를 제안하지만,
현재 저장소에서는 project-local 문서를 `projects/.../docs`에 두는 편이 자연스럽다.

## 관련 문서

- Phase 2 protocol: `projects/am64x-r5f-button-event-lab/docs/protocol.md`
- Phase 2 resource ownership: `projects/am64x-r5f-button-event-lab/docs/resource-ownership.md`
- Phase 2 completion note: `projects/am64x-r5f-button-event-lab/docs/completion.md`
- SK-AM64B board issue note: `docs/boards/SK-AM64B/2026-05-21_SK-AM64B_phase2-sw1-r5f-gpio-irq-sysfw-rm.md`
- SYSFW RM common note: `docs/common/2026-05-21_AM64x_sysfw-rm-resource-ownership.md`
- Original Phase 3 draft: `.agents/phase3_status_protocol_plan.md`

## 결론

Phase 3는 현재 저장소 기준으로 보면
`projects/am64x-r5f-button-event-lab`을 기반으로 진행하는 것이 가장 비용이 낮고,
가장 실제 구현 자산에 가깝다.

즉,

```text
Phase 2 baseline 정리
  -> 상태 모델 추가
  -> Phase 1 GPIO output 재통합
  -> status/event/error contract 정리
  -> regression 문서화
```

의 순서로 진행하는 것을 권장한다.
