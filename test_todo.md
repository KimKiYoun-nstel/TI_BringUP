# UART MCP Test Todo

새 세션에서 단일 `uart` MCP와 `target` 파라미터가 정상 동작하는지 빠르게 확인한다.

## 전제

- opencode를 재시작해서 최신 `opencode.jsonc`를 반영한다.
- 로컬 SK `uartd`는 실행 중이어야 한다.
  - 기본 TCP: `127.0.0.1:17001`
- 커스텀 보드 원격 `uartd`도 실행 중이어야 한다.
  - target profile: `192.168.0.170:17001`

## 확인 목표

- MCP server는 `uart` 하나만 보인다.
- 각 tool에 `target` 파라미터가 보인다.
- `target=sk`와 `target=custom` 호출이 각각 정상 동작한다.

## 테스트 순서

### 1. tool 목록 확인

- `uart_status`
- `uart_tail`
- `uart_sendline`
- `uart_expect`
- `uart_command`
- 각 tool input schema에 `target`이 있는지 확인

### 2. SK target 테스트

- `uart_status` with `target=sk`
- `uart_tail` with `target=sk`, `lines=20`
- `uart_command` with:

```json
{"target":"sk","line":"uname -n","expect":"# ","timeout":5}
```

기대 결과:

- endpoint가 `tcp://127.0.0.1:17001`
- shell prompt 또는 `linux_root` 상태 확인
- `uname -n` 출력 확인

### 3. custom target 테스트

- `uart_status` with `target=custom`
- `uart_tail` with `target=custom`, `lines=20`
- `uart_expect` with:

```json
{"target":"custom","pattern":"# ","timeout":1,"from":"buffer"}
```

기대 결과:

- endpoint가 `tcp://192.168.0.170:17001`
- root shell prompt backlog 또는 현재 상태 확인

## 주의

- 커스텀 보드는 원격 host에서 daemon이 실행 중이므로 local filesystem의 `runtime_log` 직접 확인을 기대하지 않는다.
- 커스텀 보드에 이미 다른 사용자가 `attach` 중일 수 있으므로, 새 세션 테스트는 가능하면 `status`, `tail`, `expect` 위주로 진행한다.
