# UART Daemon Attach / MCP Upgrade Plan

## Goal

현재 `tools/uart/uartd.py` / `tools/uart/uartctl.py` 기반 UART daemon 구조를 유지하면서, `.agents/uartd_attach_mcp_upgrade_design_v2_no_write_lock.md`의 방향에 맞춰 다음 기능을 단계적으로 추가한다.

- 사람이 사용하는 `uartctl attach` interactive UART 콘솔
- 사람이 사용하는 `uartctl watch` read-only live UART 콘솔
- attach / watch / MCP가 같은 UART 세션을 공유하는 shared-write 모델
- Agent가 사용할 MCP 어댑터와 MCP-friendly JSON 응답
- `send_expect` 계열 output/offset/timeout 정보 강화

최종적으로는 `uartd`만 UART 포트를 직접 열고, 사람과 Agent는 모두 `uartd`를 통해 같은 UART 세션을 공유하는 구조를 만든다.

## Current Baseline

현재 워킹트리 기준 사실:

- `uartd.py`는 `status`, `send`, `expect`, `send_expect`, `tail`, `stop` JSON API를 이미 가진다.
- `uartctl.py`는 `status`, `send`, `expect`, `command`, `tail`, `stop` CLI를 이미 가진다.
- `uartctl expect`와 `uartctl command`에는 `--fresh`, `--from-offset`가 이미 반영되어 있다.
- `tail`은 JSON event stream이며, raw terminal stream은 아직 없다.
- `runtime_log`는 daemon 소유의 1차 UART 증적 파일이다.
- `attach`, `watch`, MCP adapter, TCP console은 아직 구현되지 않았다.

## Constraints

- `/dev/ttyUSBx`는 오직 `uartd.py`만 직접 open한다.
- `logs/runtime_log`를 UART 1차 증적 sink로 유지한다.
- 기존 JSON line API는 가능한 한 호환성을 유지하며 확장한다.
- shared-write 정책을 따른다. write lock / ownership 강제 차단은 구현하지 않는다.
- `tail`은 유지한다. 자동화와 로그 수집에서는 JSON event stream이 여전히 유용하다.
- 구현 순서는 attach/watch -> 상태/metadata -> output 개선 -> MCP 순으로 진행한다.
- TCP console은 optional phase로 두고, 앞선 단계가 안정화되기 전에는 구현하지 않는다.

## Out of Scope

- UART 외 보드 제어(power cycle, flashing, recovery automation)
- SDK workspace 변경
- boot policy 변경
- systemd unit 자동 설치
- TCP console 기본 활성화

## File Targets

Primary:

- `tools/uart/uartd.py`
- `tools/uart/uartctl.py`

Secondary:

- `docs/common/UART_DAEMON_AGENT_WORKFLOW.md`
- `tools/README.md`
- `AGENTS.md`
- `README.md`

Future MCP files:

- `tools/uart/uart-mcp-server.py`
- 필요 시 MCP usage 문서 또는 opencode 설정 예시 문서

## Phase Plan

## Phase 0 - Baseline Test Harness

목표:

- 현재 daemon/client 동작을 보호하는 테스트 기반 확보

작업:

1. fake serial object와 임시 socket/log 경로를 사용하는 테스트 harness 추가
2. 현재 기능 기준 baseline test 작성
   - `status`
   - `send`
   - `expect`
   - `send_expect`
   - `tail`
   - `stop`
   - `fresh`
   - `from_offset`
3. `uartctl.py` parser / client 호출 테스트 추가

검증:

- `python3 -m pytest tests/tools/uart`
- `python3 -m py_compile tools/uart/uartd.py tools/uart/uartctl.py`

권장 커밋 경계:

- `test: add UART daemon baseline coverage`

## Phase 1 - Attach / Watch Raw Stream

목표:

- 사람이 raw UART 콘솔처럼 붙을 수 있는 `attach`
- read-only live console인 `watch`

작업:

1. `ClientState`에 attach 관련 필드 추가
   - `attached`
   - `attach_mode`
   - `client_id`
   - `raw_after_handshake`
2. daemon 상태에 `next_client_id` 추가
3. client accept 시 `client_id` 부여
4. `_read_client()`에 raw attach 입력 분기 추가
5. `_write_serial_bytes()` 추가
6. `_read_serial()`에서 attached client에 raw bytes broadcast 추가
7. `attach` action 추가
8. `uartctl attach` 구현
9. `uartctl watch` 구현
10. `Ctrl-] q` detach sequence는 최종 목표로 두되, MVP는 우선 `Ctrl-C` 종료 또는 단순 detach sequence 중 더 안전한 최소 구현을 선택

검증:

- PTY 기반 시뮬레이션에서 attach 화면에 UART 출력이 live로 보이는지
- attach 입력이 UART TX로 전달되는지
- watch는 출력만 보고 입력을 UART로 보내지 않는지
- attach/watch 중 `runtime_log`가 계속 append되는지

권장 커밋 경계:

- `tools: add uart attach and watch streams`

## Phase 2 - Shared-Write Status / Metadata

목표:

- shared-write 정책을 유지하면서 상태 관찰 정보 제공

작업:

1. daemon 상태에 `last_write_source`, `last_write_at` 추가
2. `status` 응답 확장
   - `attached_clients`
   - `rw_attach_clients`
   - `ro_attach_clients`
   - `monitor_clients`
   - `shared_write`
   - `last_write_source`
   - `last_write_at`
3. `send`, `send_expect`, attach input에서 source 기록
4. attach/watch handshake 응답에 `active_attach_clients` 포함
5. daemon log에 선택적 write marker 추가 여부 판단

검증:

- attach 중 `uartctl command`가 정상 동작하는지
- attach 화면에 command 결과가 보이는지
- `status` 값이 attach/watch/command 동작에 따라 갱신되는지

권장 커밋 경계:

- `tools: add shared-write UART session metadata`

## Phase 3 - send_expect / command Output Improvement

목표:

- Agent/MCP가 판단 가능한 richer response 제공

작업:

1. `send_expect` 시작 offset 저장
2. `output_since_start` 또는 `output` 추출 helper 추가
3. 성공 응답에 output text 포함
4. timeout 응답에 recent tail / output_since_start / offset 범위 포함
5. `uartctl command` 출력도 이 확장 응답을 그대로 노출
6. newline 정책 확장 여부 결정
   - 기존 boolean 유지
   - 필요하면 `lf` / `crlf` / `cr` / `none` 확장

검증:

- `uartctl command "version" --expect "=> "` 응답에 실제 output 포함
- timeout 시 최근 출력이 함께 반환되는지
- `fresh` / `from-offset` semantics가 여전히 맞는지

권장 커밋 경계:

- `tools: enrich UART command and expect responses`

## Phase 4 - MCP Adapter

목표:

- UART 포트를 직접 열지 않는 thin MCP adapter 추가

작업:

1. `tools/uart/uart-mcp-server.py` 추가
2. MCP tool 1차 구현
   - `uart_status`
   - `uart_tail`
   - `uart_sendline`
   - `uart_expect`
   - `uart_command`
3. 각 tool은 `uartd` Unix socket JSON API만 호출
4. MCP tool description 문구 작성
5. repo guidance / opencode 설정 예시 문서화

검증:

- MCP adapter 재시작이 UART ownership을 깨지 않는지
- attach 중 MCP tool 사용이 막히지 않는지
- MCP timeout 응답이 Agent 판단에 충분한지

권장 커밋 경계:

- `tools: add UART MCP adapter`
- `docs: add UART MCP usage guidance`

## Phase 5 - Optional TCP Console

목표:

- 로컬 loopback 기반 TCP console 확장 가능성 확보

작업:

1. TCP listener 옵션 추가
2. TCP client를 attach rw client와 동일하게 취급
3. 기본 bind는 `127.0.0.1`
4. SSH tunnel 전제 문서화

진입 조건:

- attach/watch/MCP가 안정화된 뒤에만 착수
- 실제 사용자 요구가 명확할 때만 구현

권장 커밋 경계:

- `tools: add optional TCP console for uartd`

## Risks

1. attach raw stream을 넣으면 현재 JSON-only `_read_client()` / `recv_buffer` 모델이 달라진다.
2. raw attach와 JSON command client를 같은 selector loop에서 섞어 처리하므로 client state 전환 버그 위험이 크다.
3. shared-write 모델에서는 UX 충돌보다 **운영 관찰 정보 부족**이 더 큰 문제다.
4. `send_expect` output 추출은 buffer trimming과 offset semantics를 깨뜨리기 쉽다.
5. raw bytes broadcast와 text buffer/log 저장을 같이 유지해야 하므로 decode boundary 처리에 주의가 필요하다.
6. MCP는 daemon API가 충분히 안정화되기 전에 붙이면 다시 인터페이스를 깨기 쉽다.

## Verification Strategy

단계별 검증 원칙:

1. 각 phase마다 fake serial 기반 automated test 추가
2. 각 phase마다 PTY 기반 end-to-end 시뮬레이션 유지
3. changed file diagnostics clean 유지
4. `runtime_log` append behavior는 모든 phase에서 regression check 포함
5. raw terminal 기능은 최소 한 번 실제 interactive smoke test 필요

## Suggested Commit Strategy

1. `test: add UART daemon baseline coverage`
2. `tools: add uart attach and watch streams`
3. `tools: add shared-write UART session metadata`
4. `tools: enrich UART command and expect responses`
5. `tools: add UART MCP adapter`
6. `docs: document UART daemon attach and MCP workflow`

## Implementation Readiness Checklist

구현 시작 전 확인:

- [ ] 현재 dirty worktree에서 `tools/uart/uartd.py`, `tools/uart/uartctl.py`를 baseline으로 고정했는가
- [ ] attach/watch를 먼저 하고 MCP는 뒤로 미룬다는 순서에 합의했는가
- [ ] shared-write 정책에서 write lock을 구현하지 않는다는 점이 명확한가
- [ ] `runtime_log`를 1차 증적으로 유지한다는 점이 유지되는가
- [ ] commit 단위를 phase 기준으로 자를 준비가 되었는가

## Immediate Next Step

다음 구현 작업은 **Phase 0 + Phase 1 범위만** 대상으로 잡는다.

즉, 바로 다음 세션/작업에서는:

1. UART daemon baseline test harness 추가
2. `attach` / `watch` raw stream 구현
3. PTY 기반 attach/watch end-to-end 검증

까지를 첫 목표로 한다.
