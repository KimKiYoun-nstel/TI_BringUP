# UART MCP 새 세션 확인

OpenCode를 종료 후 repo 루트에서 재시작해 최신 `opencode.jsonc`를 반영한다.
`tools/uart/.secrets/{sk,tmds}.token`이 준비되어 있고 원격 daemon이 실행 중이어야 한다.

## 확인 목표

- 단일 `uart` MCP에 tool 11개가 보이고 모두 `target` 인자를 제공한다.
- `sk=192.168.0.33:17001`, `tmds=192.168.0.33:17002`로 인증된 호출이 라우팅된다.
- `uart_send`, `uart_list_ports`, `uart_set_port`, `uart_disconnect`, `uart_baud` 신기능이 보인다.

## 읽기 전용 확인 순서

각 target에 다음을 호출한다.

```text
uart_status(target="sk")
uart_tail(target="sk", lines=20)
uart_list_ports(target="sk")
uart_status(target="tmds")
uart_tail(target="tmds", lines=20)
uart_list_ports(target="tmds")
```

기대 결과:

- `status.ok=true`와 `serial_state=connected`, 올바른 endpoint/instance_id를 확인한다.
- `tail`은 해당 보드의 최근 로그를 반환한다. prompt 상태는 조회 시점에 따라 다를 수 있다.
- `list_ports`는 원격 서버의 COM 목록을 반환한다.

보드 입력이 필요한 작업에서는 prompt 확인 후 다음 형식으로 실행한다.

```json
{"target":"sk","line":"uname -n","expect":"# ","timeout":5,"newline":"lf"}
```

위 JSON은 `uart_command` 인자다. timeout이면 재전송 전에 같은 target의 `uart_tail`을 확인한다.
포트 전환/baud 변경/reboot는 실제 작업에서 필요할 때 수행한다.

원격 `runtime_log`는 서버 파일이다. 로컬 `logs/runtime_log`와 자동 동기화되는 것으로 가정하지 않는다.
상세 사용법은 [tools/uart/README.md](tools/uart/README.md)를 따른다.
