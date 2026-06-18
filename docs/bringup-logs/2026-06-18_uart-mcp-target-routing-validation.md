# 2026-06-18 UART MCP Target Routing Validation

## 목적

- SK-AM64B 로컬 `uartd`를 Unix socket과 TCP `127.0.0.1:17001`을 함께 여는 기본 모델로 정리한다.
- `uartctl.py`와 `uart-mcp-server.py`가 공통 target profile(`sk`, `custom`)을 사용하도록 맞춘다.
- MCP는 단일 `uart` server를 유지하고, 실제 호출에서 `target` 파라미터로 보드를 구분한다.

## 이번 변경 범위

- `tools/uart/targets.json`
  - `sk`, `custom` target endpoint profile 추가
- `tools/uart/uart_endpoint.py`
  - target profile 로딩, TCP/Unix endpoint 해석 공용 모듈 추가
- `tools/uart/uartctl.py`
  - 기본 endpoint를 target profile 기반 TCP로 전환
  - `--target sk|custom` 지원
- `tools/uart/uart_mcp_server.py`
  - Unix socket 고정 접근에서 multi-target endpoint 접근으로 변경
  - 모든 MCP tool 입력에 `target` 추가
- `tools/uart/uartd.py`
  - Linux/WSL에서 기본적으로 Unix socket + TCP `127.0.0.1:17001` 동시 활성
  - `--no-tcp` 지원
- `opencode.jsonc`
  - 단일 generic `uart` MCP 유지
  - 기본 target은 `sk`

## 검증 결과

### 1. 로컬 SK-AM64B daemon

- 실행 포트: `/dev/ttyUSB1`
- control endpoint:
  - Unix socket: `/home/nstel/ti/TI_Bringup/logs/uartd.sock`
  - TCP: `127.0.0.1:17001`
- `./tools/uart/uartctl.py status` 정상
- `./tools/uart/uartctl.py --socket ... status` fallback 정상

### 2. `uartctl.py` target 분기

- 기본 호출은 `sk` target으로 TCP `127.0.0.1:17001` 접속
- `./tools/uart/uartctl.py --target custom status` 정상

### 3. MCP target 분기

직접 `tools/uart/uart-mcp-server.py`를 JSON-RPC로 호출해 검증함.

- `uart_status(target=sk)` 정상
- `uart_tail(target=sk)` 정상
- `uart_command(target=sk, line="uname -n", expect="# ")` 정상
- `uart_status(target=custom)` 정상
- `uart_tail(target=custom)` 정상
- `uart_expect(target=custom, pattern="# ")` 정상

## 확인된 현재 정책

- MCP server는 `uart` 하나만 유지한다.
- tool 수 증대를 막기 위해 target별 MCP alias는 사용하지 않는다.
- 실제 보드 구분은 MCP tool argument의 `target`으로 처리한다.

예:

```json
{"target":"sk","line":"uname -n","expect":"# ","timeout":5}
{"target":"custom","pattern":"# ","timeout":1,"from":"buffer"}
```

## 주의사항

- 커스텀 보드 `uartd`는 원격 Windows host에서 실행 중이므로, 이 repo host에서 원격 `runtime_log` 파일을 직접 증적으로 관리할 수 있다고 가정하지 않는다.
- 커스텀 보드 경로는 현재 status/tail/expect 같은 daemon API 기반 확인을 기준으로 본다.
- `opencode.jsonc` 변경은 새 세션 또는 재시작 후에만 반영된다.
